# Running MediMama

Three paths: **Docker Compose** (recommended), **local Python**, and **Google Colab** (demo only).

All three need the Meditron GGUF weights and an API key for the safety-net LLM.

---

## Prerequisites

| Requirement | Notes |
| :--- | :--- |
| Docker + Compose | For Option A |
| Python 3.11+ | For Option B |
| Disk space | ~6 GB — model weights plus dependencies |
| RAM | 8 GB minimum, 16 GB recommended |
| GPU | Optional. `LLM_N_GPU_LAYERS=0` forces CPU-only. |
| Safety-net API key | Any OpenAI-compatible provider |

---

## Option A — Docker Compose

Runs the API and Qdrant together.

### 1. Clone and download the model

```bash
git clone https://github.com/Tshoopa/medimama.git
cd medimama

mkdir -p models
wget -O models/meditron-7b.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/meditron-7B-GGUF/resolve/main/meditron-7b.Q4_K_M.gguf
```

The download is roughly 4 GB. The model is mounted as a volume rather than baked into the image, which keeps the image small and avoids redistributing model weights.

### 2. Configure

```bash
cp .env.example .env
```

Set your key:

```env
LLM_API_KEY=your_api_key_here
```

Compose sets `QDRANT_HOST=qdrant` automatically — do not change it in `.env` for this path.

### 3. Start

```bash
docker compose up --build
```

| Service | URL |
| :--- | :--- |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health/ready |
| Qdrant dashboard | http://localhost:6333/dashboard |

### 4. Ingest the corpus — first run only

```bash
docker compose exec api python -m backend.rag.ingestor
```

The ingester reports how many documents were loaded, skipped, and upserted. An unexpectedly high skip count usually means the corpus schema does not match what the loader expects.

### 5. Verify

```bash
curl http://localhost:8000/health/ready
```

```json
{ "status": "ready", "qdrant_available": true, "local_llm_loaded": true }
```

Then send a real query:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"symptoms": "My child has a mild runny nose and is eating normally.",
       "child_age_months": 30, "language": "en"}'
```

---

## Option B — Local Python

### 1. Environment

```bash
git clone https://github.com/Tshoopa/medimama.git
cd medimama

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Model weights

```bash
mkdir -p models
wget -O models/meditron-7b.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/meditron-7B-GGUF/resolve/main/meditron-7b.Q4_K_M.gguf
```

If you place the file elsewhere, set `MODEL_PATH` in `.env`.

**CPU-only machines:**

```env
LLM_N_GPU_LAYERS=0
```

Generation will be noticeably slower, but the `L1`/`L2` emergency fast path is unaffected because it never calls the local model.

### 3. Vector store

Either run the Qdrant server:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Or use the embedded on-disk store with no server at all:

```env
QDRANT_PATH=./qdrant_storage
```

Embedded mode is simpler for single-process development. The server is what Compose uses.

### 4. Ingest and start

```bash
python -m backend.rag.ingestor
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On the first request, startup logs should show:

```text
[init] Qdrant client ready.
[init] Loading local LLM: models/meditron-7b.Q4_K_M.gguf
[init] Local LLM loaded.
```

A `[init] Local LLM not loaded` line is not fatal — the API will serve deterministic answers with citations.

---

## Option C — Google Colab (Demo)

Useful when no local GPU is available. `demo_colab.py` starts the API and exposes it through an ngrok tunnel.

```python
!git clone https://github.com/Tshoopa/medimama.git
%cd medimama
!pip install -q -r requirements.txt pyngrok nest_asyncio

!mkdir -p models
!wget -q -O models/meditron-7b.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/meditron-7B-GGUF/resolve/main/meditron-7b.Q4_K_M.gguf

import os
os.environ["NGROK_AUTH_TOKEN"] = "your_ngrok_token"
os.environ["LLM_API_KEY"]       = "your_llm_api_key"
os.environ["QDRANT_PATH"]       = "./qdrant_storage"

!python -m backend.rag.ingestor
%run demo_colab.py
```

`QDRANT_PATH` is used because running a separate Qdrant service inside Colab is inconvenient.

The script prints a public URL. To use the web interface against it:

1. Set that URL as `apiBase` in `frontend/config.js`
2. Add the same URL to `ALLOWED_ORIGINS` — CORS is not a wildcard

```env
ALLOWED_ORIGINS=http://localhost:8000,https://your-tunnel.ngrok-free.app
```

> ngrok is a temporary development tunnel for demonstrations only. It is not part of the application architecture and is not used in the Docker path.

---

## Frontend

The frontend is static — no build step.

```bash
cd frontend
python -m http.server 8080
```

Open `http://localhost:8080`, and make sure `http://localhost:8080` is listed in `ALLOWED_ORIGINS`.

Set the API base URL in `frontend/config.js`:

```js
const apiBase = "http://localhost:8000";
```

---

## Testing

```bash
pytest                                     # full suite
pytest backend/tests/ -v                   # verbose
pytest backend/tests/test_safety_net.py    # safety-net contract only
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `[init] Qdrant unavailable` | Server not running, or wrong host | Start Qdrant, or set `QDRANT_PATH` |
| `[init] Local LLM not loaded` | Wrong `MODEL_PATH`, or out of memory | Check the path; try `LLM_N_GPU_LAYERS=0` |
| Answers arrive with no citations | Corpus not ingested | Run `python -m backend.rag.ingestor` |
| Retrieval returns irrelevant results | `SPARSE_DIM` changed after indexing | Re-ingest with the current value |
| Browser console shows a CORS error | Origin not allowlisted | Add it to `ALLOWED_ORIGINS` |
| Safety-net timeouts in the logs | Slow or unreachable provider | Raise `LLM_TIMEOUT_SECONDS`; check the key |
| Concurrent requests feel serialized | `llama.cpp` lock — expected | See [Architecture § Concurrency](ARCHITECTURE.md#concurrency-model) |
| CUDA out of memory | Retrieval models competing with `llama.cpp` | Keep `RETRIEVAL_DEVICE=cpu` and `RERANKER_DEVICE=cpu` |
| `422` on every request | `child_age_months` out of `0–216` | Check the payload |

### Re-ingesting after a config change

Changing `EMBEDDING_MODEL` or `SPARSE_DIM` invalidates the existing index. A `SPARSE_DIM` mismatch in particular fails **silently** — recall degrades with no error raised — so re-ingest after either change:

```bash
docker compose exec api python -m backend.rag.ingestor    # Docker
python -m backend.rag.ingestor                            # Local
```