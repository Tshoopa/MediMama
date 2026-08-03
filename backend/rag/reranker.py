# backend/rag/reranker.py

import os
from sentence_transformers import CrossEncoder

from backend.models import Citation
from backend.config import settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_cross_encoder = None

# Queries containing any of these are treated as acute clinical symptoms.
_CLINICAL_SYMPTOM_TERMS = [
    "pain", "hurt", "ache", "sore", "injury", "wound", "fever", "sick",
    "constipat", "poop", "cough", "breathe", "breathing", "fall", "fell",
    "hit", "bump", "swallow", "accident", "crying", "cry",
]

# HACK: the cross-encoder keeps ranking these lifestyle/developmental
# topics highly for symptom queries (e.g. "tummy pain" -> "tummy time").
# We just penalize them until the retrieval data is cleaned up properly.
_DEVELOPMENTAL_TERMS = [
    "tummy time", "cradle cap", "sleep training", "teething", "chewing on toys",
]


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        model_name = getattr(settings, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        device = str(getattr(settings, "reranker_device", "cpu") or "cpu").lower()
        print(f"[INFO] Loading cross-encoder: {model_name} on {device}")
        _cross_encoder = CrossEncoder(model_name, max_length=512, device=device)
    return _cross_encoder


def rerank(query: str, citations: list[Citation]) -> list[Citation]:
    if not citations or not query or not query.strip():
        return citations

    try:
        encoder = _get_cross_encoder()

        pairs = []
        for c in citations:
            chunk_text = c.chunk or ""
            if c.topic:
                chunk_text = f"{c.topic}. {chunk_text}"
            pairs.append([query, chunk_text[:512]])

        scores = encoder.predict(pairs, batch_size=8, convert_to_numpy=True, show_progress_bar=False)

        q_clean = query.lower()
        is_symptom_query = any(w in q_clean for w in _CLINICAL_SYMPTOM_TERMS)

        for c, score in zip(citations, scores):
            score_val = float(score)
            if is_symptom_query:
                text = (c.chunk or "").lower() + " " + (c.topic or "").lower()
                if any(t in text for t in _DEVELOPMENTAL_TERMS):
                    score_val -= 8.0
            c.score = round(score_val, 4)

        citations.sort(key=lambda x: x.score, reverse=True)
        return citations

    except Exception as e:
        print("[reranker] failed, returning original order:", repr(e))
        return citations