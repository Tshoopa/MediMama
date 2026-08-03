# backend/audit_logger.py

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.models import Citation


def _safe_model_dump(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


def _serialize_emergency_level(emergency_level: int | None) -> int | None:
    """Coerce an EmergencyLevel/IntEnum/int to a plain int. Stays None for
    out-of-scope refusals, which were never clinically triaged."""
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
    """Append one JSONL audit record. Must never crash the /ask endpoint, so
    every failure is swallowed and logged to stdout instead."""
    try:
        path: Path = settings.audit_log_path
        path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "language": language,
            "age_months": age_months,
            "emergency_level": _serialize_emergency_level(emergency_level),
            "citations": [_safe_model_dump(c) for c in (citations or [])],
            "answer": answer,
            "verified": bool(verified),
            "refusal": bool(refusal),
            "refusal_type": refusal_type,
        }

        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    except Exception as exc:
        print("[audit_logger] failed to write audit log:", repr(exc))