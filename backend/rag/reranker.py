"""Optional local cross-encoder reranking.

API-only mode intentionally skips this stage to avoid downloading/loading any
local ML model; reciprocal-rank fusion order is kept instead.
"""

from functools import lru_cache

from backend.config import settings


@lru_cache(maxsize=1)
def _get_cross_encoder():
    if settings.inference_mode == "api" or not settings.reranker_enabled:
        return None
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError("Local reranking requires requirements-local.txt") from exc
    return CrossEncoder(
        settings.reranker_model,
        max_length=512,
        device=settings.reranker_device,
    )


def rerank(query: str, citations: list):
    if not citations or not query or not query.strip():
        return citations
    if settings.inference_mode == "api" or not settings.reranker_enabled:
        return citations

    try:
        encoder = _get_cross_encoder()
        if encoder is None:
            return citations

        pairs = []
        for citation in citations:
            chunk_text = citation.chunk or ""
            if citation.topic:
                chunk_text = f"{citation.topic}. {chunk_text}"
            pairs.append([query, chunk_text[:512]])
        scores = encoder.predict(
            pairs, batch_size=8, convert_to_numpy=True, show_progress_bar=False
        )
        for citation, score in zip(citations, scores):
            citation.score = round(float(score), 4)
        citations.sort(key=lambda item: item.score, reverse=True)
        return citations
    except Exception as exc:
        print("[reranker] failed, keeping reciprocal-rank order:", repr(exc))
        return citations
