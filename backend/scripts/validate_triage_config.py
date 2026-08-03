# backend/scripts/validate_triage_config.py

import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------
# Make this script runnable both ways:
#   python backend/scripts/validate_triage_config.py
#   python -m backend.scripts.validate_triage_config
#
# File location:
#   backend/scripts/validate_triage_config.py
#
# Project root:
#   parents[2]
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.triage.features import ClinicalFeatures  # noqa: E402


TRIAGE_DIR = PROJECT_ROOT / "backend" / "triage"

PATTERNS_PATH = TRIAGE_DIR / "deterministic_feature_patterns.json"
RULES_PATH = TRIAGE_DIR / "triage_rules.json"


FEATURE_ALIASES = {
    "photophobia": "light_sensitivity"
}


ALLOWED_TOP_LEVEL_PATTERN_KEYS = {
    "version",
    "description",
    "tokens",
    "count_terms",
    "negation_overrides",
    "boolean_patterns",
    "value_patterns",
    "derived_patterns",
    "medical_floor_tokens"
}


def canonical_field(field: str) -> str:
    return FEATURE_ALIASES.get(field, field)


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def feature_sample() -> ClinicalFeatures:
    return ClinicalFeatures(raw_text="", text="", age_months=None)


def validate_patterns() -> list[str]:
    errors: list[str] = []

    data = load_json(PATTERNS_PATH)
    sample = feature_sample()

    unknown_top = set(data.keys()) - ALLOWED_TOP_LEVEL_PATTERN_KEYS

    for key in sorted(unknown_top):
        errors.append(
            f"{PATTERNS_PATH}: top-level key '{key}' is not allowed. "
            f"Clinical feature patterns must be inside boolean_patterns."
        )

    boolean_patterns = data.get("boolean_patterns", {})

    if not isinstance(boolean_patterns, dict):
        errors.append(f"{PATTERNS_PATH}: boolean_patterns must be an object/dict")
        return errors

    for field in boolean_patterns:
        target = canonical_field(field)

        if not hasattr(sample, target):
            errors.append(
                f"{PATTERNS_PATH}: boolean_patterns field '{field}' "
                f"maps to unknown ClinicalFeatures field '{target}'"
            )
            continue

        if not isinstance(getattr(sample, target), bool):
            errors.append(
                f"{PATTERNS_PATH}: boolean_patterns field '{field}' "
                f"maps to non-bool ClinicalFeatures field '{target}'"
            )

    negation_overrides = data.get("negation_overrides", {})

    if not isinstance(negation_overrides, dict):
        errors.append(f"{PATTERNS_PATH}: negation_overrides must be an object/dict")
        return errors

    for field in negation_overrides:
        target = canonical_field(field)

        if not hasattr(sample, target):
            errors.append(
                f"{PATTERNS_PATH}: negation_overrides field '{field}' "
                f"maps to unknown ClinicalFeatures field '{target}'"
            )
            continue

        if not isinstance(getattr(sample, target), bool):
            errors.append(
                f"{PATTERNS_PATH}: negation_overrides field '{field}' "
                f"maps to non-bool ClinicalFeatures field '{target}'"
            )

    value_patterns = data.get("value_patterns", [])

    if not isinstance(value_patterns, list):
        errors.append(f"{PATTERNS_PATH}: value_patterns must be a list")
        return errors

    for idx, item in enumerate(value_patterns):
        if not isinstance(item, dict):
            errors.append(f"{PATTERNS_PATH}: value_patterns[{idx}] must be an object/dict")
            continue

        field = item.get("field")

        if not field:
            errors.append(f"{PATTERNS_PATH}: value_patterns[{idx}] missing field")
            continue

        if not hasattr(sample, field):
            errors.append(
                f"{PATTERNS_PATH}: value_patterns field '{field}' "
                f"is unknown in ClinicalFeatures"
            )

    return errors


def extract_rule_fields(node: Any) -> list[str]:
    fields: list[str] = []

    if isinstance(node, str):
        fields.append(node)

    elif isinstance(node, list):
        for item in node:
            fields.extend(extract_rule_fields(item))

    elif isinstance(node, dict):
        if "feature" in node:
            feature = node["feature"]
            if isinstance(feature, str):
                fields.append(feature)

        for key in ("all", "any", "not"):
            if key in node:
                fields.extend(extract_rule_fields(node[key]))

    return fields


def validate_rules() -> list[str]:
    errors: list[str] = []

    data = load_json(RULES_PATH)
    sample = feature_sample()

    rules = data.get("rules", [])

    if not isinstance(rules, list):
        errors.append(f"{RULES_PATH}: rules must be a list")
        return errors

    for rule in rules:
        if not isinstance(rule, dict):
            errors.append(f"{RULES_PATH}: rule item must be an object/dict")
            continue

        rule_id = rule.get("id", "<unknown>")
        conditions = rule.get("conditions", {})

        for field in extract_rule_fields(conditions):
            target = canonical_field(field)

            if not hasattr(sample, target):
                errors.append(
                    f"{RULES_PATH}: rule '{rule_id}' references unknown "
                    f"ClinicalFeatures field '{field}' -> '{target}'"
                )

    return errors


def main() -> None:
    errors: list[str] = []

    errors.extend(validate_patterns())
    errors.extend(validate_rules())

    if errors:
        print("❌ TRIAGE CONFIG VALIDATION FAILED")
        print()

        for error in errors:
            print(" - " + error)

        raise SystemExit(1)

    print("✅ Triage config validation passed.")


if __name__ == "__main__":
    main()