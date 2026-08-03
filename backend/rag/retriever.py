# backend/rag/retriever.py

import os

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.config import settings
from backend.models import Citation
from .reranker import rerank
from .sparse_utils import build_sparse_vector

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_embedder = None


def _device() -> str:
    return str(getattr(settings, "retrieval_device", "cpu") or "cpu").lower()


def _get_embedder():
    global _embedder
    if _embedder is None:
        print(f"[INFO] Loading embedder: {settings.embedding_model} on {_device()}")
        _embedder = SentenceTransformer(settings.embedding_model, device=_device())
        _embedder.eval()
    return _embedder


def build_filter(source_type=None, age_group=None, content_type=None, topic=None):
    must = []
    if source_type:
        must.append(FieldCondition(key="source_type", match=MatchValue(value=source_type)))
    if age_group:
        must.append(FieldCondition(key="age_group", match=MatchValue(value=age_group)))
    if content_type:
        must.append(FieldCondition(key="content_type", match=MatchValue(value=content_type)))
    if topic:
        must.append(FieldCondition(key="topic", match=MatchValue(value=topic)))
    return Filter(must=must) if must else None


def _search_dense(query, client, qfilter=None, limit=25):
    try:
        vector = _get_embedder().encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
            device=_device(),
            show_progress_bar=False,
        ).tolist()
        return client.query_points(
            collection_name=settings.collection_name,
            query=vector, using="dense",
            query_filter=qfilter, limit=limit, with_payload=True,
        ).points
    except Exception as e:
        print("[retriever] dense search failed:", repr(e))
        return []


def _search_sparse(query, client, qfilter=None, limit=25):
    try:
        sparse = build_sparse_vector(query, settings.sparse_dim)
        if not sparse.indices:
            return []
        return client.query_points(
            collection_name=settings.collection_name,
            query=sparse, using="sparse",
            query_filter=qfilter, limit=limit, with_payload=True,
        ).points
    except Exception as e:
        print("[retriever] sparse search failed:", repr(e))
        return []


def _rrf_merge(dense_hits, sparse_hits, k=60):
    """Reciprocal Rank Fusion — avoids normalizing incomparable dense/sparse scores."""
    scores, payloads = {}, {}
    for hits in (dense_hits, sparse_hits):
        for rank, h in enumerate(hits or [], start=1):
            scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (k + rank)
            payloads[h.id] = h.payload
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(doc_id, score, payloads[doc_id]) for doc_id, score in ranked]


def retrieve(
    query: str,
    client: QdrantClient,
    source_type=None,
    age_group=None,
    content_type=None,
    topic=None,
) -> list[Citation]:
    if client is None or not query or not query.strip():
        return []

    qfilter = build_filter(source_type, age_group, content_type, topic)

    dense_k = int(getattr(settings, "dense_candidate_k", 25))
    sparse_k = int(getattr(settings, "sparse_candidate_k", 25))
    rerank_pool = int(getattr(settings, "rerank_pool_size", 15))

    dense_hits = _search_dense(query, client, qfilter, dense_k)
    sparse_hits = _search_sparse(query, client, qfilter, sparse_k)

    merged = _rrf_merge(dense_hits, sparse_hits)

    # Send a wider pool than top_k to the reranker, otherwise the right doc
    # can get dropped before the cross-encoder ever scores it.
    pool = merged[:rerank_pool]
    if not pool:
        return []

    citations = [
        Citation(
            source=p.get("source_name", "Unknown"),
            chunk=p.get("text", ""),
            score=round(float(score), 4),
            page_start=p.get("page_start"),
            page_end=p.get("page_end"),
            section=p.get("section"),
            topic=p.get("topic"),
            content_type=p.get("content_type"),
            source_type=p.get("source_type"),
            source_priority=p.get("source_priority"),
        )
        for _, score, p in pool
    ]

    citations = rerank(query, citations)
    return citations[: settings.top_k]