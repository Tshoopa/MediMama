# ADR 003: Citations Must Pass a Relevance Threshold

## Status
Accepted

## Context
The RAG component retrieves medical documents to support and explain
triage answers. In early testing, the retriever returned documents
that were topically unrelated to the user's query.

For example, a query about a "red eye" returned documents about
"middle ear infection", "threadworms", and "febrile seizures".
These irrelevant citations were displayed alongside the answer.

An irrelevant citation is worse than no citation: it damages user
trust, makes the system look unreliable, and falsely implies that the
answer is grounded in evidence when it is not.

## Decision
Every retrieved document must pass a **relevance threshold** before it
can be shown as a citation.

The policy is:
- No relevant evidence found → show no citation.
- Relevant evidence found → answer is supported by that citation.
- Emergency fast-path → no RAG citation, with an explicit reason
  stating why (e.g., "This is an emergency; no source lookup needed").

Documents scoring below the relevance threshold are discarded and
never displayed.

## Consequences
### Positive
- Users only see citations that genuinely support the answer.
- Prevents "decorative" citations that look supportive but are not.
- Increases the credibility and honesty of the system.

### Negative
- Some answers will have no citation at all.
- This is acceptable and intentional: an honest "no supporting source"
  is better than a misleading one.

### Notes
- The exact threshold value is tuned empirically and documented in the
  configuration.
- Citation relevance is measured and reported in the evaluation harness.