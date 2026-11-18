"""Mode-aware embedding adapter.

Local mode uses the project's biomedical SentenceTransformer encoder.
API mode uses OpenAI embeddings and never imports torch or sentence-transformers.
The API collection must be re-ingested when switching embedding backends.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from backend.config import settings
from backend.openai_client import get_openai_client


@lru_cache(maxsize=1)
def _get_local_encoder():
    if settings.active_embedding_backend != "local":
        raise RuntimeError("Local embedding encoder is disabled in API mode.")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Local mode needs sentence-transformers. Install requirements-local.txt."
        ) from exc
    encoder = SentenceTransformer(settings.embedding_model, device=settings.retrieval_device)
    encoder.eval()
    return encoder


def embedding_dimension() -> int:
    if settings.active_embedding_backend == "openai":
        return int(settings.openai_embedding_dimensions)
    return int(_get_local_encoder().get_sentence_embedding_dimension())


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    clean_texts = [str(text or "") for text in texts]
    if not clean_texts:
        return []

    if settings.active_embedding_backend == "openai":
        client = get_openai_client()
        output: list[list[float]] = []
        batch_size = max(1, min(int(settings.embedding_batch_size), 128))
        for start in range(0, len(clean_texts), batch_size):
            batch = clean_texts[start : start + batch_size]
            response = client.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
                dimensions=settings.openai_embedding_dimensions,
                encoding_format="float",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            output.extend([list(item.embedding) for item in ordered])
        return output

    encoder = _get_local_encoder()
    vectors = encoder.encode(
        clean_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=max(1, int(settings.embedding_batch_size)),
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
