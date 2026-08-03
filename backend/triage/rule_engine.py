# backend/triage/rule_engine.py

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.triage.constants import LABELS
from backend.triage.features import ClinicalFeatures, FeatureValue, RuleResult


RULES_PATH = Path(__file__).resolve().parent / "triage_rules.json"

# Operators that only make sense on a FeatureValue (severity/modifier aware).
SEVERITY_AWARE_OPS = {"severity_is", "severity_in", "modifier_is", "modifier_in"}


def _sample_features() -> ClinicalFeatures:
    return ClinicalFeatures(raw_text="", text="", age_months=None)


def _validate_atom(atom: Any, rule_id: str, sample: ClinicalFeatures) -> None:
    """Validate a single condition atom against the ClinicalFeatures schema,
    so a malformed rule fails loudly at load time rather than silently at
    runtime."""
    if isinstance(atom, str):
        if not hasattr(sample, atom):
            raise ValueError(
                f"[triage_rules.json] Rule '{rule_id}' references unknown feature '{atom}'."
            )
        return

    if isinstance(atom, dict):
        if "feature" in atom:
            feature = atom["feature"]
            op = atom.get("op")

            if not hasattr(sample, feature):
                raise ValueError(
                    f"[triage_rules.json] Rule '{rule_id}' references unknown feature '{feature}'."
                )

            actual = getattr(sample, feature)
            if op in SEVERITY_AWARE_OPS and not isinstance(actual, FeatureValue):
                raise TypeError(
                    f"[triage_rules.json] Rule '{rule_id}' uses '{op}' on '{feature}', which is "
                    f"{type(actual).__name__}, not FeatureValue. Convert the field to FeatureValue "
                    f"in features.py, or use a plain boolean operator (is_true/is_false)."
                )
            return

        for key in ("any", "all", "not"):
            if key in atom:
                items = atom[key]
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    _validate_atom(item, rule_id, sample)
                return

        raise ValueError(f"[triage_rules.json] Rule '{rule_id}' has invalid condition atom: {atom}")


def _validate_rules(rules: list[dict[str, Any]]) -> None:
    sample = _sample_features()
    for rule in rules:
        rule_id = rule.get("id", "<no id>")
        conditions = rule.get("conditions", {})
        for key in ("all", "any", "not"):
            for item in conditions.get(key, []):
                _validate_atom(item, rule_id, sample)


@lru_cache(maxsize=1)
def load_triage_rules() -> dict[str, Any]:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_rules(data.get("rules", []))
    return data


def _result(level: int, reason: str) -> RuleResult:
    level = max(1, min(5, level))  # keep within valid triage range
    title, message = LABELS[level]
    return RuleResult(level=level, title=title, message=message, reason=reason)


def _get_feature(f: ClinicalFeatures, name: str) -> Any:
    return getattr(f, name, None)


def _severity_of(actual: Any) -> str | None:
    return actual.severity if isinstance(actual, FeatureValue) else None


def _eval_comparison(f: ClinicalFeatures, condition: dict[str, Any]) -> bool:
    feature = condition.get("feature")
    op = condition.get("op")
    expected = condition.get("value")
    actual = _get_feature(f, feature)

    if op == "exists":
        return actual is not None
    if op == "is_true":
        return bool(actual) is True
    if op == "is_false":
        return bool(actual) is False

    if op == "severity_is":
        return bool(actual) and _severity_of(actual) == expected
    if op == "severity_in":
        return bool(actual) and _severity_of(actual) in (expected or [])

    if op == "modifier_is":
        if not isinstance(actual, FeatureValue):
            return False
        return actual.modifiers.get(expected.get("key")) == expected.get("equals")
    if op == "modifier_in":
        if not isinstance(actual, FeatureValue):
            return False
        return actual.modifiers.get(expected.get("key")) in expected.get("in", [])

    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in expected if expected is not None else False

    if actual is None:
        return False

    try:
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
    except TypeError:
        return False

    raise ValueError(f"Unsupported operator in triage rule: {op}")


def _eval_atom(f: ClinicalFeatures, atom: Any) -> bool:
    if isinstance(atom, str):
        return bool(_get_feature(f, atom))

    if isinstance(atom, dict):
        if "feature" in atom:
            return _eval_comparison(f, atom)
        if "any" in atom:
            return any(_eval_atom(f, x) for x in atom["any"])
        if "all" in atom:
            return all(_eval_atom(f, x) for x in atom["all"])
        if "not" in atom:
            items = atom["not"] if isinstance(atom["not"], list) else [atom["not"]]
            return not any(_eval_atom(f, x) for x in items)

    raise ValueError(f"Invalid condition atom: {atom}")


def _eval_conditions(f: ClinicalFeatures, conditions: dict[str, Any]) -> bool:
    all_items = conditions.get("all", [])
    any_items = conditions.get("any", [])
    not_items = conditions.get("not", [])

    if all_items and not all(_eval_atom(f, item) for item in all_items):
        return False
    if any_items and not any(_eval_atom(f, item) for item in any_items):
        return False
    if not_items and any(_eval_atom(f, item) for item in not_items):
        return False

    return True


def apply_json_triage_rules(f: ClinicalFeatures) -> RuleResult | None:
    """Evaluate all enabled rules; return the most urgent match (lowest level,
    then highest priority), or None if nothing matches."""
    rules = load_triage_rules().get("rules", [])

    matches = [
        rule
        for rule in rules
        if rule.get("enabled") is not False and _eval_conditions(f, rule.get("conditions", {}))
    ]
    if not matches:
        return None

    matches.sort(key=lambda r: (int(r["level"]), -int(r.get("priority", 0))))
    best = matches[0]
    return _result(int(best["level"]), best.get("reason", best.get("id", "matched triage rule")))