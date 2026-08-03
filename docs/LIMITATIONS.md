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

**Retrieval quality is not yet measured.** Triage correctness is evaluated; retrieval relevance, context relevance, and citation quality are not. A case can be triaged correctly and shown an unrelated passage. These two dimensions are independent and only one of them currently has numbers.

**Grounding verification is heuristic.** It checks lexical and structural support against retrieved evidence. It does not perform semantic entailment, so a paraphrase that subtly changes clinical meaning can pass.

**Translation is unverified for clinical terminology.** Persian and Arabic output is not reviewed by a clinical translator. A term rendered imprecisely could change how urgent a caregiver believes the situation to be — arguably the highest-impact untested surface in the project.

**Local generation is serialized.** `llama.cpp` is not thread-safe, so `L3–L5` requests queue behind a single lock. `L1`/`L2` are unaffected because the fast path never calls the model. Horizontal scaling would require one model instance per worker or a dedicated inference server.

**No caching or streaming.** Identical questions are recomputed from scratch, and answers are returned only when complete.

**The safety net depends on a third party.** If the provider is slow or unavailable, the request falls back to the deterministic level after `LLM_TIMEOUT_SECONDS`. Safe, but a reduced safety net.

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
| Audit log storage | Unencrypted JSONL on local disk |
| Log retention | No policy; grows without bound |
| Data minimization | Symptom text and age are logged in full |
| Third-party data flow | Symptom text is sent to an external LLM provider |
| Regulatory compliance | No HIPAA, GDPR, or medical-device conformance work |
| Input abuse handling | Prompt-injection resistance tested; DoS and abuse are not |

The audit log is the sharpest issue: it stores child age together with free-text symptom descriptions, which in combination is sensitive health information. It exists to make triage decisions reviewable — a genuine safety requirement — but the current implementation has no encryption, access control, or retention limit.

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