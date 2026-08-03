import json
import os
import sys
from dataclasses import asdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.triage.normalizer import normalize_text
from backend.triage.feature_extractor import extract_clinical_features
from backend.triage.safety_rules import apply_deterministic_safety_rules
from backend.triage.semantic_backup import detect_semantic_red_flag, classify_non_emergency
from backend.emergency_detector import assess


FAILED_IDS = {"T012", "T075", "T083", "T101", "T103", "T104"}


def load_scenarios(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["test_cases", "scenarios", "cases", "tests", "data"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        for _, value in data.items():
            if isinstance(value, list):
                return value

    return []


def compact_true_features(features_dict):
    result = {}
    for k, v in features_dict.items():
        if k in {"raw_text", "text", "debug"}:
            continue
        if v is True:
            result[k] = v
        elif v not in [False, None, "", [], {}]:
            result[k] = v
    return result


def main():
    file_path = os.path.join(os.path.dirname(__file__), "test_scenarios.json")
    scenarios = load_scenarios(file_path)

    for item in scenarios:
        case_id = item.get("id")

        if case_id not in FAILED_IDS:
            continue

        input_text = item.get("input", "")
        expected = item.get("expected_level")
        age = item.get("child_age_months", 24)

        level, label, urgency = assess(input_text, age, citations=None)

        text = normalize_text(input_text)
        features = extract_clinical_features(input_text, text, age)

        rule_result = apply_deterministic_safety_rules(features)
        semantic_result = detect_semantic_red_flag(text)
        non_emergency_level = classify_non_emergency(text, features)

        print("\n" + "═" * 90)
        print(f"ID: {case_id}")
        print(f"Expected: L{expected} | Actual: L{level}")
        print(f"Age months: {age}")
        print(f"Input: {input_text}")
        print("-" * 90)
        print("Normalized:")
        print(text)
        print("-" * 90)
        print("Extracted features:")
        print(json.dumps(compact_true_features(asdict(features)), indent=2, ensure_ascii=False))
        print("-" * 90)
        print("Deterministic rule:")
        if rule_result:
            print(asdict(rule_result))
        else:
            print(None)
        print("-" * 90)
        print("Semantic backup:")
        if semantic_result:
            print(asdict(semantic_result))
        else:
            print(None)
        print("-" * 90)
        print(f"Non-emergency classifier level: L{non_emergency_level}")
        print("═" * 90)


if __name__ == "__main__":
    main()