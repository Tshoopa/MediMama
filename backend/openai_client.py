"""Shared lazy OpenAI client. No OpenAI SDK is imported in local-only paths
unless an API feature (translation, embeddings, or optional triage assist) is used.
"""

from functools import lru_cache

from backend.config import settings


@lru_cache(maxsize=1)
def get_openai_client():
    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is required for this operation.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - installation guidance
        raise RuntimeError("Install the API dependencies: pip install -r requirements.txt") from exc

    return OpenAI(
        api_key=settings.openai_api_key.strip(),
        base_url=settings.openai_base_url.strip() or "https://api.openai.com/v1",
        timeout=settings.openai_timeout_seconds,
        max_retries=1,
    )
