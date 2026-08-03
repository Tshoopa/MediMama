# backend/evaluation.py

import json
from pathlib import Path

from backend.config import settings


def load_eval_set() -> list[dict]:
    path: Path = settings.eval_path
    if not path.exists():
        return []

    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_eval_example(
    question: str,
    answer: str,
    expected: str,
    sources: list[str],
    score: float,
) -> None:
    path = settings.eval_path
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "question": question,
        "answer": answer,
        "expected": expected,
        "sources": sources,
        "score": score,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")