# backend/rag/retriever.py

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.config import settings
from backend.models import Citation
from backend.rag.embeddings import embed_query
from .reranker import rerank
from .sparse_utils import build_sparse_vector


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
        vector = embed_query(query)
        if not vector:
            return []
        return client.query_points(
            collection_name=settings.active_collection_name,
            query=vector,
            using="dense",
            query_filter=qfilter,
            limit=limit,
            with_payload=True,
        ).points
    except Exception as exc:
        print("[retriever] dense search failed:", repr(exc))
        return []


def _search_sparse(query, client, qfilter=None, limit=25):
    try:
        sparse = build_sparse_vector(query, settings.sparse_dim)
        if not sparse.indices:
            return []
        return client.query_points(
            collection_name=settings.active_collection_name,
            query=sparse,
            using="sparse",
            query_filter=qfilter,
            limit=limit,
            with_payload=True,
        ).points
    except Exception as exc:
        print("[retriever] sparse search failed:", repr(exc))
        return []


def _rrf_merge(dense_hits, sparse_hits, k=60):
    """Reciprocal Rank Fusion avoids normalizing incomparable dense/sparse scores."""
    scores, payloads = {}, {}
    for hits in (dense_hits, sparse_hits):
        for rank, hit in enumerate(hits or [], start=1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank)
            payloads[hit.id] = hit.payload
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
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
    dense_k = int(settings.dense_candidate_k)
    sparse_k = int(settings.sparse_candidate_k)
    rerank_pool = int(settings.rerank_pool_size)

    dense_hits = _search_dense(query, client, qfilter, dense_k)
    sparse_hits = _search_sparse(query, client, qfilter, sparse_k)
    merged = _rrf_merge(dense_hits, sparse_hits)
    pool = merged[:rerank_pool]
    if not pool:
        return []

    citations = [
        Citation(
            source=payload.get("source_name", "Unknown"),
            chunk=payload.get("text", ""),
            score=round(float(score), 4),
            page_start=payload.get("page_start"),
            page_end=payload.get("page_end"),
            section=payload.get("section"),
            topic=payload.get("topic"),
            content_type=payload.get("content_type"),
            source_type=payload.get("source_type"),
            source_priority=payload.get("source_priority"),
        )
        for _, score, payload in pool
    ]
    return rerank(query, citations)[: settings.top_k]
