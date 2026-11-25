# API Reference

Base URL in local development: `http://localhost:8000`

Interactive documentation is available at `/docs` while the server is running.

---

## `POST /ask`

Triages a pediatric symptom description and returns caregiver-facing guidance.

### Request

```json
{
  "symptoms": "My 2-year-old has a barking cough and makes a harsh noise when breathing in.",
  "child_age_months": 24,
  "language": "en"
}
```

| Field | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `symptoms` | string | Non-empty | Free-text description in any supported language |
| `child_age_months` | integer | `0–216` | Age in months, birth to 18 years |
| `language` | string | `en` · `fa` · `ar` | Preferred response language |

**Language override.** If `symptoms` contains Persian or Arabic codepoints, the detected language takes precedence over `language`. A user typing Persian into a form left on English still receives a Persian response.

### Response

```json
{
  "answer": "I know this is worrying, but try to stay calm — you are taking exactly the right step by checking. Based on what you describe — **Croup with stridor** — your child should be seen by a doctor urgently. Please take your child to the nearest emergency department or urgent care centre now.",
  "emergency_level": 2,
  "emergency_label": "Emergency",
  "see_doctor_urgency": "Go to an emergency department now",
  "verified": true,
  "refusal": false,
  "refusal_type": null,
  "citations": []
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `answer` | string | Formatted caregiver guidance in the detected language |
| `emergency_level` | int \| null | `1` (most urgent) to `5` (home care). `null` means never clinically triaged. |
| `emergency_label` | string | Localized level label |
| `see_doctor_urgency` | string | Localized action guidance |
| `citations` | array | Supporting evidence; may be empty |
| `verified` | bool | `true` when the answer is deterministic or passed grounding verification |
| `refusal` | bool | `true` when the request was declined rather than triaged |
| `refusal_type` | string \| null | `safety_critical` · `medication_misuse` · `scope` |

---

## Triage Levels

| Level | Label | Meaning |
| :---: | :--- | :--- |
| `1` | Resuscitation | Life-threatening; immediate emergency response |
| `2` | Emergency | Emergency department now |
| `3` | Urgent | Same-day medical review |
| `4` | Semi-urgent | GP or clinic within 1–2 days |
| `5` | Non-urgent | Home care and routine monitoring |
| `null` | Not triaged | Request was refused before triage |

> Lower numbers indicate greater urgency. This matters when interpreting the API: `emergency_level: 1` is the most severe possible response, not the mildest.

---

## Citation Object

```json
{
  "source": "Royal Children's Hospital Melbourne",
  "chunk": "Mild croup is characterised by a barking cough without stridor at rest...",
  "score": -2.14,
  "topic": "Croup",
  "section": "Assessment",
  "content_type": "guideline",
  "source_type": "hospital_guideline",
  "source_priority": 10,
  "page_start": null,
  "page_end": null
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `source` | string | Source name |
| `chunk` | string | Retrieved passage, translated to the response language |
| `score` | float | Cross-encoder rerank score. Higher is better; values are commonly negative. |
| `topic` | string \| null | Clinical topic label |
| `section` | string \| null | Section within the source document |
| `content_type` | string \| null | `guideline` · `faq` · other corpus metadata |
| `source_type` | string \| null | Source category |
| `source_priority` | int \| null | Relative trust weight — `10` for guidelines, `5` for FAQ |
| `page_start` | int \| null | Reserved for paginated sources |
| `page_end` | int \| null | Reserved for paginated sources |

Citations are filtered by `MIN_RERANK_SCORE_FOR_DISPLAY` (default `-7.0`) and capped at `MAX_DISPLAY_CITATIONS` (default `3`).

**Negative scores are normal.** `ms-marco` cross-encoder outputs are unbounded logits, not similarities. A score of `-2.1` is a strong match; `-9.0` is not.

---

## When Citations Are Empty

An empty `citations` array is not an error. It occurs whenever:

| Situation | `citations` | `verified` |
| :--- | :---: | :---: |
| `L1`/`L2` emergency fast path | `[]` | `true` |
| Request refused | `[]` | `false` |
| No result cleared the score threshold | `[]` | `true` |
| Qdrant unavailable | `[]` | `true` |

`verified: true` with no citations means the answer came from the deterministic rule engine, which does not require retrieved evidence.

---

## Refusal Responses

A refused request is **not** assigned a low-urgency level. The schema keeps *"not triaged"* and *"triaged as non-urgent"* as distinct states.

### `safety_critical` → `emergency_level: 1`

```json
{
  "answer": "...",
  "emergency_level": 1,
  "emergency_label": "Emergency safety warning",
  "see_doctor_urgency": "Contact local emergency services or an appropriate local crisis support service immediately.",
  "verified": false,
  "refusal": true,
  "refusal_type": "safety_critical",
  "citations": []
}
```

Immediate danger was identified, so the response escalates rather than declining silently.

### `medication_misuse` → `emergency_level: null`

```json
{
  "emergency_level": null,
  "emergency_label": "Medication safety warning",
  "see_doctor_urgency": "Do not give the medication. Contact a pediatrician, pharmacist, poison information service, or emergency service for guidance.",
  "refusal": true,
  "refusal_type": "medication_misuse"
}
```

Ingestion was not established, so no clinical level is implied.

### `scope` → `emergency_level: null`

```json
{
  "emergency_level": null,
  "emergency_label": "Not clinically triaged",
  "see_doctor_urgency": "Please submit a question related to your child's health.",
  "refusal": true,
  "refusal_type": "scope"
}
```

The request was outside the pediatric health domain and never entered triage.

> **Client implementation note.** Treat `emergency_level: null` as "unknown", never as "safe". Rendering `null` as a green low-urgency badge would invert the intended meaning.

---

## Examples

### Persian input

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
        "symptoms": "دخترم دو ساله است و سرفه خشک و صدای خس خس دارد",
        "child_age_months": 24,
        "language": "fa"
      }'
```

The answer, label, urgency text, and citation passages are all returned in Persian.

### Low-urgency case with citations

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
        "symptoms": "My child has a mild runny nose and is eating and playing normally.",
        "child_age_months": 30,
        "language": "en"
      }'
```

`L3–L5` cases run the full retrieval and generation path, so citations are typically present.

---

## `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

---

## `GET /health/ready`

Readiness probe with dependency status.

```json
{
  "status": "ready",
  "inference_mode": "api",
  "qdrant_available": true,
  "generation": {
    "mode": "api",
    "provider": "OpenAI",
    "model": "gpt-6.1-sol",
    "ready": true,
    "local_model_loaded": false
  },
  "active_collection": "medimama_api",
  "embedding_backend": "openai"
}
```

`status` is `ready` only when Qdrant and the selected generation backend are configured. Otherwise it reports `degraded`; the API may still serve deterministic emergency responses and fallback answers. Local mode reports the MedGemma model and whether local weights loaded successfully.

---

## Error Behavior

The `/ask` endpoint is designed not to return `5xx` for dependency failures. Retrieval, generation, translation, and audit-logging errors degrade the answer instead:

| Failure | Result |
| :--- | :--- |
| Retrieval error | Deterministic answer, no citations |
| Generation error | Deterministic answer with citations |
| Grounding failure | Deterministic answer with citations |
| Input translation error | Request is not triaged; localized safe message returned |
| Audit-logging error | Response returned; error logged to stderr |
| Safety-checker error | `safety_critical` refusal |
| Rule-engine error | Falls back to `L3`, not `L5` |

Validation errors on the request body return the standard FastAPI `422` response.

---

## CORS

Allowed origins come from `ALLOWED_ORIGINS` (comma-separated). Wildcards are not used, so any new frontend host — including a tunnel URL used for a demo — must be added explicitly.

```env
ALLOWED_ORIGINS=http://localhost:8000,https://your-tunnel.ngrok-free.app
```

## Authentication

None. The API is unauthenticated and unrate-limited, and is intended for local and demonstration use only. See [Limitations](LIMITATIONS.md).
---

## Conversational API

The conversational API is additive. It does not replace or change the request
or response contract of `POST /ask`.

### `POST /conversations`

Create a new conversation and submit the initial concern.

```json
{
  "symptoms": "My child has a fever and diarrhea.",
  "child_age_months": 24,
  "language": "en",
  "additional_context": "The child is still playing."
}
```

`additional_context` is optional. Age remains expressed in months at the API
boundary, including for the redesigned UI, which converts years to months.

### `POST /conversations/{conversation_id}/turn`

Submit the answer to the currently active question. For a quick reply, `answer`
contains the question option's `value`; custom text is also accepted.

```json
{
  "question_id": "symptom_duration",
  "answer": "less_than_24_hours"
}
```

The `question_id` must match the active question. An expired/unknown session
returns `404`; a stale question or completed session returns `409`.

### `DELETE /conversations/{conversation_id}`

Delete the in-memory session. Returns `{ "deleted": true }` when successful.

### Conversational response

The response keeps the legacy clinical fields and adds conversation state plus the session language selected at creation.

```json
{
  "conversation_id": "uuid",
  "language": "en",
  "status": "needs_clarification",
  "answer": null,
  "follow_up_question": {
    "id": "symptom_duration",
    "text": "How long has the current symptom been present?",
    "input_type": "single_choice",
    "options": [
      {"value": "less_than_24_hours", "label": "Less than 24 hours"},
      {"value": "one_to_two_days", "label": "1–2 days"},
      {"value": "more_than_two_days", "label": "More than 2 days"},
      {"value": "unknown", "label": "I'm not sure"}
    ]
  },
  "emergency_level": null,
  "emergency_label": "Assessment pending",
  "citations": [],
  "see_doctor_urgency": "No triage level has been finalized...",
  "verified": false,
  "refusal": false,
  "refusal_type": null
}
```

Possible `status` values:

| Status | Meaning |
|---|---|
| `needs_clarification` | The backend returned one follow-up question. No final urgency level is assigned. |
| `completed` | The existing MediMama pipeline returned a completed assessment. |
| `urgent_escalation` | L1/L2 emergency escalation was returned immediately. |
| `refused` | The existing safety/scope gate refused the request before a normal assessment. |
| `assessment_incomplete` | Answers remained uncertain, conflicted, or clarification limits were reached. No level is assigned. |
| `error` | Translation or another preflight error prevented assessment. |

A `null` emergency level for `needs_clarification`, `assessment_incomplete`,
`refused`, or `error` is not a low-risk assessment. Clients must render these
states distinctly and never display them as green/self-care results.

### Clarification and safety behavior

The question bank currently collects symptom duration for selected reported
symptoms and hydration context for reported vomiting/diarrhea when that context
has not been mentioned. Question selection does not change triage thresholds
or make a diagnosis. The deterministic triage engine is run before a question
is considered. L1/L2 cases use the existing emergency fast path; L3 cases
proceed immediately to the existing same-day guidance path.

Unknown answers remain unknown. The feature-state adapter treats a feature as
`present` only when extracted, `absent` only when an existing explicit-negation
marker is present, and `unknown` otherwise. Conflicting explicit facts across
turns stop completion rather than silently overwriting one another.

Question templates are supplied directly in English, Persian, and Arabic; they
are not machine-translated at response time. The question bank and selection
conditions require review by a qualified pediatric clinician before real
clinical use.

### Session storage

Sessions use a bounded, in-memory, TTL-based store protected by a global index
lock and per-conversation turn locks. Defaults are 30 minutes, 500 sessions,
and 3 clarification turns. Override them with:

```env
CONVERSATION_TTL_SECONDS=1800
CONVERSATION_MAX_SESSIONS=500
CONVERSATION_MAX_CLARIFICATION_TURNS=3
```

This storage is for a single-process demo only. Sessions are lost on process
restart and are not shared across multiple workers or instances.
