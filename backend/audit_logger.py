"""Privacy-conscious audit logging.

By default, raw parent messages, child ages, answer text, and evidence chunks are
not written to disk. Enable AUDIT_LOG_SENSITIVE_FIELDS only in a protected,
consented evaluation environment.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.models import Citation


def _safe_model_dump(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif hasattr(obj, "dict"):
        data = obj.dict()
    elif isinstance(obj, dict):
        data = obj
    else:
        data = {"value": str(obj)}

    if not settings.audit_log_sensitive_fields:
        data.pop("chunk", None)
        data.pop("text", None)
        data.pop("answer", None)
        data.pop("question", None)
    return data


def _serialize_emergency_level(emergency_level: int | None) -> int | None:
    if emergency_level is None:
        return None
    try:
        return int(emergency_level)
    except (TypeError, ValueError):
        return None


def log_query(
    question: str,
    language: str,
    age_months: int | None,
    emergency_level: int | None,
    citations: list[Citation] | None,
    answer: str,
    verified: bool,
    refusal: bool,
    refusal_type: str | None = None,
):
    """Append a metadata-only JSONL record unless sensitive logging is enabled."""
    try:
        path: Path = settings.audit_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "language": language,
            "question_char_count": len(question or ""),
            "answer_char_count": len(answer or ""),
            "emergency_level": _serialize_emergency_level(emergency_level),
            "citations": [_safe_model_dump(c) for c in (citations or [])],
            "verified": bool(verified),
            "refusal": bool(refusal),
            "refusal_type": refusal_type,
        }
        if settings.audit_log_sensitive_fields:
            record["question"] = question
            record["age_months"] = age_months
            record["answer"] = answer
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print("[audit_logger] failed to write audit log:", repr(exc))
