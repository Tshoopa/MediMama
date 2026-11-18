content = '''# MediMama 🍼

**Safety-oriented pediatric triage prototype with grounded RAG.**

A multilingual research prototype with one codebase and two selectable inference modes:

- **Mode 1 — Local model:** **Qwen3-4B-Instruct** runs locally through Hugging Face Transformers. This is the mode to demonstrate local-model integration in a GitHub portfolio.
- **Mode 2 — API-only:** OpenAI handles answer generation, translation, and query embeddings. The runtime does not install or load PyTorch, Transformers, Sentence Transformers, a local LLM, or a local reranker. This is the lightweight mode intended for low-resource demo hosting.

Switch modes with one setting in `.env`:

```env
INFERENCE_MODE=local  # Mode 1: local Qwen3-4B
# INFERENCE_MODE=api  # Mode 2: API-only (default)
```

`FastAPI` · `Qdrant` · `Qwen3-4B-Instruct / OpenAI API` · `Hybrid RAG` · `English / فارسی / العربية`

> [!WARNING]
> **Research prototype — not a medical device.** Not clinically validated. Must not be used for diagnosis or as a substitute for professional medical care. In an emergency, contact local emergency services.

---

## Why Qwen3-4B instead of MedGemma?

The original design targeted **Google MedGemma 1.5 4B** (a medically pre-trained model from Google Health AI). MedGemma was replaced with **Qwen/Qwen3-4B-Instruct-2507** for practical reasons:

| Criterion | MedGemma 1.5 4B | Qwen3-4B-Instruct |
|---|---|---|
| Access | Gated — requires accepting Google Health AI terms on Hugging Face; reviewer approval can take days | Fully open, download immediately |
| Medical pre-training | Yes — trained on clinical text and medical Q&A | General instruction tuning; no special medical corpus |
| Multilingual (FA / AR) | Weak — primarily English | Strong multilingual support |
| Instruction following | Moderate | Very strong |
| Portfolio friction | High — visitors cannot reproduce the demo without approved access | Zero — anyone can clone and run |

For a research **prototype** where the LLM is one layer behind a deterministic triage engine and a grounding verifier, instruction-following quality and reproducibility matter more than domain pre-training. MedGemma remains a valid option: change `LOCAL_MODEL_ID` in `.env` to `google/medgemma-1.5-4b-it` and accept the Google Health AI license on Hugging Face to use it instead.

---

## Two runtime modes

| Capability | Mode 1: `local` | Mode 2: `api` |
|---|---|---|
| Answer-generation model | Qwen3-4B-Instruct, local | OpenAI API |
| Query/document embeddings | PubMedBERT SentenceTransformer, local | OpenAI `text-embedding-3-small` |
| Reranking | Local cross-encoder (`ms-marco-MiniLM-L-6-v2`) | Disabled; reciprocal-rank fusion is used |
| Semantic feature/concept models | Local SentenceTransformers | Disabled; deterministic feature/rule logic is used |
| Translation | Local Qwen3-4B by default (`TRANSLATION_BACKEND=auto`) | OpenAI API |
| Heavy local ML libraries | Required | Not installed |
| Intended use | GitHub portfolio, Colab, GPU workstation | Low-memory cloud demo |

**Note:** Local mode uses Qwen3 for both answer generation and translation by default and does not require an OpenAI API key unless you explicitly enable optional OpenAI triage assists or choose `TRANSLATION_BACKEND=openai`. API mode uses OpenAI for everything and has no local ML runtime dependencies.

### Mode 1 — Local Qwen3-4B

`Qwen/Qwen3-4B-Instruct-2507` is openly available on Hugging Face. A CUDA GPU is strongly recommended for reasonable latency. Install the local extras:

```bash
pip install -r requirements-local.txt
cp .env.example .env
```

Then set:

```env
INFERENCE_MODE=local
LOCAL_MODEL_ID=Qwen/Qwen3-4B-Instruct-2507
HF_TOKEN=<your_huggingface_token>
```

The model downloads to `LOCAL_MODEL_CACHE_DIR` on first use. Do not upload its weights to GitHub.

> **To use MedGemma instead:** set `LOCAL_MODEL_ID=google/medgemma-1.5-4b-it` and accept the Google Health AI license at https://huggingface.co/google/medgemma-1.5-4b-it. No other code changes are needed.

### Mode 2 — API-only (default)

This mode is intended for lightweight hosting:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Set:

```env
INFERENCE_MODE=api
OPENAI_API_KEY=<your_openai_key>
QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
QDRANT_API_KEY=<your_qdrant_key>
```

No local generative model, embedding model, semantic encoder, or cross-encoder is loaded. OpenAI embeddings have a different vector dimension from the local PubMedBERT vectors, so the project automatically uses a separate `medimama_api` Qdrant collection. **Run ingestion again after switching modes.**

---

## How it works

```
Parent question
    │
    ▼
[Translation — local Qwen3 or OpenAI]
    │
    ▼
[Safety & scope gate]
    │
    ▼
[Deterministic clinical feature extraction]
    │
    ▼
[Deterministic triage rules]
    │
    ├─── L1 / L2 ──► [Deterministic emergency response]
    │                         │
    └─── L3–L5 ──► [Hybrid RAG: dense + sparse + RRF]
                              │
                   ┌──────────┴──────────┐
              [Local Qwen3]         [OpenAI API]
                   └──────────┬──────────┘
                              ▼
                   [Grounding verification]
                              │
                              ▼
                   [Translated answer + citations]
```

**Safety invariant:** the LLM safety net may escalate a deterministic triage level, but it cannot downgrade it.

---

## Quick start — API-only Docker demo

```bash
git clone https://github.com/Tshoopa/medimama.git
cd medimama
cp .env.example .env
# Edit .env: set OPENAI_API_KEY and INFERENCE_MODE=api
docker compose up --build
```

Ingest the corpus once:

```bash
docker compose exec medimama python -m backend.rag.ingestor
```

Then open:

- Frontend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Readiness: http://localhost:8000/health/ready
- Qdrant dashboard: http://localhost:6333/dashboard

For public cloud hosting, use Qdrant Cloud and set `QDRANT_URL` / `QDRANT_API_KEY`; do not run an ephemeral local Qdrant volume on a free web instance.

---

## Running locally without Docker (Windows / Linux / Mac)

1. Start Qdrant:
   ```bash
   docker run -d -p 6333:6333 qdrant/qdrant
   ```

2. Install dependencies (API mode):
   ```bash
   pip install -r requirements.txt
   ```

3. Configure `.env` (minimum for API mode):
   ```env
   INFERENCE_MODE=api
   OPENAI_API_KEY=<your_key>
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   TRANSLATION_BACKEND=auto
   EMBEDDING_BACKEND=auto
   ```

4. Ingest data:
   ```bash
   python -m backend.rag.ingestor
   ```

5. Start the server:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

---

## API example

```bash
curl -X POST http://localhost:8000/ask \\
  -H "Content-Type: application/json" \\
  -d '{"symptoms":"My child has a barking cough and a harsh noise when breathing in.",
       "child_age_months":24,"language":"en"}'
```

`emergency_level` runs from `1` (resuscitation) to `5` (home care). `null` means the request was not clinically triaged (e.g. translation unavailable or question out of scope).

---

## Stack

| Layer | Implementation |
|---|---|
| API | FastAPI · Pydantic · Docker |
| Vector store | Qdrant (local server or cloud) |
| Local generation | Qwen3-4B-Instruct via Transformers |
| API generation | OpenAI Responses API |
| Local retrieval | PubMedBERT embeddings + cross-encoder |
| API retrieval | OpenAI `text-embedding-3-small` + dense/sparse RRF |
| Translation | Local Qwen3 (auto) or OpenAI API |
| Clinical logic | Deterministic feature extraction and triage rules |
| Optional LLM assists | OpenAI API, disabled by default |

---

## Testing

```bash
pytest
```

The tests cover language handling, translation contracts, mode isolation, privacy-safe audit logging, and the escalation-only safety-net invariant.

---

## Current limitations

- This project is not clinically validated. The existing 92-case evaluation set is an engineering benchmark, not evidence of clinical safety.
- Qwen3-4B-Instruct has not been evaluated on MediMama's pediatric scenarios; general instruction-tuning benchmarks do not certify this use case.
- In API mode, symptom text is transmitted to OpenAI for translation, embeddings, and answer generation. Use synthetic data for public demos and disclose this in production.
- The API has no authentication or rate limiting. Do not expose it as a public health service.
- Switching between local and API embeddings requires re-ingestion; the modes use separate Qdrant collection names by default.

See [Limitations](docs/LIMITATIONS.md) · [Architecture](docs/ARCHITECTURE.md) · [Running](docs/RUNNING.md) · [Configuration](docs/CONFIGURATION.md)
'''
from pathlib import Path
p = Path('/mnt/data/README.txt')
p.write_text(content, encoding='utf-8')
print(f'path={p} exists={p.is_file()} bytes={p.stat().st_size} lines={len(content.splitlines())}')
