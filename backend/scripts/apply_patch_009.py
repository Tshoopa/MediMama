"""
فقط triage_rules.json و triage_semantic_concepts.json را پچ می‌کند.
هیچ import از کد پروژه ندارد.
"""
import json
from pathlib import Path

BASE = Path("/content/drive/MyDrive/medimama/backend/triage")

# ── triage_rules.json ──────────────────────────────────────────────
with open(BASE / "triage_rules.json", "r", encoding="utf-8") as f:
    rules_data = json.load(f)

rules = rules_data["rules"]
ids = {r["id"] for r in rules}

# اصلاح coin: level 4 -> 3
for r in rules:
    if r["id"] == "swallowed_non_sharp_object_advice":
        r["level"] = 3

NEW_RULES = [
    {"id":"anaphylaxis_face_swelling_breathing","category":"allergy","level":1,"priority":97,
     "conditions":{"all":["face_lip_tongue_swelling"],"any":["breathing_difficulty","not_breathing","wheeze","throat_swelling","stridor_or_noisy_breathing"]},
     "reason":"face/lip/tongue swelling + breathing difficulty = anaphylaxis"},
    {"id":"suicidal_ideation_or_self_harm","category":"mental_health","level":1,"priority":100,
     "conditions":{"any":["suicidal_ideation","self_harm"]},
     "reason":"suicidal ideation or self-harm = immediate emergency"},
    {"id":"loss_of_consciousness","category":"head_injury","level":1,"priority":91,
     "conditions":{"any":["loss_of_consciousness"]},
     "reason":"loss of consciousness = emergency"},
    {"id":"diabetic_ketoacidosis","category":"endocrine","level":1,"priority":95,
     "conditions":{"all":["known_diabetic"],"any":["fruity_breath","fast_breathing","breathing_difficulty","vomiting"]},
     "reason":"diabetic + DKA signs = emergency"},
    {"id":"umbilical_infection_omphalitis","category":"neonatal_infection","level":2,"priority":86,
     "conditions":{"any":["umbilical_redness_or_discharge"]},
     "reason":"umbilical redness/discharge = possible omphalitis"},
]

for nr in NEW_RULES:
    if nr["id"] not in ids:
        rules.append(nr)
        print(f"✅ added: {nr['id']} (L{nr['level']})")

with open(BASE / "triage_rules.json", "w", encoding="utf-8") as f:
    json.dump(rules_data, f, ensure_ascii=False, indent=2)
print("✅ triage_rules.json saved")

# ── triage_semantic_concepts.json ──────────────────────────────────
with open(BASE / "triage_semantic_concepts.json", "r", encoding="utf-8") as f:
    sc = json.load(f)

concepts = sc["concepts"]
cids = {c["id"] for c in concepts}

# تقویت stiff_neck
for c in concepts:
    if c["id"] == "stiff_neck":
        for e in ["her neck feels stiff","neck feels really stiff","cannot bend the neck","neck stiff and painful"]:
            if e not in c["exemplars"]: c["exemplars"].append(e)
        c["threshold"] = 0.56

# تقویت hot_swollen_joint
for c in concepts:
    if c["id"] == "hot_swollen_joint":
        for e in ["warm to touch and won't walk","leg is warm to the touch","won't put weight on the warm leg"]:
            if e not in c["exemplars"]: c["exemplars"].append(e)

# اضافه کردن concept های جدید
if "appendicitis_signs" not in cids:
    concepts.append({"id":"appendicitis_signs","set_features":["appendicitis_signs","severe_abdominal_pain"],"threshold":0.57,"medical_signal":True,
        "exemplars":["pain in the lower right belly getting worse","pain moved from belly button to lower right","right lower abdominal pain with fever","belly pain on the right side getting worse for hours"],
        "negative_patterns":["mild stomach ache","better after gas"]})
    print("✅ added: appendicitis_signs concept")

if "seizure_event" not in cids:
    concepts.append({"id":"seizure_event","set_features":["seizure"],"threshold":0.58,"medical_signal":True,
        "exemplars":["body was shaking uncontrollably","had a seizure","started convulsing with arms jerking","eyes rolled back and body shook","whole body shaking fit"],
        "negative_patterns":[]})
    print("✅ added: seizure_event concept")

with open(BASE / "triage_semantic_concepts.json", "w", encoding="utf-8") as f:
    json.dump(sc, f, ensure_ascii=False, indent=2)
print("✅ triage_semantic_concepts.json saved")
print("\n🎉 پچ 009 کامل شد. Runtime را ری‌استارت کن، سپس تست بزن.")