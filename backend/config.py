"""
Central application settings.

INFERENCE_MODE selects the answer-generation runtime:
- local: Qwen3-4B-Instruct-2507 via Transformers.
- api: OpenAI API only; no local transformer models are loaded.
"""


from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Runtime mode ──────────────────────────────────────────────
    inference_mode: Literal["local", "api"] = "api"

    # ── OpenAI API ────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-6.1-sol"
    openai_translation_model: str = "gpt-6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = 30.0
    translation_backend: Literal["auto", "local", "openai"] = "auto"

    # ── Local answer model (Mode 1 only) ──────────────────────────
    local_model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    hf_token: str = ""
    local_device_map: str = "auto"
    local_model_dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto"
    local_max_new_tokens: int = 220
    local_translation_max_new_tokens: int = 512
    local_temperature: float = 0.1
    local_repetition_penalty: float = 1.15
    local_model_cache_dir: str = str(BASE_DIR / ".model_cache")

    # ── RAG embeddings ───────────────────────────────────────────
    # auto resolves to local sentence-transformers in local mode and OpenAI
    # embeddings in API mode. API mode explicitly rejects local embeddings.
    embedding_backend: Literal["auto", "local", "openai"] = "auto"
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    embedding_batch_size: int = 64
    openai_embedding_dimensions: int = 1536

    # ── Vector store ─────────────────────────────────────────────
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_path: Path | None = None
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = ""

    # ── Retrieval ─────────────────────────────────────────────────
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_device: str = "cpu"
    retrieval_device: str = "cpu"
    top_k: int = 6
    dense_candidate_k: int = 25
    sparse_candidate_k: int = 25
    rerank_pool_size: int = 15
    sparse_dim: int = 2**20
    max_display_citations: int = 3
    min_rerank_score_for_display: float = -7.0

    # ── Optional semantic helpers (local mode only) ───────────────
    enable_query_expansion: bool = False
    semantic_models_enabled: bool = True
    semantic_embedding_model: str = "all-MiniLM-L6-v2"
    semantic_device: str = "cpu"
    semantic_similarity_threshold: float = 0.65

    # ── Optional API triage assists ───────────────────────────────
    llm_safety_net: bool = False
    llm_feature_assist: bool = False
    eager_safety_net: bool = False
    llm_timeout_seconds: float = 15.0
    llm_debug: bool = False
    llm_only_if_base_level_greater_than: int = 2
    fallback_floor_enabled: bool = True

    # ── Paths and source priorities ───────────────────────────────
    data_dir: Path = BASE_DIR / "data"
    sources_dir: Path = BASE_DIR / "data" / "sources"
    synonyms_path: Path = BASE_DIR / "data" / "medical_synonyms.json"
    audit_log_path: Path = BASE_DIR / "logs" / "audit.jsonl"
    audit_log_sensitive_fields: bool = False
    eval_path: Path = BASE_DIR / "data" / "eval" / "pediatric_vignettes.jsonl"
    qa_filename: str = "pediatric_qa.jsonl"
    source_priority_guidelines: int = 10
    source_priority_faq: int = 5

    # ── In-memory conversational demo sessions ───────────────────
    conversation_ttl_seconds: int = 1800
    conversation_max_sessions: int = 500
    conversation_max_clarification_turns: int = 3

    # ── CORS / server ─────────────────────────────────────────────
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("inference_mode", mode="before")
    @classmethod
    def normalize_inference_mode(cls, value):
        return str(value or "api").strip().lower()

    @field_validator("translation_backend", mode="before")
    @classmethod
    def normalize_translation_backend(cls, value):
        return str(value or "auto").strip().lower()

    @field_validator("embedding_backend", mode="before")
    @classmethod
    def normalize_embedding_backend(cls, value):
        return str(value or "auto").strip().lower()

    @property
    def active_translation_backend(self) -> str:
        if self.translation_backend == "auto":
            return "local" if self.inference_mode == "local" else "openai"
        if self.inference_mode == "api" and self.translation_backend == "local":
            raise ValueError(
                "API mode cannot use local translation. Set TRANSLATION_BACKEND=openai or auto."
            )
        return self.translation_backend

    @property
    def active_embedding_backend(self) -> str:
        if self.embedding_backend == "auto":
            return "openai" if self.inference_mode == "api" else "local"
        if self.inference_mode == "api" and self.embedding_backend == "local":
            raise ValueError(
                "API mode cannot use local embeddings. Set EMBEDDING_BACKEND=openai or auto."
            )
        return self.embedding_backend

    @property
    def active_collection_name(self) -> str:
        # The two modes use different vector dimensions. Separate collections
        # prevent accidental searches against incompatible vectors.
        return self.collection_name.strip() or f"medimama_{self.inference_mode}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_api_only(self) -> bool:
        return self.inference_mode == "api"


settings = Settings()

# Fail early on an unsafe/misconfigured combination.
_ = settings.active_embedding_backend
_ = settings.active_translation_backend
if settings.inference_mode == "api" and settings.reranker_enabled:
    # No local reranker can be loaded in the API-only runtime. RRF ranking is
    # used instead; users may not accidentally pull PyTorch into the image.
    settings.reranker_enabled = False
if settings.inference_mode == "api":
    settings.semantic_models_enabled = False
