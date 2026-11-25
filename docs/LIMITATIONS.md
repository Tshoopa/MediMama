# Limitations and Roadmap

> [!WARNING]
> MediMama is a research and portfolio prototype. It is **not a medical device**, has not been clinically validated, and must not be used for real clinical decision-making.

This document is deliberately specific. A prototype that lists no limitations has either not been tested or is not being described honestly.

---

## Clinical Limitations

**Not clinically validated.** No trial, no expert panel review, no measurement against real patient outcomes. The 92-case evaluation is an engineering test set, not evidence of safety or effectiveness.

**The test set is small.** 92 cases cannot represent the range of pediatric presentations, comorbidities, ages, and phrasings a real system would encounter. Reported metrics describe performance on this suite and do not predict performance on unseen cases.

**Labels are not authoritative.** Expected levels in the evaluation set were assigned during development, not ratified by a clinician. The 11 `L4 → L5` disagreements documented in [Evaluation](EVALUATION.md#under-triage-analysis) are as likely to be label problems as system problems, and there is currently no way to settle that from inside the project.

**One known rule gap.** Croup with stridor **at rest** is currently triaged `L2` instead of `L1`. Stridor while a child is calm indicates significant airway narrowing and warrants immediate emergency response. Tracked as P0 below.

**No diagnosis, no differential.** The system assigns urgency and returns supporting guidance. It does not identify a condition, rank possible causes, or recommend treatment.

**Single-session only.** There is no memory, no follow-up, and no deterioration monitoring. A child who worsens two hours later is a new, unrelated request.

**The corpus is narrow and regionally specific.** Clinical content derives from Royal Children's Hospital Melbourne guidelines. Care pathways, service names, and escalation thresholds differ by country, so guidance may not match local practice.

**Age coverage is uneven.** The API accepts `0–216` months, but rules are tuned toward common presentations. Neonates and adolescents are the least well covered, and neonates are the group where the cost of an error is highest.

---

## Technical Limitations

**Two runtime modes have different retrieval behavior.** Local mode uses PubMedBERT embeddings and a cross-encoder; API mode uses OpenAI embeddings and RRF without a local reranker. The vector collections are therefore separate and must be ingested independently. API mode also skips local semantic concept and semantic feature models, leaving deterministic features/rules as the triage basis unless optional OpenAI assists are explicitly enabled.

**Local mode can run without an OpenAI API key.** MedGemma handles both answer generation and translation by default, and local encoders handle RAG/semantic helpers. Initial model downloads still require Hugging Face access, and any configured cloud Qdrant instance or explicitly enabled OpenAI triage assist remains an external dependency.


**Retrieval quality is not yet measured.** Triage correctness is evaluated; retrieval relevance, context relevance, and citation quality are not. A case can be triaged correctly and shown an unrelated passage. These two dimensions are independent and only one of them currently has numbers.

**Grounding verification is heuristic.** It checks lexical and structural support against retrieved evidence. It does not perform semantic entailment, so a paraphrase that subtly changes clinical meaning can pass.

**Translation is unverified for clinical terminology.** Persian and Arabic translation now uses explicit source languages and a clinical-preservation prompt, but it has not been reviewed by clinical translators. A term or negation rendered imprecisely could change how urgent a caregiver believes the situation to be.

**Local generation is serialized.** MedGemma generation uses one in-process lock, so concurrent `L3–L5` requests queue behind one local model instance. `L1`/`L2` are unaffected because the emergency fast path never calls the generator. API mode delegates generation to OpenAI, but remains subject to provider latency, quotas and network failures.

**No caching or streaming.** Identical questions are recomputed from scratch, and answers are returned only when complete.

**Optional LLM triage assists depend on a third party.** They are disabled by default. If explicitly enabled and the provider is slow or unavailable, the assist fails open and deterministic triage remains authoritative.

**A silent-failure mode exists.** Changing `SPARSE_DIM` or `EMBEDDING_MODEL` without re-ingesting degrades recall with no error raised. Sparse-vector construction is centralized in one shared module to make this unlikely, but nothing currently detects the mismatch at startup.

---

## Security and Privacy Limitations

> These are the limitations that would block any real deployment, regardless of clinical performance.

| Area | Current state |
| :--- | :--- |
| Authentication | None |
| Authorization | None |
| Rate limiting | None |
| Transport security | HTTP in local development |
| Audit log storage | JSONL on local disk; raw text disabled by default |
| Log retention | No policy; grows without bound |
| Data minimization | Character counts and operational metadata by default; raw question/age/answer require explicit opt-in |
| Third-party data flow | Symptom text is sent to an external LLM provider |
| Regulatory compliance | No HIPAA, GDPR, or medical-device conformance work |
| Input abuse handling | Prompt-injection resistance tested; DoS and abuse are not |

Audit logging now omits raw question text, child age, answer text and evidence chunks by default. Setting `AUDIT_LOG_SENSITIVE_FIELDS=true` restores those fields for a protected, consented evaluation environment; do not enable it for public demos. Log encryption, access controls and retention limits are still not implemented.

CORS is restricted to an explicit allowlist (`ALLOWED_ORIGINS`) rather than a wildcard, which is the one hardening measure that *is* in place.

---

## Roadmap

### P0 — Safety correctness

- [ ] Add a distinct rule for **stridor at rest** and route it to `L1`
- [ ] Add a startup check that fails loudly on an index/config mismatch instead of degrading silently
- [ ] Expand adversarial coverage for indirect downgrade pressure

### P1 — Evaluation depth

- [ ] Integrate retrieval-relevance and context-relevance metrics into [`rag-eval`](https://github.com/Tshoopa/rag-eval)
- [ ] Measure grounding rate and citation precision as first-class metrics
- [ ] Grow the vignette suite beyond 92 cases, with wider neonatal and adolescent coverage
- [ ] Have a clinician review the disputed `L4`/`L5` labels so the accuracy figure means something stable

### P2 — Engineering hardening

- [ ] API-key authentication and per-client rate limiting
- [ ] Audit-log encryption at rest plus a retention policy
- [ ] Structured logging with request-scoped correlation IDs
- [ ] Replace the in-process lock with a dedicated inference service to allow horizontal scaling
- [ ] Response caching for repeated low-urgency queries
- [ ] Clinical review of Persian and Arabic terminology

### Explicitly out of scope

Deliberately **not** planned, because they would add surface area without addressing anything above:

- Additional agents or a third LLM in the pipeline
- A second vector database
- A general-purpose chat interface
- Adult or non-pediatric triage
- Prescribing or dosage calculation

---

## What Real Clinical Use Would Require

Listed so the gap between "working prototype" and "deployable system" is not left ambiguous:

1. Clinical governance — a named responsible clinician and a documented review process
2. Prospective validation against real presentations with recorded outcomes
3. Regulatory assessment under the applicable medical-device software framework
4. A formal risk analysis and hazard log
5. Human-in-the-loop review for every emergency-level output
6. A privacy and security posture appropriate to health data
7. Localization to the target region's care pathways
8. Post-deployment monitoring with a defined incident process

None of these exist. That is the honest distance between this repository and a clinical tool.

---

## Disclaimer

MediMama is a research prototype and **not a medical device**. It does not provide medical advice, diagnosis, or treatment, and must not replace assessment by a qualified healthcare professional. Outputs may be incomplete, incorrect, or inappropriate for an individual child.

If a child may be seriously ill, contact local emergency services immediately.
---

## Conversational clarification limitations

The current clarification engine is deliberately small and deterministic. It
contains language-specific, prewritten templates for symptom duration and hydration context
in selected cases; it is not a complete pediatric history-taking system and
does not represent comprehensive clinical guidance. A qualified pediatric
clinician must review every template and selection condition before real-world
clinical use.

The engine does not assign urgency. It runs only after the existing safety gate
and triage assessment, and it never delays L1/L2 emergency escalation or L3
same-day review. It does not change clinical rules, thresholds, or RAG behavior.

The session store is in-memory, bounded, and TTL-based. It is suitable only for
a single-process demo, loses all sessions on restart, and cannot coordinate
multiple workers or service instances. The unauthenticated API also does not
provide identity-bound session access; do not use it for real patient data.

When a user answers "I'm not sure", the unknown is retained and the system may
finish in `assessment_incomplete` rather than treating it as a negative finding.
Explicit present-versus-negated facts across turns are treated as conflicts;
the prototype stops rather than deciding which report is current. This is a
conservative engineering behavior, not a validated clinical conflict-resolution
policy.
