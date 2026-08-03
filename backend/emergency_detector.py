# backend/emergency_detector.py

"""Facade over the triage pipeline, preserving the legacy tuple API:

    assess(symptoms_en, age_months, citations=None) -> (level, label_en, urgency_en)

It adapts whatever backend.triage.engine.assess() returns (RuleResult, debug
dict, int, or tuple) into that tuple for main.py.
"""

from typing import Any

from backend.triage.constants import LABELS
from backend.triage.engine import assess as _triage_assess


def _label_message_from_level(level: int) -> tuple[str, str]:
    try:
        title, message = LABELS[int(level)]
        return title, message
    except Exception:
        return "Medical advice", "Please consult a healthcare professional."


def assess(
    symptoms_en: str,
    age_months: int | None = None,
    citations=None,
) -> tuple[int, str, str]:
    result: Any = _triage_assess(symptoms_en, age_months=age_months, citations=citations)

    # Already a legacy tuple.
    if isinstance(result, tuple) and len(result) >= 3:
        return int(result[0]), str(result[1]), str(result[2])

    # Debug-dict form: {"result": RuleResult, ...}
    if isinstance(result, dict) and "result" in result:
        result = result["result"]

    # RuleResult / object with .level
    if hasattr(result, "level"):
        level = int(result.level)
        title = getattr(result, "title", None)
        message = getattr(result, "message", None)
        if title and message:
            return level, str(title), str(message)
        title, message = _label_message_from_level(level)
        return level, title, message

    # Raw int.
    if isinstance(result, int):
        title, message = _label_message_from_level(result)
        return int(result), title, message

    # Fail-safe default: treat unknown shapes as L3 (urgent same-day).
    title, message = _label_message_from_level(3)
    return 3, title, message