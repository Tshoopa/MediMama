
# Configuration

All settings resolve from environment variables or a `.env` file. Copy `.env.example` to `.env` and adjust as needed.

## Local Generation Model

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `MODEL_PATH` | `models/meditron-7b.Q4_K_M.gguf` | Path to the GGUF weights |
| `MODEL_TYPE` | `llama` | Model family |
| `MAX_NEW_TOKENS` | `512` | Generation cap |
| `TEMPERATURE` | `0.2` | Sampling temperature |
| `LLM_N_GPU_LAYERS` | `-1` | `-1` offloads all layers to GPU; `0` forces CPU |
| `LLM_CONTEXT_SIZE` | `4096` | Context window |

## Safety-Net LLM

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_API_KEY` | — | **Required.** Provider credentials |
| `LLM_BASE_URL` | `https://api.deepseek.com` | Any OpenAI-compatible endpoint |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `LLM_TIMEOUT_SECONDS` | `12.0` | Timeout before falling back to deterministic triage |

The safety net uses an OpenAI-compatible client, so switching to OpenAI, Groq, Together, or a self-hosted vLLM endpoint requires only `LLM_BASE_URL` and `LLM_MODEL`. Provider choice is a cost and availability decision, not an architectural constraint.

## Vector Store

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `QDRANT_PATH` | unset | Embedded on-disk store. Leave unset to use a server. |
| `QDRANT_HOST` | `localhost` | Server host (`qdrant` under docker-compose) |
| `QDRANT_PORT` | `6333` | Server port |
| `COLLECTION_NAME` | `medimama` | Collection name |

`QDRANT_PATH` is useful in Colab, where running a separate service is inconvenient.

## Retrieval

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `EMBEDDING_MODEL` | `pritamdeka/S-PubMedBert-MS-MARCO` | Dense embeddings |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder reranker |
| `TOP_K` | `6` | Citations passed downstream after reranking |
| `DENSE_CANDIDATE_K` | `25` | Dense candidates before fusion |
| `SPARSE_CANDIDATE_K` | `25` | Sparse candidates before fusion |
| `RERANK_POOL_SIZE` | `15` | Candidates sent to the cross-encoder |
| `SPARSE_DIM` | `1048576` | Hashed sparse-vector dimensionality |
| `RETRIEVAL_DEVICE` | `cpu` | Embedding model device |
| `RERANKER_DEVICE` | `cpu` | Reranker device |
| `MAX_DISPLAY_CITATIONS` | `3` | Citations returned to the user |
| `MIN_RERANK_SCORE_FOR_DISPLAY` | `-7.0` | Rerank score floor for display |

**`RERANK_POOL_SIZE` must exceed `TOP_K`.** The cross-encoder can only correct dense or sparse ranking errors if it receives more candidates than are ultimately kept.

**Retrieval models stay on CPU by default.** `llama.cpp` owns the GPU for Meditron, so keeping embedding and reranking on CPU avoids CUDA context contention.

**`SPARSE_DIM` must match between indexing and querying.** A mismatch degrades keyword recall silently, with no error raised. Both paths share `backend/rag/sparse_utils.py` for exactly this reason.

**`MIN_RERANK_SCORE_FOR_DISPLAY` is deliberately conservative.** `ms-marco` scores are typically negative and higher is better. Showing a weakly relevant citation next to clinical guidance is worse than showing none, because a caregiver may read it as corroboration.

## Query Expansion

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `ENABLE_QUERY_EXPANSION` | `false` | Semantic expansion toggle |
| `SEMANTIC_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Expansion embeddings |
| `SEMANTIC_DEVICE` | `cpu` | Expansion device |
| `SEMANTIC_SIMILARITY_THRESHOLD` | `0.65` | Concept match threshold |

Disabled by default. During evaluation, expanding a plain query such as `fever` toward concepts like meningitis introduced false positives. It remains available behind a flag.

## Paths and Corpus

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATA_DIR` | `data/` | Corpus root |
| `SOURCES_DIR` | `data/sources/` | Raw source documents |
| `QA_FILENAME` | `pediatric_qa.jsonl` | Ingested QA corpus |
| `SYNONYMS_PATH` | `data/medical_synonyms.json` | Clinical synonym map |
| `EVAL_PATH` | `data/eval/pediatric_vignettes.jsonl` | Evaluation vignettes |
| `AUDIT_LOG_PATH` | `logs/audit.jsonl` | Audit log destination |
| `SOURCE_PRIORITY_GUIDELINES` | `10` | Trust weight for guideline sources |
| `SOURCE_PRIORITY_FAQ` | `5` | Trust weight for FAQ sources |

## CORS

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `ALLOWED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Comma-separated browser origin allowlist |

Parsed into a list by the `cors_origins` property. Wildcard origins are not used, so any new frontend host — including a tunnel URL used for demos — must be added explicitly.