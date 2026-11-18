# ADR 002: Deterministic Rules Make the Final Triage Decision, Not the LLM

## Status
Accepted

## Context
The system processes a patient case in layers:
1. An LLM extracts clinical features and an initial severity signal
   from free-text symptoms.
2. A deterministic rule engine evaluates these features against
   predefined triage rules.
3. A RAG component retrieves supporting medical documents and
   generates an explanation.

A key design question is: **who makes the final triage decision?**
The LLM is flexible and understands natural language well, but it is
non-deterministic and can hallucinate. Relying on it for the final
decision would make the system unpredictable and hard to audit.

## Decision
The LLM is used **only** to extract features and provide an initial
signal. The **final triage severity is decided by the deterministic
rule engine**, not by the LLM.

The processing order is:
LLM feature extraction → rule engine decision → RAG explanation.

## Consequences
### Positive
- The final decision is deterministic, reproducible, and auditable.
- The same input always produces the same triage level.
- Clinical logic lives in explicit, reviewable rules rather than in
  opaque model weights.

### Negative
- Rules must be manually written and maintained.
- The system may miss nuanced cases that the rules do not cover.

### Mitigation
- The LLM safety net can still escalate severity (but never override
  the rules to downgrade it — see ADR 001).
- Uncovered edge cases are tracked in the failure analysis report.