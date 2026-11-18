# ADR 001: RAG Cannot Downgrade Triage Severity

## Status
Accepted

## Context
The system uses a deterministic rule engine and an LLM safety net to
assign a triage severity level (e.g., emergency, urgent, routine).
A separate RAG component retrieves medical documents to explain the
decision to the user.

However, retrieved documents may be irrelevant, incomplete, or
misleading. If the RAG output were allowed to influence the final
severity, it could accidentally lower a critical case to a non-urgent
one. In a pediatric triage context, this "dangerous under-triage"
could delay emergency care.

## Decision
The RAG component may **only explain** the triage decision.
It **cannot reduce** the severity level chosen by the deterministic
rule engine or the safety net.

Severity can only be maintained or escalated — never downgraded — by
any downstream component.

## Consequences
### Positive
- Eliminates the risk of dangerous under-triage caused by retrieval
  errors or hallucinated explanations.
- Keeps the safety-critical decision path deterministic and auditable.

### Negative
- May increase over-triage (some mild cases flagged as more serious).
- This trade-off is intentional: over-triage is safer than
  under-triage in a medical context.

### Monitoring
- Over-triage rate is tracked in the evaluation harness to ensure it
  stays within an acceptable range.