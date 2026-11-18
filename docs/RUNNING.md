# Running MediMama

MediMama uses one codebase with two runtime modes. The mode is selected by `INFERENCE_MODE` in `.env`.

## Requirements

- Python 3.11+
- A Qdrant server or Qdrant Cloud account
- For API mode: an OpenAI API key
- For local mode: Hugging Face access to MedGemma 1.5 4B; a CUDA GPU is strongly recommended. Local generation and translation use MedGemma by default.

## Mode 1 — Local MedGemma (GitHub / portfolio / Colab)

This mode demonstrates local model loading and generation using `google/medgemma-1.5-4b-it`.

### 1. Accept model access

Open the [MedGemma 1.5 model card](https://huggingface.co/google/medgemma-1.5-4b-it), request/accept access, and read the [Google Health AI Developer Foundations terms](https://developers.google.com/health-ai-developer-foundations/medgemma). Create a Hugging Face read token and keep it private.

### 2. Install local dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-local.txt
cp .env.example .env
```

### 3. Configure `.env`

```env
INFERENCE_MODE=local
TRANSLATION_BACKEND=auto
HF_TOKEN=your_huggingface_read_token
LOCAL_MODEL_ID=google/medgemma-1.5-4b-it
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

The model weights are downloaded to `.model_cache` when the app starts. Do not commit the cache directory or the weights.

### 4. Start Qdrant and ingest the corpus

```bash
docker run -p 6333:6333 qdrant/qdrant
python -m backend.rag.ingestor
```

Local mode embeds with the configured PubMedBERT model and uses a local cross-encoder. It will create/use the `medimama_local` collection by default.

### 5. Run the API

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Readiness: `http://localhost:8000/health/ready`. A ready local generation backend reports `provider: Hugging Face Transformers` and `local_model_loaded: true`.

## Mode 2 — API-only (lightweight cloud demo)

This mode avoids all local ML model packages and weights. It uses OpenAI for generation, translation and dense embeddings. In API mode, the reranker and semantic sentence-transformer components are skipped; deterministic rules remain active.

### 1. Install the lightweight dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure `.env`

```env
INFERENCE_MODE=api
OPENAI_API_KEY=your_openai_api_key
QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_cloud_key
```

For a local test with Docker Compose, leave `QDRANT_URL` blank; Compose points the API to the Qdrant container.

### 3. Ingest with API embeddings

```bash
python -m backend.rag.ingestor
```

This creates the `medimama_api` collection by default using the OpenAI embedding dimension. Ingestion sends the corpus text to OpenAI embeddings; do not ingest content unless you are authorized to send it to the provider.

### 4. Run locally or in Docker

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

or:

```bash
docker compose up --build
```

For a cloud host, deploy the standard `Dockerfile`, configure `INFERENCE_MODE=api`, `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `ALLOWED_ORIGINS`, and the platform-provided `PORT`. Do not deploy a local Qdrant database or local ML weights to an ephemeral free instance.

## Switching between modes

1. Change `INFERENCE_MODE` in `.env`.
2. Install the dependency file for that mode.
3. Ensure the relevant API/Hugging Face credentials are configured.
4. Ingest the corpus again. The default collection names (`medimama_local` and `medimama_api`) keep their vector dimensions separate.

Do not point both modes at the same explicit `COLLECTION_NAME` unless you have recreated the collection with the selected embedding dimension.

## Google Colab demo (Mode 1)

The Colab launcher defaults to local mode. Install `requirements-demo.txt`, configure `HF_TOKEN` and `NGROK_AUTH_TOKEN`, then run `demo_colab.py`. An OpenAI key is not required in the default local configuration. Colab must provide a supported GPU with enough memory for MedGemma 1.5 4B. The first model download can take several minutes and uses persistent disk only if you mount Google Drive and point `LOCAL_MODEL_CACHE_DIR` there.

```python
!git clone https://github.com/Tshoopa/medimama.git
%cd medimama
!pip install -q -r requirements-demo.txt

import os
os.environ["INFERENCE_MODE"] = "local"
os.environ["HF_TOKEN"] = "your_huggingface_read_token"
os.environ["NGROK_AUTH_TOKEN"] = "your_ngrok_token"
os.environ["QDRANT_PATH"] = "./qdrant_storage"

!python -m backend.rag.ingestor
%run demo_colab.py
```

Use Colab secrets rather than hard-coding credentials in a notebook you publish.

## Frontend

The frontend is static and served by FastAPI from the same origin. For separate hosting, set `apiBase` in `frontend/config.js` to the backend origin and add that exact frontend origin to `ALLOWED_ORIGINS`.

## Testing

```bash
pytest
```

The test suite does not download MedGemma weights or make paid OpenAI requests. Run separate integration and clinical evaluation before relying on any external model.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `MedGemma` access denied | Hugging Face model access not accepted or token missing | Accept model terms and set `HF_TOKEN` |
| CUDA out of memory | GPU memory insufficient | Use a compatible GPU, reduce max new tokens, or select API mode |
| API mode says API key missing | `OPENAI_API_KEY` not configured | Set key in host secrets or `.env` |
| No citations | Qdrant collection empty or unavailable | Run ingestion and verify Qdrant connection |
| Vector dimension mismatch | Changed embedding backend/model without re-indexing | Use the mode-specific collection or re-ingest into a fresh collection |
| CORS error | Frontend origin not allowlisted | Add exact origin to `ALLOWED_ORIGINS` |
| Slow first response | Model download or sleeping free host | Warm the service or use an always-on host for demos |

