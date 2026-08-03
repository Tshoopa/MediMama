# backend/triage/evidence.py

from backend.triage.constants import (
    CRITICAL_TOPICS,
    EMERGENCY_TOPICS,
    EVIDENCE_DANGER_SIGNS,
    LABELS,
)
from backend.triage.features import RuleResult


def _result(level: int, reason: str) -> RuleResult:
    level = max(1, min(5, level))  # keep within valid triage range
    title, message = LABELS[level]
    return RuleResult(level=level, title=title, message=message, reason=reason)


def get_top_topics(citations, top_n: int = 3) -> set[str]:
    return {
        getattr(c, "topic", "")
        for c in (citations or [])[:top_n]
        if getattr(c, "topic", "")
    }


def scan_evidence_for_danger(citations, top_n: int = 6) -> bool:
    return any(
        kw in (getattr(c, "chunk", "") or "").lower()
        for c in (citations or [])[:top_n]
        for kw in EVIDENCE_DANGER_SIGNS
    )


def evaluate_rag_evidence(citations) -> RuleResult | None:
    """Safety backup: escalate when retrieved evidence hits a dangerous
    topic or contains danger-sign language."""
    top_topics = get_top_topics(citations)

    critical = top_topics & CRITICAL_TOPICS
    if critical:
        return _result(1, f"critical RAG topic matched: {critical}")

    if scan_evidence_for_danger(citations):
        return _result(2, "RAG evidence contains danger-sign language")

    emergency = top_topics & EMERGENCY_TOPICS
    if emergency:
        return _result(2, f"emergency RAG topic matched: {emergency}")

    return None