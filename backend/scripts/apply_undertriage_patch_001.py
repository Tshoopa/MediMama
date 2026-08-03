# backend/scripts/apply_undertriage_patch_001.py

import json
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
TRIAGE_DIR = BACKEND_DIR / "triage"

DETERMINISTIC_PATH = TRIAGE_DIR / "deterministic_feature_patterns.json"
SEMANTIC_PATH = TRIAGE_DIR / "triage_semantic_concepts.json"


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


def ensure_negation_patterns(data: dict[str, Any], field: str, patterns: list[str]) -> None:
    data.setdefault("negation_overrides", {})
    data["negation_overrides"].setdefault(field, [])
    append_unique(data["negation_overrides"][field], patterns)


def ensure_medical_floor_tokens(data: dict[str, Any], tokens: list[str]) -> None:
    data.setdefault("medical_floor_tokens", [])
    append_unique(data["medical_floor_tokens"], tokens)


def patch_deterministic_patterns() -> None:
    data = load_json(DETERMINISTIC_PATH)

    # ------------------------------------------------------------------
    # T003 / T004: high-risk fall mechanism
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "fall_from_height", [
        "(tumbled|tumble|slipped|slip|fell|fallen|dropped|rolled).{0,60}(down|off|from|out of).{0,90}(stairs?|bed|table|changing table|pram|stroller|cot|couch|sofa|chair|high chair|highchair)",
        "(tumbled down|fell down|rolled down|slipped down).{0,40}stairs?",
        "(slipped|fell|dropped|tumbled).{0,50}(from|off).{0,40}(high chair|highchair)",
        "tumbled down.{0,30}stairs?",
        "slipped from.{0,30}high chair",
        "slipped from.{0,30}highchair"
    ])

    ensure_boolean_patterns(data, "head_injury", [
        "(fell|tumbled|slipped|dropped|rolled).{0,100}(head|floor|ground)",
        "(head|forehead).{0,60}(hit|bump|bumped|injury)"
    ])

    # ------------------------------------------------------------------
    # T009 / T105: dehydration variants
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "reduced_urine", [
        "has not.{0,40}(peed|wee|weed|urinated|passed urine)",
        "hasn't.{0,40}(peed|wee|weed|urinated|passed urine)",
        "not passed urine",
        "not passing urine",
        "barely.{0,30}(peed|wee|weed|urinated)",
        "hardly.{0,30}(peed|wee|weed|urinated)",
        "very little.{0,30}(urine|pee|wee)",
        "much less.{0,30}(urine|pee|wee)"
    ])

    ensure_boolean_patterns(data, "no_wet_diapers", [
        "has not had.{0,50}wet.{0,30}(diaper|diapers|nappy|nappies)",
        "hasn't had.{0,50}wet.{0,30}(diaper|diapers|nappy|nappies)",
        "no wet diaper",
        "no wet diapers",
        "no wet nappy",
        "no wet nappies",
        "dry diaper",
        "dry nappy",
        "dry nappies",
        "dry diapers"
    ])

    ensure_boolean_patterns(data, "sunken_eyes", [
        "eyes look sunken",
        "eyes are sunken",
        "sunken eyes",
        "eyes.{0,30}sunken"
    ])

    ensure_boolean_patterns(data, "no_tears", [
        "no tears",
        "without tears",
        "crying without tears",
        "cries without tears",
        "tears.{0,30}not.{0,30}(coming|come)",
        "no tears.{0,30}(when|while).{0,20}crying"
    ])

    ensure_boolean_patterns(data, "poor_feeding", [
        "not feeding",
        "not feeding well",
        "poor feeding",
        "feeding poorly",
        "not taking milk",
        "too sleepy to feed"
    ])

    ensure_boolean_patterns(data, "lethargic", [
        "lethargic",
        "very sleepy",
        "floppy",
        "hard to wake",
        "not acting normally",
        "drowsy",
        "too sleepy"
    ])

    # ------------------------------------------------------------------
    # T015: non-blanching / dark spots
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "has_rash", [
        "dark spots",
        "small dark spots",
        "pinprick rash",
        "pin prick rash",
        "tiny red dots",
        "tiny dark dots"
    ])

    ensure_boolean_patterns(data, "non_blanching_rash", [
        "dark spots.{0,80}(do not|does not|did not|don't|doesn't).{0,40}(fade|go away|disappear|blanch)",
        "spots.{0,80}(do not|does not|did not|don't|doesn't).{0,40}(fade|go away|disappear|blanch)",
        "dots.{0,80}(do not|does not|did not|don't|doesn't).{0,40}(fade|go away|disappear|blanch)",
        "(do not|does not|did not|don't|doesn't).{0,40}(fade|go away|disappear|blanch).{0,80}(spots|dots|rash)",
        "do not go away when pressed",
        "does not go away when pressed",
        "did not go away when pressed",
        "do not fade when pressed",
        "does not fade when pressed",
        "did not fade when pressed",
        "small dark spots",
        "pinprick rash",
        "pin prick rash"
    ])

    # ------------------------------------------------------------------
    # T026: severe wheeze / cannot speak
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "wheeze", [
        "wheezing",
        "wheeze"
    ])

    ensure_boolean_patterns(data, "breathing_difficulty", [
        "wheez.{0,80}(cannot|can't|can not).{0,50}(speak|talk|finish sentence|finish a sentence)",
        "(cannot|can't|can not).{0,50}(speak|talk|finish sentence|finish a sentence).{0,80}wheez",
        "too breathless.{0,50}(speak|talk)",
        "so breathless.{0,50}(speak|talk)",
        "struggling to speak",
        "cannot speak in sentences",
        "can't speak in sentences",
        "cannot finish a sentence",
        "can't finish a sentence"
    ])

    # ------------------------------------------------------------------
    # T049: prolonged coughing fit / cannot catch breath
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "prolonged_coughing_fit", [
        "coughing.{0,100}(long bouts|long spells|long bursts|fits|fit)",
        "cough.{0,100}(long bouts|long spells|long bursts|fits|fit)",
        "coughing.{0,100}(cannot|can't|can not).{0,40}catch.{0,20}breath",
        "cough.{0,100}(cannot|can't|can not).{0,40}catch.{0,20}breath",
        "(cannot|can't|can not).{0,40}catch.{0,20}breath.{0,100}cough",
        "coughing.{0,100}(turns red|turning red|goes red|turned red|turns blue|turning blue|goes blue|turned blue)"
    ])

    ensure_boolean_patterns(data, "breathing_difficulty", [
        "cannot catch.{0,20}breath",
        "can't catch.{0,20}breath",
        "can not catch.{0,20}breath"
    ])

    # ------------------------------------------------------------------
    # T148: young infant fever + urinary pain
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "urinary_pain", [
        "(cries|crying|screams|screaming).{0,60}(when|while|every time).{0,40}(weeing|peeing|passing urine|passes urine|pees|wees|urinating)",
        "(pain|hurts|burning).{0,50}(when|while).{0,40}(weeing|peeing|passing urine|urinating)",
        "(weeing|peeing|passing urine|urinating).{0,50}(hurts|pain|burning|crying|cries)"
    ])

    ensure_boolean_patterns(data, "very_irritable", [
        "very irritable",
        "inconsolable",
        "cannot settle",
        "will not settle",
        "crying nonstop",
        "crying non stop"
    ])

    # ------------------------------------------------------------------
    # T153: neonatal jaundice
    # ------------------------------------------------------------------
    ensure_boolean_patterns(data, "jaundice_or_yellow", [
        "very yellow",
        "looks very yellow",
        "yellow all over",
        "bright yellow",
        "yellow skin",
        "yellow eyes",
        "yellow in the eyes",
        "jaundice",
        "jaundiced"
    ])

    # ------------------------------------------------------------------
    # Negation safety
    # ------------------------------------------------------------------
    ensure_negation_patterns(data, "breathing_difficulty", [
        "breathing normally",
        "breathing fine",
        "no trouble breathing",
        "no breathing problems",
        "no breathing problem"
    ])

    ensure_negation_patterns(data, "non_blanching_rash", [
        "rash fades",
        "spots fade",
        "dots fade",
        "fades when pressed",
        "goes away when pressed",
        "blanches"
    ])

    ensure_negation_patterns(data, "wheeze", [
        "no wheeze",
        "not wheezing",
        "no wheezing"
    ])

    # Medical floor tokens
    ensure_medical_floor_tokens(data, [
        "lethargic",
        "floppy",
        "wheeze",
        "wheezing",
        "urine",
        "pee",
        "wee",
        "jaundice",
        "yellow",
        "dark spots",
        "purple spots",
        "not feeding"
    ])

    save_json(DETERMINISTIC_PATH, data)
    print(f"✅ Patched deterministic patterns: {DETERMINISTIC_PATH}")


def find_concept(data: dict[str, Any], concept_id: str) -> dict[str, Any] | None:
    for concept in data.get("concepts", []):
        if concept.get("id") == concept_id:
            return concept
    return None


def upsert_concept(
    data: dict[str, Any],
    concept_id: str,
    set_features: list[str],
    exemplars: list[str],
    threshold: float = 0.57,
    negative_patterns: list[str] | None = None,
    medical_signal: bool = True,
) -> None:
    data.setdefault("concepts", [])

    concept = find_concept(data, concept_id)

    if concept is None:
        concept = {
            "id": concept_id,
            "set_features": set_features,
            "threshold": threshold,
            "medical_signal": medical_signal,
            "exemplars": [],
            "negative_patterns": []
        }
        data["concepts"].append(concept)

    concept.setdefault("set_features", set_features)
    concept.setdefault("exemplars", [])
    concept.setdefault("negative_patterns", [])

    append_unique(concept["exemplars"], exemplars)

    if negative_patterns:
        append_unique(concept["negative_patterns"], negative_patterns)

    # Do not raise existing thresholds accidentally.
    existing_threshold = float(concept.get("threshold", threshold))
    concept["threshold"] = min(existing_threshold, threshold)


def patch_semantic_concepts() -> None:
    data = load_json(SEMANTIC_PATH)

    upsert_concept(
        data,
        concept_id="fall_from_height",
        set_features=["fall_from_height", "head_injury"],
        threshold=0.55,
        exemplars=[
            "toddler tumbled down the stairs",
            "child slipped from a high chair",
            "fell down several stairs",
            "rolled down stairs",
            "fell from a highchair",
            "dropped from the sofa onto the floor"
        ],
        negative_patterns=[
            "tripped while running and now playing normally",
            "minor bump and now playing"
        ],
    )

    upsert_concept(
        data,
        concept_id="severe_dehydration_urine",
        set_features=["reduced_urine", "no_wet_diapers"],
        threshold=0.56,
        exemplars=[
            "has not peed all day",
            "has not passed urine since morning",
            "no wet nappies for many hours",
            "dry diaper all day",
            "very little urine",
            "barely passing urine"
        ],
        negative_patterns=[
            "normal wet nappies",
            "normal wet diapers",
            "wetting nappies normally",
            "wetting diapers normally",
            "plenty of wet nappies",
            "plenty of wet diapers"
        ],
    )

    upsert_concept(
        data,
        concept_id="sunken_eyes",
        set_features=["sunken_eyes"],
        threshold=0.56,
        exemplars=[
            "eyes look sunken",
            "eyes are sunken in",
            "sunken eyes after vomiting and diarrhea",
            "face looks drawn and eyes look sunken"
        ],
    )

    upsert_concept(
        data,
        concept_id="non_blanching_rash",
        set_features=["has_rash", "non_blanching_rash"],
        threshold=0.56,
        exemplars=[
            "small dark spots that do not fade when pressed",
            "dark spots do not go away when pressed",
            "spots stay when I press them",
            "pinprick rash that does not fade",
            "purple dots that do not disappear with pressure"
        ],
        negative_patterns=[
            "fine pink rash",
            "rash fades when pressed",
            "spots fade when pressed",
            "blanches",
            "goes away when pressed"
        ],
    )

    upsert_concept(
        data,
        concept_id="severe_wheeze_cannot_speak",
        set_features=["wheeze", "breathing_difficulty"],
        threshold=0.56,
        exemplars=[
            "wheezing so badly he cannot speak",
            "wheezing and cannot finish a sentence",
            "too breathless to talk",
            "struggling to speak because of wheezing",
            "cannot speak in sentences due to breathing"
        ],
        negative_patterns=[
            "mild wheeze",
            "breathing normally",
            "speaking normally",
            "no trouble breathing"
        ],
    )

    upsert_concept(
        data,
        concept_id="prolonged_coughing_fit",
        set_features=["prolonged_coughing_fit", "breathing_difficulty"],
        threshold=0.56,
        exemplars=[
            "coughing in long bouts and cannot catch breath",
            "long coughing fits and turns red",
            "coughing fits where he cannot breathe properly",
            "keeps coughing and cannot catch her breath",
            "coughing spells that make him go red"
        ],
        negative_patterns=[
            "mild cough",
            "occasional cough",
            "cough but breathing normally",
            "brief cough"
        ],
    )

    upsert_concept(
        data,
        concept_id="urinary_pain",
        set_features=["urinary_pain"],
        threshold=0.56,
        exemplars=[
            "cries when passing urine",
            "cries every time he wees",
            "screams when peeing",
            "pain when peeing",
            "burning when passing urine"
        ],
    )

    upsert_concept(
        data,
        concept_id="neonatal_jaundice",
        set_features=["jaundice_or_yellow"],
        threshold=0.55,
        exemplars=[
            "one week old baby looks very yellow",
            "newborn is very yellow",
            "newborn has yellow skin",
            "baby is yellow all over",
            "yellow eyes in a newborn"
        ],
    )

    upsert_concept(
        data,
        concept_id="poor_feeding",
        set_features=["poor_feeding"],
        threshold=0.56,
        exemplars=[
            "not feeding well",
            "too sleepy to feed",
            "not taking milk",
            "feeding poorly",
            "refusing feeds"
        ],
        negative_patterns=[
            "feeding well",
            "taking milk well",
            "breastfeeding well",
            "bottle feeding well"
        ],
    )

    save_json(SEMANTIC_PATH, data)
    print(f"✅ Patched semantic concepts: {SEMANTIC_PATH}")


def main() -> None:
    if not DETERMINISTIC_PATH.exists():
        raise FileNotFoundError(DETERMINISTIC_PATH)

    if not SEMANTIC_PATH.exists():
        raise FileNotFoundError(SEMANTIC_PATH)

    patch_deterministic_patterns()
    patch_semantic_concepts()

    print("✅ Under-triage patch 001 applied.")


if __name__ == "__main__":
    main()