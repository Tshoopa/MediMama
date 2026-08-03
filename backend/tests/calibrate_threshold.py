# backend/tests/calibrate_threshold.py
import os
import sys
import json

# ─────────────────────────────────────────────────────────────
# 🛠️ تنظیم مسیر (برای اجرا در گوگل کولب و ترمینال)
# ─────────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.emergency_detector import _detect_semantic_concepts

json_path = os.path.join(current_dir, "test_scenarios.json")

try:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"❌ Error: Could not find test_scenarios.json at {json_path}")
    sys.exit(1)

print("\n" + "═"*75)
print("🔴 SECTION 1: POSITIVE CASES (Must detect the correct concept)")
print("═"*75)
print(f"{'ID':<6} {'Expected Concept':<22} {'Detected Concept':<22} {'Score':<8} {'Status'}")
print("─" * 75)

passed_pos = 0
total_pos = 0

for s in data["scenarios"]:
    if s["expected_concept"] is None:
        continue
        
    total_pos += 1
    concepts = _detect_semantic_concepts(s["input"])
    
    if concepts:
        top_name, top_score = concepts[0]
        match = top_name == s["expected_concept"]
        if match:
            status = "✅ PASS"
            passed_pos += 1
        else:
            status = f"❌ MISMATCH (Expected {s['expected_concept']})"
        print(f"{s['id']:<6} {s['expected_concept']:<22} {top_name:<22} {top_score:<8} {status}")
    else:
        print(f"{s['id']:<6} {s['expected_concept']:<22} {'NOT DETECTED':<22} {'0.00':<8} ❌ FAIL")

print("\n" + "═"*75)
print("🟢 SECTION 2: NEGATIVE CASES (Should NOT trigger high scores)")
print("═"*75)
print(f"{'ID':<6} {'Input Snippet':<35} {'Top Detected (If Any)':<22} {'Score':<8}")
print("─" * 75)

total_neg = 0
false_positives = 0
# حد آستانه تست برای بررسی خطای False Positive
WARNING_THRESHOLD = 0.40 

for s in data["scenarios"]:
    if s["expected_concept"] is not None:
        continue
        
    total_neg += 1
    concepts = _detect_semantic_concepts(s["input"])
    snippet = s['input'][:32] + "..." if len(s['input']) > 32 else s['input']
    
    if concepts:
        top_name, top_score = concepts[0]
        if top_score >= WARNING_THRESHOLD:
            status = "⚠️ FALSE POSITIVE RISK"
            false_positives += 1
        else:
            status = "✅ SAFE (Score low)"
        print(f"{s['id']:<6} {snippet:<35} {top_name:<22} {top_score:<8} {status}")
    else:
        print(f"{s['id']:<6} {snippet:<35} {'NONE':<22} {'0.00':<8} ✅ SAFE")

print("\n" + "═"*75)
print(f"📊 Positive Accuracy: {passed_pos}/{total_pos} ({(passed_pos/total_pos*100) if total_pos else 0:.1f}%)")
print(f"📉 Negative False Positives (>= {WARNING_THRESHOLD}): {false_positives}/{total_neg}")
print("═"*75)