# backend/scripts/apply_undertriage_patch_002.py

import json
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
TRIAGE_DIR = BACKEND_DIR / "triage"

DETERMINISTIC_PATH = TRIAGE_DIR / "deterministic_feature_patterns.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_unique(target: list[str], items: list[str]) -> None:
    for item in items:
        if item not in target:
            target.append(item)


def ensure_boolean_patterns(data: dict[str, Any], field: str, patterns: list[str]) -> None:
    data.setdefault("boolean_patterns", {})
    data["boolean_patterns"].setdefault(field, [])
    append_unique(data["boolean_patterns"][field], patterns)


def ensure_count_terms(data: dict[str, Any], field: str, terms: list[str]) -> None:
    data.setdefault("count_terms", {})
    data["count_terms"].setdefault(field, [])
    append_unique(data["count_terms"][field], terms)


def ensure_medical_floor_tokens(data: dict[str, Any], tokens: list[str]) -> None:
    data.setdefault("medical_floor_tokens", [])
    append_unique(data["medical_floor_tokens"], tokens)


def patch() -> None:
    data = load_json(DETERMINISTIC_PATH)

    # ------------------------------------------------------------------
    # Vomiting variants: T156, T162, T202, T239
    # ------------------------------------------------------------------
    ensure_count_terms(data, "vomiting", [
        "throw up",
        "throws up",
        "throwing up",
        "thrown up",
        "puke",
        "puked",
        "puking",
        "sick",
        "vomiting everything",
        "can't keep water down",
        "cannot keep water down",
        "keeps vomiting"
    ])

    ensure_boolean_patterns(data, "vomiting", [
        "throwing up",
        "throws up",
        "thrown up",
        "puking",
        "puked",
        "vomiting everything",
        "can't keep.{0,30}(water|fluids|milk|formula).{0,20}down",
        "cannot keep.{0,30}(water|fluids|milk|formula).{0,20}down",
        "keeps vomiting",
        "vomited repeatedly",
        "vomiting repeatedly",
        "vomiting pale green",
        "vomiting green",
        "green vomit",
        "pale green fluid"
    ])

    # ------------------------------------------------------------------
    # Head injury: T156
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "head_injury", [
        "hit.{0,40}head.{0,80}concrete",
        "head.{0,40}concrete",
        "fell off.{0,50}scooter",
        "scooter.{0,80}(hit|bumped).{0,50}head",
        "huge goose egg",
        "goose egg.{0,50}(forehead|head)",
        "forehead.{0,50}goose egg"
    ])

    ensure_boolean_patterns(data, "vomiting_after_head_injury", [
        "(hit|bumped).{0,50}head.{0,120}(vomit|vomited|vomiting|throwing up|thrown up|throws up|puked|puking)",
        "(vomit|vomited|vomiting|throwing up|thrown up|throws up|puked|puking).{0,120}(hit|bumped).{0,50}head",
        "fell off.{0,50}scooter.{0,160}(vomit|vomited|vomiting|throwing up|thrown up|puked|puking)"
    ])

    # ------------------------------------------------------------------
    # Severe dehydration: T162, T166
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "reduced_urine", [
        "hasn't peed since yesterday",
        "has not peed since yesterday",
        "hasn't passed urine since yesterday",
        "has not passed urine since yesterday",
        "hasn't urinated since yesterday",
        "has not urinated since yesterday",
        "no pee since yesterday",
        "no urine since yesterday",
        "not peed since yesterday",
        "not passed urine since yesterday"
    ])

    ensure_boolean_patterns(data, "not_drinking", [
        "vomiting everything",
        "can't keep water down",
        "cannot keep water down",
        "can't keep fluids down",
        "cannot keep fluids down",
        "can't keep milk down",
        "cannot keep milk down"
    ])

    ensure_boolean_patterns(data, "lethargic", [
        "too weak to stand",
        "too weak to stand up",
        "too weak to sit",
        "too weak",
        "completely floppy",
        "floppy",
        "just wants to sleep",
        "too tired to latch",
        "too tired to feed",
        "very confused",
        "confused",
        "too weak to stand and",
        "too weak to stand up and"
    ])

    ensure_boolean_patterns(data, "sunken_eyes", [
        "sunken eyes",
        "eyes are sunken",
        "eyes look sunken"
    ])

    ensure_boolean_patterns(data, "very_irritable", [
        "won't let me touch him",
        "will not let me touch him",
        "won't let me touch her",
        "will not let me touch her",
        "extremely irritable",
        "very irritable",
        "screaming and cannot settle",
        "screaming and won't settle"
    ])

    # ------------------------------------------------------------------
    # Meningitis / sepsis / CNS red flags: T169, T170, T171, T239
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "light_sensitivity", [
        "sensitive to light",
        "light is bothering",
        "light hurts",
        "room is too bright",
        "hiding.{0,60}face.{0,80}(light|bright)",
        "hides.{0,60}face.{0,80}(light|bright)",
        "keeps crying and hiding.{0,60}face"
    ])

    # If no dedicated bulging_fontanelle field exists, we map it to meningitis/CNS danger via stiff_neck proxy.
    ensure_boolean_patterns(data, "stiff_neck", [
        "soft spot.{0,80}(bulging|bulges|bulged|sticking out|hard)",
        "fontanelle.{0,80}(bulging|bulges|bulged|sticking out|hard)",
        "bulging.{0,40}(soft spot|fontanelle)",
        "(soft spot|fontanelle).{0,40}feels hard"
    ])

    ensure_boolean_patterns(data, "blue_lips", [
        "blue tint around.{0,40}(mouth|nose|lips)",
        "blue around.{0,40}(mouth|nose|lips)",
        "mouth.{0,40}blue",
        "nose.{0,40}blue",
        "lips looked blue",
        "looked blue",
        "turns blue",
        "turned blue",
        "slightly blue",
        "skin looks mottled",
        "mottled and purple",
        "mottled purple",
        "purple mottled",
        "hands and feet.{0,80}(ice cold|cold)",
        "(ice cold|cold).{0,80}hands and feet"
    ])

    ensure_boolean_patterns(data, "hard_to_wake", [
        "too weak to stand",
        "too weak to stand up",
        "very confused",
        "confused",
        "too weak to sit",
        "not making sense"
    ])

    # ------------------------------------------------------------------
    # Poisoning / chemical / medicine ingestion: T177, T178
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "swallowed_medicine_or_chemical", [
        "(bit into|chewed|swallowed|ate|drank).{0,100}(laundry detergent|detergent packet|detergent pod|washing pod|laundry pod)",
        "(laundry detergent|detergent packet|detergent pod|washing pod|laundry pod).{0,100}(bit into|chewed|swallowed|ate|drank)",
        "spitting up.{0,50}(soap|detergent|blue soap)",
        "(iron supplements|iron tablets|iron pills).{0,100}(missing|open|ate|swallowed|chewed)",
        "(ate|swallowed|chewed).{0,100}(iron supplements|iron tablets|iron pills)",
        "tablets missing",
        "pills missing",
        "dark red powder on.{0,30}lips"
    ])

    # ------------------------------------------------------------------
    # Allergy/anaphylaxis: T181
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "allergen_exposure", [
        "hazelnut",
        "hazelnut traces",
        "nut traces",
        "tree nut",
        "cashew",
        "almond",
        "walnut"
    ])

    ensure_boolean_patterns(data, "throat_swelling", [
        "tongue feels itchy",
        "tongue feels fuzzy",
        "itchy tongue",
        "fuzzy tongue",
        "voice sounds raspy",
        "raspy voice",
        "voice sounds deep",
        "voice changed",
        "voice has changed",
        "hoarse voice after.{0,60}(nut|hazelnut|peanut|egg|milk|bee|wasp)",
        "raspy.{0,40}voice.{0,80}(nut|hazelnut|peanut|egg|milk|bee|wasp)"
    ])

    # ------------------------------------------------------------------
    # Respiratory/cyanosis: T190, T235
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "chest_retractions", [
        "chest is pulling in",
        "chest.{0,40}pulling in",
        "chest.{0,40}sucking in",
        "stomach is sucking in",
        "skin pulling in under.{0,30}ribs",
        "pulling in very hard",
        "pulling in deeply"
    ])

    ensure_boolean_patterns(data, "choking_silent", [
        "choking.{0,100}(silent|completely silent|cannot make any sound|can't make any sound|no sound)",
        "gasped.{0,80}(turned blue|blue).{0,80}(silent|struggling to breathe)",
        "plastic wrapper.{0,100}(gasped|choking|silent|turned blue)",
        "completely silent and struggling to breathe",
        "silent and struggling to breathe"
    ])

    ensure_boolean_patterns(data, "not_breathing", [
        "struggling to breathe",
        "cannot breathe",
        "can't breathe",
        "gasping",
        "gasped"
    ])

    # ------------------------------------------------------------------
    # Burns: T191, T195, T196
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "burn", [
        "hot soup",
        "bowl of hot soup",
        "pulled.{0,80}hot soup",
        "sunburn",
        "bad sunburn",
        "hot coal",
        "stepped on.{0,40}hot coal",
        "white and charred",
        "charred",
        "skin is peeling",
        "peeling"
    ])

    ensure_boolean_patterns(data, "burn_blister", [
        "large blisters",
        "extensive blistering",
        "skin is blistering",
        "forming large blisters",
        "peeling",
        "skin is peeling"
    ])

    ensure_boolean_patterns(data, "burn_infected", [
        "yellow pus",
        "pus oozing",
        "oozing pus"
    ])

    ensure_boolean_patterns(data, "burn_sensitive_area", [
        "neck",
        "foot",
        "feet",
        "sole",
        "sole of his foot",
        "sole of her foot"
    ])

    ensure_boolean_patterns(data, "lethargic", [
        "feels dizzy",
        "dizzy",
        "feels sick",
        "sick and dizzy"
    ])

    # ------------------------------------------------------------------
    # Abdominal pain / appendicitis / intussusception / hernia: T201, T202, T205
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "severe_abdominal_pain", [
        "severe pain around.{0,50}belly button",
        "pain around.{0,50}belly button.{0,80}lower right",
        "moved to the lower right",
        "lower right side",
        "right lower.{0,30}(tummy|belly|abdomen|abdominal)",
        "crying when he walks",
        "crying when she walks",
        "won't let me touch.{0,30}(tummy|belly|abdomen)",
        "will not let me touch.{0,30}(tummy|belly|abdomen)",
        "screaming in pain every",
        "screaming in pain.{0,80}pulling.{0,30}knees",
        "hard, purple lump in.{0,40}groin",
        "purple lump in.{0,40}groin",
        "groin.{0,40}(hard|purple).{0,80}(screaming|vomiting|pain)"
    ])

    ensure_boolean_patterns(data, "knees_up", [
        "pulling his knees up to his chest",
        "pulling her knees up to her chest",
        "knees up to his chest",
        "knees up to her chest",
        "pulling.{0,30}knees.{0,30}chest"
    ])

    # ------------------------------------------------------------------
    # Urinary / flank pain / hematuria: T210, T211
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "urinary_pain", [
        "flank pain",
        "lower back pain",
        "severe pain in her lower back",
        "severe pain in his lower back",
        "pain in her lower back",
        "pain in his lower back",
        "urine is pink",
        "pink urine",
        "red urine",
        "blood in urine",
        "blood in his urine",
        "blood in her urine",
        "red clots",
        "small red clots",
        "clots in urine"
    ])

    # ------------------------------------------------------------------
    # Persistent nosebleed: T220
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "persistent_nosebleed", [
        "nosebleed.{0,100}(25 minutes|twenty five minutes|twenty-five minutes)",
        "gushing blood.{0,100}(25 minutes|twenty five minutes|twenty-five minutes)",
        "despite.{0,80}pinching.{0,80}nose",
        "pinching.{0,80}nose.{0,80}(still bleeding|gushing|won't stop|will not stop)",
        "leaning forward.{0,80}(still bleeding|gushing|won't stop|will not stop)"
    ])

    # ------------------------------------------------------------------
    # Limp / joint / musculoskeletal: T223
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "sudden_limp", [
        "walking with a limp",
        "walking funny",
        "limping.{0,80}no trauma",
        "limp.{0,80}no trauma",
        "no trauma.{0,80}limp",
        "no injury.{0,80}limp",
        "woke up.{0,80}limping"
    ])

    ensure_boolean_patterns(data, "refusing_weight_bear", [
        "refuses to stand",
        "refuses to walk",
        "will not stand",
        "will not walk",
        "won't stand",
        "won't walk"
    ])

    # ------------------------------------------------------------------
    # Wounds / bites: T226
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "deep_wound", [
        "cat bite",
        "stray cat",
        "animal bite",
        "dog bite",
        "puncture wounds",
        "puncture wound",
        "bite.{0,80}puncture",
        "puncture.{0,80}bleeding"
    ])

    # ------------------------------------------------------------------
    # Measles/systemic rash: T227
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "has_rash", [
        "flat red rash",
        "rash started behind his ears",
        "rash started behind her ears",
        "rash behind ears",
        "red watery eyes",
        "watery eyes"
    ])

    ensure_boolean_patterns(data, "rash_starting_on_face", [
        "rash started behind his ears",
        "rash started behind her ears",
        "rash behind ears",
        "spreading to his face and neck",
        "spreading to her face and neck",
        "spreading to face and neck",
        "started behind.{0,30}ears.{0,80}spreading"
    ])

    ensure_boolean_patterns(data, "spreading_rash", [
        "rash.{0,80}spreading",
        "spreading.{0,80}rash",
        "spreading to his face and neck",
        "spreading to her face and neck",
        "spreading to face and neck"
    ])

    # ------------------------------------------------------------------
    # Submersion / aspiration: T237
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "water_submersion", [
        "slipped under the bathwater",
        "under the bathwater",
        "under bathwater",
        "bathwater.{0,80}(slipped under|went under)",
        "went under.{0,40}bathwater"
    ])

    ensure_boolean_patterns(data, "post_submersion_coughing", [
        "choked and vomited",
        "breathing sounds very wet",
        "wet and rattling",
        "rattling breathing",
        "breathing sounds.{0,40}rattling",
        "breathing sounds.{0,40}wet",
        "wet.{0,40}breathing"
    ])

    # ------------------------------------------------------------------
    # Headache/meningitis/encephalitis: T239
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "headache", [
        "severe headache",
        "bad headache",
        "terrible headache"
    ])

    ensure_boolean_patterns(data, "worst_headache", [
        "severe headache.{0,120}(vomiting|confused|confusion|too weak)",
        "high fever.{0,120}severe headache",
        "severe headache.{0,120}high fever"
    ])

    # ------------------------------------------------------------------
    # Spider/systemic bite: T248
    # Use deep_wound + systemic signals so rules can escalate.
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "deep_wound", [
        "spider bite",
        "bitten by a spider",
        "bite area is turning purple",
        "bite area is turning black",
        "turning purple/black",
        "purple/black"
    ])

    ensure_boolean_patterns(data, "lethargic", [
        "severe headache and fever",
        "fever and severe headache"
    ])

    # ------------------------------------------------------------------
    # Testicular pain wording: T254
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "testicular_pain", [
        "testicle hurts",
        "testicles hurt",
        "left testicle hurts",
        "right testicle hurts",
        "testicle is hurting",
        "testicles are hurting",
        "scrotum hurts",
        "scrotum is hurting",
        "says his.{0,30}testicle hurts",
        "says her.{0,30}testicle hurts"
    ])

    ensure_medical_floor_tokens(data, [
        "goose egg",
        "thrown up",
        "throwing up",
        "fontanelle",
        "soft spot",
        "mottled",
        "laundry pod",
        "detergent pod",
        "iron supplements",
        "hazelnut",
        "raspy voice",
        "hot soup",
        "hot coal",
        "charred",
        "flank pain",
        "blood in urine",
        "pink urine",
        "spider bite",
        "testicle hurts"
    ])

    save_json(DETERMINISTIC_PATH, data)
    print(f"✅ Patched deterministic patterns: {DETERMINISTIC_PATH}")
    print("✅ Under-triage patch 002 applied.")


if __name__ == "__main__":
    if not DETERMINISTIC_PATH.exists():
        raise FileNotFoundError(DETERMINISTIC_PATH)

    patch()