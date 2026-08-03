# backend/rag/ingestor.py

import os
import json
import re
from typing import List, Dict, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client.models import PointStruct, SparseVector

# Works both as a package (backend.rag.ingestor) and run directly from rag/.
try:
    from backend import config
    from .vector_store import get_client, ensure_collection
    from .sparse_utils import build_sparse_vector
except (ImportError, ValueError):
    import config
    from vector_store import get_client, ensure_collection
    from sparse_utils import build_sparse_vector


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00ad", "")  # soft hyphen
    return re.sub(r"\s+", " ", text).strip()


def _split_qa_from_text(text: str) -> Tuple[str, str]:
    m = re.search(r"Q:\s*(.*?)\s*A:\s*(.*)", text.strip(), re.S | re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", text.strip()


def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def smart_chunk_text(
    text: str,
    embedder: SentenceTransformer,
    similarity_threshold: float = 0.65,
    max_words: int = 220,
) -> List[str]:
    """Semantic chunking; short QA pairs are kept as a single chunk."""
    cleaned_text = normalize_text(text)
    if not cleaned_text:
        return []

    # Short entries fit in one chunk — no point splitting them.
    if len(cleaned_text.split()) <= max_words:
        return [cleaned_text]

    sentences = re.split(r'(?<=[.!?؟])\s+', cleaned_text)
    if len(sentences) <= 1 or embedder is None:
        return [cleaned_text]

    embeddings = embedder.encode(sentences, show_progress_bar=False)

    chunks = []
    current_sentences = [sentences[0]]
    current_word_count = len(sentences[0].split())

    for i in range(len(sentences) - 1):
        similarity = _cosine_similarity(embeddings[i], embeddings[i + 1])
        next_word_count = len(sentences[i + 1].split())

        # Break on topic drift or when the word budget is exceeded.
        if similarity < similarity_threshold or (current_word_count + next_word_count > max_words):
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentences[i + 1]]
            current_word_count = next_word_count
        else:
            current_sentences.append(sentences[i + 1])
            current_word_count += next_word_count

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


# Keep sparse-vector logic in one place so index-time and query-time stay
# in sync — a mismatch here silently kills keyword recall.
def sparse_from_text(text: str) -> SparseVector:
    return build_sparse_vector(text, config.settings.sparse_dim)


def load_qa_documents(json_path: str) -> List[Dict]:
    docs = []
    if not os.path.exists(json_path):
        print(f"[WARN] QA data file not found: {json_path}")
        return docs

    items = []
    with open(json_path, "r", encoding="utf-8") as f:
        if json_path.endswith(".jsonl"):
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception as e:
                    print(f"[WARN] Bad JSONL line {line_num}: {e}")
        else:
            try:
                items = json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to load JSON: {e}")

    skipped = 0
    for item in items:
        q = normalize_text(item.get("question", ""))
        a = normalize_text(item.get("answer", ""))

        # Fallback: some entries only have a raw "Q: ... A: ..." text field.
        if not q and not a:
            raw_text = item.get("text", "")
            if raw_text:
                q, a = _split_qa_from_text(raw_text)
                q, a = normalize_text(q), normalize_text(a)

        if not q and not a:
            skipped += 1
            continue

        full_text = f"Question: {q}\nAnswer: {a}" if (q and a) else (a or q)

        docs.append({
            "source_name": item.get("source", "Royal Children's Hospital Melbourne"),
            "topic": item.get("topic") or item.get("focus") or item.get("category", "general"),
            "age_group": item.get("age_group", "children"),
            "url": item.get("url", ""),
            "text": full_text,
            "question": q,
            "answer": a,
            "category": item.get("category", "general"),
        })

    print(f"[INFO] Loaded {len(docs)} documents ({skipped} skipped)")
    return docs


def ingest():
    client = get_client()

    print(f"[INFO] Loading embedding model: {config.settings.embedding_model}")
    embedder = SentenceTransformer(config.settings.embedding_model)
    dim = embedder.get_sentence_embedding_dimension()

    ensure_collection(client, vector_size=dim)

    qa_json = os.path.join(str(config.settings.data_dir), config.settings.qa_filename)
    qa_docs = load_qa_documents(qa_json)

    points = []
    point_id = 1
    for item in qa_docs:
        for chunk in smart_chunk_text(item["text"], embedder):
            points.append(PointStruct(
                id=point_id,
                vector={
                    "dense": embedder.encode(chunk).tolist(),
                    "sparse": sparse_from_text(chunk),
                },
                payload={
                    "source_type": "qa",
                    "source_name": item["source_name"],
                    "page_start": 0,
                    "page_end": 0,
                    "section": "faq",
                    "subsection": item["category"],
                    "topic": item["topic"],
                    "age_group": item["age_group"],
                    "content_type": "qa",
                    "source_priority": config.settings.source_priority_faq,
                    "url": item["url"],
                    "question": item["question"],
                    "answer": item["answer"],
                    "text": chunk,
                },
            ))
            point_id += 1

    if not points:
        print("[ERROR] No points generated; nothing to upsert.")
        return

    client.upsert(collection_name=config.settings.collection_name, points=points)
    print(f"[INFO] Upserted {len(points)} points.")

    try:
        info = client.get_collection(config.settings.collection_name)
        print(f"[INFO] Active points: {info.points_count}")
    except Exception as e:
        print("[WARN] Could not read collection info:", e)


if __name__ == "__main__":
    ingest()