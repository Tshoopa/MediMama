import json

# مواردی که قطعاً می‌خواهیم حذف شوند
REMOVE_FOCUSES = [
    "Electromagnetic Fields",
    "Anaplasmosis",
    "Anabolic Steroids",
    "Lead Poisoning",        # عمومی‌تر از آن است که فقط کودک باشد
    "Chronic Lymphocytic Leukemia"  # بیماری بزرگسالان
]

with open("strict_pediatric_qa.jsonl", "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f]

cleaned = [d for d in data if d["focus"] not in REMOVE_FOCUSES]

with open("pediatric_qa_final.jsonl", "w", encoding="utf-8") as f:
    for rec in cleaned:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"✅ {len(cleaned)} QA pairs after cleanup (removed {len(data)-len(cleaned)})")
