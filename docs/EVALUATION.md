# Evaluation

MediMama is evaluated with [**`rag-eval`**](https://github.com/Tshoopa/rag-eval), a standalone framework built for RAG and clinical decision-support systems.

Keeping evaluation outside the application keeps benchmarking reproducible and reusable, and prevents the system under test from sharing code with the thing measuring it.

```text
┌────────────────┐     ┌───────────────────────┐     ┌────────────────┐
│  MediMama API  │ ──▶ │ triage_results.json   │ ──▶ │    rag-eval    │
└────────────────┘     └───────────────────────┘     └───────┬────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │ Interactive HTML    │
                                                  │ Dashboard & Report  │
                                                  └─────────────────────┘
```

> [!NOTE]
> These are engineering test-set results. They are **not** clinical validation and do not establish safety or effectiveness on unseen real-world cases.

---

## Results — 92-Case Triage Suite

| Metric | Result |
| :--- | :---: |
| Evaluation cases | **92** |
| Exact-match accuracy | **69.6%** (64/92) |
| Clinical safety rate | **82.6%** (76/92 not under-triaged) |
| Critical-case recall (L1) | **95%** (19/20) |
| Under-triage | **17.4%** (16/92) |
| Over-triage | **13.0%** (12/92) |
| Maximum downgrade distance | **1 level** |
| Adversarial downgrade attempts blocked | ✅ |

**Exact-match accuracy** is the strictest possible metric: the predicted level must equal the expected level exactly. Adjacent-level agreement is not credited.

**Clinical safety rate** is the proportion of cases *not* assigned a less urgent level than expected. This is the metric that matters most in a triage context — over-triage costs time and money, under-triage costs safety.

---

## Confusion Matrix

| Expected ↓ / Predicted → | L1 | L2 | L3 | L4 | L5 |
| :--- | :-: | :-: | :-: | :-: | :-: |
| **L1** | **19** | 1 | 0 | 0 | 0 |
| **L2** | 0 | **15** | 3 | 0 | 0 |
| **L3** | 0 | 5 | **12** | 1 | 1 |
| **L4** | 0 | 0 | 0 | **4** | 11 |
| **L5** | 0 | 0 | 0 | 0 | **20** |

Reading the matrix, given that lower numbers mean greater urgency:

- **Diagonal** — exact match
- **Left of diagonal** — over-triage (more urgent than expected)
- **Right of diagonal** — under-triage (less urgent than expected)

Two structural properties are worth noting:

1. **No case was downgraded by more than one level.** The escalation-only merge and clamp bound how far a result can drift.
2. **All 20 expected-`L5` cases were classified as `L5`.** The system does not manufacture urgency out of benign presentations.

---

## Under-Triage Analysis

All 16 under-triage results, grouped:

| Pattern | Count | Assessment |
| :--- | :-: | :--- |
| `L4 → L5` on benign, self-limiting presentations | 11 | Label ambiguity |
| `L3 → L4` / `L3 → L5` | 4 | Under review |
| `L1 → L2` — croup with stridor at rest | 1 | **Actionable rule gap** |

### The 11 `L4 → L5` cases

These involved presentations such as warts, cradle cap, mild eczema, and growing pains — conditions where home care and a routine GP appointment are both defensible answers.

The evaluation dataset labels them `L4` (see a GP within 1–2 days). The rule engine returns `L5` (home care with monitoring). Standard triage guidance supports either reading, which means this cluster reflects a **labeling disagreement rather than a clinical risk**.

It is reported as under-triage anyway. Reclassifying inconvenient failures as "not really failures" is how evaluation stops being useful, so the raw number stands and the interpretation is documented separately.

### The one actionable case

Croup with **stridor at rest** was classified `L2` rather than `L1`. Stridor present while the child is calm and at rest indicates significant airway narrowing and warrants immediate emergency response, not urgent-care attendance.

This is a genuine gap in `triage_rules.json`: the current rule does not distinguish stridor at rest from stridor on exertion or when upset. It is the highest-priority item on the roadmap.

---

## Over-Triage Analysis

Twelve cases were assigned a more urgent level than expected — most commonly `L3 → L2`.

Over-triage is treated as the **acceptable failure direction**. Sending a child to an emergency department that turns out not to need one is a cost; keeping a child home who needed emergency care is a harm.

That said, over-triage is not free. A tool that escalates everything is not a triage tool, it is a referral, and caregivers stop trusting a system that always says "go to hospital". The `L3 → L2` cluster is tracked as a precision problem worth reducing.

---

## Adversarial Testing

The evaluation includes prompt-injection and downgrade-pressure cases where the input text attempts to influence the triage outcome directly — for example instructing the system that a presentation is not serious, or requesting a home-care answer for an emergency presentation.

All downgrade attempts were blocked. This is structural rather than fortunate: the safety net's output can only be used through `min()`, so even a fully compromised model response cannot lower the deterministic level.

---

## What Is Measured Separately

Triage correctness and answer quality are distinct dimensions and are **not** collapsed into a single number.

A case can receive the correct urgency level while retrieving the wrong topic. A wrist injury may be triaged correctly and then be shown supporting content about a pulled elbow. The triage was right; the retrieval was not.

| Dimension | Status |
| :--- | :--- |
| Triage correctness | ✅ Measured — 69.6% exact match |
| Under-triage severity | ✅ Measured — 17.4%, max 1 level |
| Over-triage severity | ✅ Measured — 13.0% |
| Critical-case recall | ✅ Measured — 95% |
| Adversarial resistance | ✅ Measured — all blocked |
| Retrieval relevance | ⏳ Planned |
| Context relevance | ⏳ Planned |
| Answer relevance | ⏳ Planned |
| Evidence grounding rate | ⏳ Planned |
| Citation quality | ⏳ Planned |

Integrating these retrieval and generation metrics into `rag-eval` is active work.

---

## Reproducing the Evaluation

With the API running and the corpus ingested:

```bash
# 1. Run the vignette suite against the API
python -m rag_eval.run \
  --api http://localhost:8000/ask \
  --cases data/eval/pediatric_vignettes.jsonl \
  --out triage_results.json

# 2. Generate metrics and the HTML dashboard
python -m rag_eval.report \
  --input triage_results.json \
  --out docs/triage_evaluation_report.html
```

Adjust the entry points to match the `rag-eval` CLI. Evaluation vignettes live at the path given by `EVAL_PATH` (default `data/eval/pediatric_vignettes.jsonl`).

🔗 **[View the interactive report](https://Tshoopa.github.io/medimama/triage_evaluation_report.html)**

---

## Reporting Notes

Metrics are stored as **raw ratios** (`0.174`) and converted to percentages only at the display layer (`17.4%`).

This is worth stating because an earlier version of the dashboard rendered stored ratios directly into a percentage field, displaying `0.174%` instead of `17.4%` — a two-orders-of-magnitude error that made the system look either flawless or broken depending on which metric was read. The reporting layer now distinguishes ratio from percentage explicitly.

An evaluation report can be wrong in exactly the same ways as the system it measures, and it deserves the same scrutiny.