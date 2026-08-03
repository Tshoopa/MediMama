# Engineering Journey

The decisions in this project were mostly not designed up front. They were reactions to things that broke.

This document records the failures that shaped the architecture, because the reasoning behind a constraint is usually more useful than the constraint itself.

---

## 1. The evaluation report was wrong before the system was

An early dashboard reported a safety rate of `0.826%`.

The number looked catastrophic, so the obvious next step was to debug the triage engine. The triage engine was fine. Metrics were stored as raw ratios (`0.826`) and the reporting layer rendered them straight into a percentage field without conversion — a two-orders-of-magnitude error in the measurement tool, not the system.

The inverse mistake is more dangerous. Had the same bug run the other direction, an under-triage rate of `0.174` would have displayed as `0.174%` — a rate low enough to look like proof that everything worked.

**What changed.** Ratio and percentage are now distinct at the type level, and conversion happens only at the display layer.

**What it changed about my process.** The evaluation harness gets the same scrutiny as the system under test. A metric that looks unusually good is a bug report until proven otherwise.

---

## 2. Retrieval quietly got worse and nothing failed

Keyword recall degraded on cases that had previously worked. No exception, no failing test, no log line.

The sparse vectors were built in two places — once by the ingester and once by the retriever — and the hashing dimensionality had drifted between them. Every query still returned results. They were just the wrong results, ranked confidently.

**What changed.** Sparse-vector construction lives in exactly one module, `backend/rag/sparse_utils.py`, imported by both paths. The mismatch is no longer possible to express.

**The general lesson.** The failures worth engineering against are the ones that don't raise. A crash is a gift; it tells you where to look. This class of bug is why the roadmap includes a startup check that fails loudly on an index/config mismatch rather than trusting that the two paths agree.

---

## 3. "No breathing difficulty" became a respiratory red flag

The LLM feature extractor was better than regex at handling unusual phrasing, which is why it was added. It was also willing to extract `respiratory_distress: true` from the sentence *"no breathing difficulty, no wheeze"*.

The model recognized the clinical concept and dropped the negation — inverting the meaning of the sentence, in the direction of a false red flag.

**What changed.** LLM-proposed features must pass three gates before merging: grounding against the input text, schema validation, and explicit negation protection. A deterministically-detected negative cannot be overwritten by a model-proposed positive.

**The principle it produced.** The LLM is treated as an untrusted input source, not a component. Its output is validated the same way a request body is validated.

---

## 4. Choosing the merge operator instead of writing the check

The first version of the safety-net merge was a conditional: compare the two levels, and if the LLM proposed something less urgent, log a warning and keep the deterministic value.

It worked. It was also a rule that had to be *maintained* — one refactor away from being reordered, inverted, or accidentally bypassed by a new code path.

Because `L1` is the most urgent level, the same guarantee is expressible as arithmetic:

```python
final_level = min(deterministic_level, llm_level)
final_level = max(1, min(5, final_level))
```

There is no branch to get wrong. Downgrading is not prevented by a check; it is unrepresentable. The clamp does the same job for range validity — a corrupted rule file or a model returning `7` cannot produce an out-of-range level in the response.

**The general form.** When a safety property can be encoded in the shape of the code rather than enforced by a check on top of it, that is worth the refactor.

---

## 5. The defensive default was pointing the wrong way

The rule engine's exception handler returned `L5`.

The reasoning at the time was that `L5` is the safe, conservative answer — don't alarm anyone over an internal error. That reasoning was exactly backwards. `L5` means *"home care, monitor at home"*. A system that hits an unexpected error and responds by telling a caregiver to stay home has failed in the worst available direction.

**What changed.** The error fallback is `L3` — same-day medical review. Unknown state resolves toward *"have this looked at"*, not *"probably fine"*.

**Where else it applied.** The same audit found refusals defaulting to `L5`, so an out-of-scope question rendered as a low-urgency clinical answer. Refusals now return `emergency_level: null`, and *"not triaged"* is a distinct state from *"triaged as non-urgent"*.

---

## 6. Green for critical, red for home care

The frontend color-coded triage levels by iterating over the level list and mapping the palette in order. Level `1` got the first color, level `5` got the last.

The result: emergencies rendered green, home-care advice rendered red.

Every backend safety mechanism worked correctly on those cases. The correct answer reached the user and was then presented in a way that suggested the opposite.

**What changed.** Level-to-color mapping is explicit, and inverted-scale assumptions are treated as a UI hazard rather than a cosmetic issue.

**Why it stayed in this document.** It is the cheapest possible reminder that the safety boundary is not the API response — it is what the caregiver actually perceives. Backend correctness is necessary and not sufficient.

---

## 7. Query expansion made the system worse

Semantic query expansion is a standard RAG improvement, and it improved retrieval on ambiguous phrasing.

It also expanded a plain query of `fever` toward concepts including meningitis, pulling serious-condition guidance into the evidence context for routine presentations. In a general search product that is a mild precision problem. In a pediatric triage tool it means a worried parent asking about a mild fever receives meningitis content as supporting evidence.

**What changed.** `ENABLE_QUERY_EXPANSION` defaults to `false`. The implementation remains behind the flag, along with the reason it is off.

**The uncomfortable part.** Removing a working feature felt like losing progress. It was progress. A technique being correct in general does not make it correct in a specific risk context, and evaluation is what tells you which situation you are in.

---

## 8. Emergencies stopped depending on the model

Originally, every request ran the full pipeline: retrieve, rerank, generate, verify.

That meant a button-battery ingestion — one of the most time-critical presentations in pediatrics — waited on a local 7B model, could be affected by retrieval quality, and became unanswerable if the model failed to load.

**What changed.** `L1` and `L2` bypass retrieval and generation entirely and return deterministic guidance.

**Why it was a safety decision before a performance one.** The most dangerous cases are now the *most* predictable and the *least* dependent on infrastructure. Deleting the vector store and unloading the model still leaves emergency triage working correctly. The generative path serves only the cases where being slightly wrong is survivable.

---

## 9. A logging bug nearly caused a 500

Audit logging was inline in the request path. A malformed record could raise, and the exception propagated — converting a valid, correct medical answer into an HTTP 500 for the caregiver.

**What changed.** Audit logging is isolated. Failures go to stderr and the response is still returned.

**Where the same reasoning went.** Every dependency now degrades independently: Qdrant, local generation, grounding verification, the safety net, translation. Each has a defined fallback, so the answer gets worse instead of disappearing. A tool that returns a slightly less detailed answer is useful; a tool that returns an error page during a medical worry is not.

---

## What I'd Do Differently

**Build the evaluation harness first.** Every real problem in this list was found by measurement, and most were found later than they should have been. The order should have been: test set, harness, then features.

**Get labels reviewed before optimizing against them.** A meaningful share of the reported under-triage is label disagreement rather than system error, which makes the headline accuracy figure less informative than it looks. Locking down the ground truth is a prerequisite for tuning against it, not a follow-up task.

**Treat the interface as part of the safety system from day one.** The color-mapping bug bypassed every backend guarantee. Anything the caregiver sees is inside the trust boundary.

---

## The Underlying Position

The recurring pattern in every entry above is the same: a probabilistic component was useful, and was also willing to be confidently wrong in the direction that mattered.

The architecture that emerged from that is not "use an LLM carefully". It is:

> Establish urgency deterministically. Let probabilistic components **add** urgency and never remove it. Validate their output as untrusted input. Make the highest-risk paths the ones that depend on the least.

That constraint costs accuracy on ambiguous mid-urgency cases, and it makes over-triage the dominant failure mode. Both are accepted trade-offs, chosen rather than inherited.