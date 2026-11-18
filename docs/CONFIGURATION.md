# Configuration

All settings resolve from environment variables or `.env`. Copy `.env.example` to `.env` and select one of the two runtime modes.

## Runtime mode

| Variable | Default | Purpose |
|---|---|---|
| `INFERENCE_MODE` | `api` | `local` loads MedGemma 1.5 4B; `api` uses OpenAI and no local ML models |
| `COLLECTION_NAME` | empty | Optional explicit Qdrant collection; if empty, `medimama_local` or `medimama_api` is selected automatically |

Install dependencies that match the selected mode:

```bash
pip install -r requirements.txt          # API-only, lightweight
pip install -r requirements-local.txt    # local MedGemma + local retrieval models
```

Changing the mode changes the embedding backend and vector dimension. Re-ingest the corpus after switching modes.

## OpenAI API

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | empty | Required for API mode; optional in local mode unless API assists are enabled or translation is explicitly switched to OpenAI |
| `OPENAI_BASE_URL` | OpenAI API URL | API base URL |
| `OPENAI_MODEL` | `gpt-6.1-sol` | API answer-generation and optional triage-assist model |
| `OPENAI_TRANSLATION_MODEL` | `gpt-6-luna` | Explicit Persian/Arabic/English translation |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Dense vectors in API mode |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | Dense vector dimension; must match the selected embedding model and Qdrant collection |
| `OPENAI_TIMEOUT_SECONDS` | `30` | OpenAI client timeout |
| `TRANSLATION_BACKEND` | `auto` | `auto` selects local MedGemma in local mode and OpenAI in API mode; API mode cannot load local translation |

The key is used only by the backend. Never put it in `frontend/config.js` or commit `.env`.

## Local model — Mode 1 only

| Variable | Default | Purpose |
|---|---|---|
| `LOCAL_MODEL_ID` | `google/medgemma-1.5-4b-it` | Hugging Face model ID |
| `HF_TOKEN` | empty | Hugging Face access token after accepting model terms |
| `LOCAL_DEVICE_MAP` | `auto` | Transformers device placement |
| `LOCAL_MODEL_DTYPE` | `auto` | `float16` on CUDA and `float32` on CPU; may set `bfloat16` on supported GPUs |
| `LOCAL_MAX_NEW_TOKENS` | `220` | Answer generation limit |
| `LOCAL_TRANSLATION_MAX_NEW_TOKENS` | `512` | Translation output limit when local translation is selected |
| `LOCAL_TEMPERATURE` | `0.1` | Sampling temperature |
| `LOCAL_REPETITION_PENALTY` | `1.15` | Repetition penalty |
| `LOCAL_MODEL_CACHE_DIR` | `./.model_cache` | Local model cache directory |

MedGemma is gated and governed by the Google Health AI Developer Foundations terms. Do not commit weights or access tokens.

## Embeddings and reranking

| Variable | Default | Purpose |
|---|---|---|
| `EMBEDDING_BACKEND` | `auto` | `auto` chooses local in `local` mode and OpenAI in `api` mode |
| `EMBEDDING_MODEL` | `pritamdeka/S-PubMedBert-MS-MARCO` | Local biomedical embedding model |
| `EMBEDDING_BATCH_SIZE` | `64` | Batch size for vector creation |
| `RERANKER_ENABLED` | `true` | Local cross-encoder in local mode; forced off in API mode |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local cross-encoder name |
| `RERANKER_DEVICE` | `cpu` | Device for the local reranker |
| `RETRIEVAL_DEVICE` | `cpu` | Device for local embeddings |
| `TOP_K` | `6` | Final citations |
| `DENSE_CANDIDATE_K` | `25` | Dense candidates before fusion |
| `SPARSE_CANDIDATE_K` | `25` | Sparse candidates before fusion |
| `RERANK_POOL_SIZE` | `15` | Candidate pool before local reranking |
| `SPARSE_DIM` | `1048576` | Hashed sparse-vector dimensionality |

API mode deliberately avoids local embedding, reranking, and semantic models. It uses reciprocal-rank fusion of dense OpenAI vectors and sparse keyword vectors.

## Vector store

| Variable | Default | Purpose |
|---|---|---|
| `QDRANT_URL` | empty | Cloud Qdrant URL; takes precedence over host/port |
| `QDRANT_API_KEY` | empty | Qdrant Cloud API key |
| `QDRANT_HOST` | `localhost` | Local server host (`qdrant` in Compose) |
| `QDRANT_PORT` | `6333` | Local server port |
| `QDRANT_PATH` | unset | Embedded local Qdrant path |

Use a separate Qdrant collection for each embedding backend. The application chooses `medimama_local` or `medimama_api` automatically unless `COLLECTION_NAME` is explicitly set.

## Optional triage assists

| Variable | Default | Purpose |
|---|---|---|
| `LLM_SAFETY_NET` | `false` | Enable an additional OpenAI triage review; escalation-only |
| `LLM_FEATURE_ASSIST` | `false` | Enable text-grounded feature extraction assistance |
| `EAGER_SAFETY_NET` | `false` | Start the safety-net request before its result is needed; may incur extra API cost |
| `LLM_TIMEOUT_SECONDS` | `15` | Optional triage-assist timeout setting |
| `LLM_DEBUG` | `false` | Debug output; avoid on public deployments |
| `FALLBACK_FLOOR_ENABLED` | `true` | Conservative non-emergency fallback floor |

Both optional assists transmit symptom text to OpenAI. They are disabled by default until separately evaluated.

## Privacy, CORS and server

| Variable | Default | Purpose |
|---|---|---|
| `AUDIT_LOG_SENSITIVE_FIELDS` | `false` | If false, raw question, age, answer and evidence chunks are not persisted in audit logs |
| `ALLOWED_ORIGINS` | localhost origins | Comma-separated exact browser origins; no wildcard |
| `PORT` | `8000` | HTTP port; cloud hosts can inject their own `PORT` |

Keep sensitive audit logging disabled for demos. The API still needs authentication and rate limiting before public production exposure.
