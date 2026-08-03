# backend/config.py
"""Application settings, resolved from environment variables or a .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── Local generation model (llama.cpp / Meditron) ──
    model_path: Path = BASE_DIR / "models" / "meditron-7b.Q4_K_M.gguf"
    model_type: str = "llama"
    max_new_tokens: int = 512
    temperature: float = 0.2

    # -1 offloads every layer to the GPU. Set LLM_N_GPU_LAYERS=0 for CPU-only.
    llm_n_gpu_layers: int = -1
    llm_context_size: int = 4096

    # ── Safety-net LLM (any OpenAI-compatible provider) ──
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 12.0

    # ── Vector store ──
    # qdrant_path selects the embedded on-disk store. Leave it unset to use the
    # host/port server, which is what docker-compose provides.
    qdrant_path: Path | None = None
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "medimama"

    # ── Retrieval ──
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    top_k: int = 6
    dense_candidate_k: int = 25
    sparse_candidate_k: int = 25

    # Must stay larger than top_k so the cross-encoder can recover from dense
    # and sparse ranking errors.
    rerank_pool_size: int = 15
    sparse_dim: int = 2**20

    # Retrieval models stay on CPU so their CUDA context does not collide with
    # llama.cpp, which owns the GPU for Meditron.
    retrieval_device: str = "cpu"
    reranker_device: str = "cpu"

    # ms-marco cross-encoder scores are typically negative; higher is better.
    max_display_citations: int = 3
    min_rerank_score_for_display: float = -7.0

    # ── Query expansion ──
    # Disabled by default so a plain "fever" is not expanded toward meningitis.
    enable_query_expansion: bool = False
    semantic_embedding_model: str = "all-MiniLM-L6-v2"
    semantic_device: str = "cpu"
    semantic_similarity_threshold: float = 0.65

    # ── Paths ──
    data_dir: Path = BASE_DIR / "data"
    sources_dir: Path = BASE_DIR / "data" / "sources"
    synonyms_path: Path = BASE_DIR / "data" / "medical_synonyms.json"
    audit_log_path: Path = BASE_DIR / "logs" / "audit.jsonl"
    eval_path: Path = BASE_DIR / "data" / "eval" / "pediatric_vignettes.jsonl"
    qa_filename: str = "pediatric_qa.jsonl"

    source_priority_guidelines: int = 10
    source_priority_faq: int = 5

    # ── CORS ──
    # Comma-separated list of allowed browser origins.
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()