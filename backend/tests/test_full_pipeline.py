import json
import os
import sys
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.triage.engine import assess


def load_scenarios(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["test_cases", "scenarios", "cases", "tests", "data"]:
            if key in data and isinstance(data[key], list):
                print(f"✅ Loaded scenarios from key: '{key}'")
                return data[key]

        for key, value in data.items():
            if isinstance(value, list):
                print(f"✅ Loaded scenarios from key: '{key}'")
                return value

    return []


def extract_level_from_assess_result(result):
    """
    Handles both possible return formats from assess():
    1) RuleResult object  -> result.level
    2) tuple             -> (level, label, urgency)
    """
    if hasattr(result, "level"):
        return result.level

    if isinstance(result, tuple) and len(result) >= 1:
        return result[0]

    raise TypeError(
        f"Unsupported assess() return type: {type(result)} | value={result}"
    )


def run_pipeline_test(file_name: str = "holdout_test_6_50.json"):
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, file_name)

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    scenarios = load_scenarios(file_path)

    total = len(scenarios)
    passed = 0
    over_triage = 0
    dangerous = 0
    ignored = 0

    dangerous_cases = []
    over_triage_cases = []

    print("═══════════════════════════════════════════════════════════════════════════")
    print("🚀 FULL TRIAGE PIPELINE TEST (Defense-in-Depth Assessment)")
    print(f"📂 File: {file_name}  |  Total: {total} scenarios")
    print("═══════════════════════════════════════════════════════════════════════════")
    print(f"{'ID':<6} | {'Exp':<4} | {'Got':<4} | {'Status':<26} | Snippet")
    print("───────────────────────────────────────────────────────────────────────────")

    for item in scenarios:
        case_id = item.get("id", "N/A")
        input_text = item.get("input", "")
        expected = item.get("expected_level")
        age_months = item.get("child_age_months", 24)

        result = assess(input_text, age_months, citations=None)
        actual_level = extract_level_from_assess_result(result)

        snippet = (input_text[:45] + "...") if len(input_text) > 45 else input_text

        if expected is None:
            status = "⚪ IGNORE"
            ignored += 1

        elif actual_level == expected:
            status = "✅ PASS"
            passed += 1

        elif actual_level < expected:
            status = "⚠️ OVER-TRIAGE"
            over_triage += 1
            over_triage_cases.append({
                "id": case_id,
                "expected": expected,
                "actual": actual_level,
                "snippet": snippet,
            })

        else:
            status = "❌ UNDER-TRIAGE (DANGER)"
            dangerous += 1
            dangerous_cases.append({
                "id": case_id,
                "expected": expected,
                "actual": actual_level,
                "snippet": snippet,
                "input": input_text,
                "rationale": item.get("rationale", "")
            })

        exp_str = f"L{expected}" if expected is not None else "N/A"
        print(f"{case_id:<6} | {exp_str:<4} | L{actual_level:<3} | {status:<26} | {snippet}")

    counted = total - ignored
    accuracy = (passed / counted) * 100 if counted > 0 else 0
    safe_rate = ((passed + over_triage) / counted) * 100 if counted > 0 else 0

    print("═══════════════════════════════════════════════════════════════════════════")
    print(f"📊 Exact Match Accuracy  : {passed}/{counted} ({accuracy:.1f}%)")
    print(f"🛡️ Clinically Safe Rate  : {passed + over_triage}/{counted} ({safe_rate:.1f}%)")
    print(f"⚠️ Over-Triage Cases     : {over_triage}")
    print(f"🚨 Dangerous Under-Triage: {dangerous}  (این عدد باید صفر باشد!)")
    print("═══════════════════════════════════════════════════════════════════════════")

    if dangerous_cases:
        print("\n🔴 DANGEROUS UNDER-TRIAGE DETAILS")
        print("───────────────────────────────────────────────────────────────────────────")
        for c in dangerous_cases:
            print(f"[{c['id']}] Expected L{c['expected']} → Got L{c['actual']}")
            print(f"  Input     : {c['input']}")
            print(f"  Rationale : {c['rationale']}")
            print()

    if over_triage_cases:
        print("\n🟡 OVER-TRIAGE DETAILS")
        print("───────────────────────────────────────────────────────────────────────────")
        for c in over_triage_cases:
            print(f"[{c['id']}] Expected L{c['expected']} → Got L{c['actual']} | {c['snippet']}")

    print("\n*(Over-triage = محتاط بودن سیستم | Under-triage = خطای خطرناک)*")
    print("═══════════════════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run full triage pipeline test")
    parser.add_argument(
        "--file",
        type=str,
        default="holdout_test_6_50.json",
        help="JSON file name inside backend/tests/"
    )
    args = parser.parse_args()
    run_pipeline_test(file_name=args.file)