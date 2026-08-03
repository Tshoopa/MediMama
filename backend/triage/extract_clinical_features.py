# backend/triage/extract_clinical_features.py

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.triage.features import ClinicalFeatures, FeatureValue
from backend.triage.semantic_feature_detector import apply_semantic_feature_detection
from backend.triage.feature_assist_merge import merge_feature_assist

PATTERNS_PATH = Path(__file__).resolve().parent / "deterministic_feature_patterns.json"

NUMBER_WORDS = {
    "one": 1, "once": 1, "two": 2, "twice": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}

REDUCED_URINE_HOURS_THRESHOLD = 6

EXCLUDED_MEDICAL_FLOOR_FIELDS = {
    "routine_or_nonmedical",
    "mild_medical_symptom",
    "negated_fever",
    "negated_fields",
}

FEATURE_ALIASES = {
    "photophobia": "light_sensitivity",
}

ALLOWED_TOP_LEVEL_PATTERN_KEYS = {
    "version", "description", "tokens", "count_terms", "negation_overrides",
    "boolean_patterns", "value_patterns", "derived_patterns", "medical_floor_tokens",
}


def _canonical_field(field: str) -> str:
    return FEATURE_ALIASES.get(field, field)


def _new_empty_features() -> ClinicalFeatures:
    return ClinicalFeatures(raw_text="", text="", age_months=None)


def _is_setable_bool_like(sample: ClinicalFeatures, target: str) -> bool:
    val = getattr(sample, target)
    return isinstance(val, (bool, FeatureValue))


def _validate_loaded_patterns(data: dict[str, Any]) -> None:
    """Fail fast if the patterns JSON references unknown or unsettable fields."""
    unknown_top_level = set(data.keys()) - ALLOWED_TOP_LEVEL_PATTERN_KEYS
    if unknown_top_level:
        keys = ", ".join(sorted(unknown_top_level))
        raise ValueError(f"Disallowed top-level keys in patterns JSON: {keys}.")

    sample = _new_empty_features()

    for field in data.get("boolean_patterns", {}):
        target = _canonical_field(field)
        if not hasattr(sample, target):
            raise AttributeError(f"Unknown field in boolean_patterns: '{field}' -> '{target}'")
        if not _is_setable_bool_like(sample, target):
            raise TypeError(f"Field not settable via boolean_patterns: '{field}' -> '{target}'")

    for field in data.get("negation_overrides", {}):
        target = _canonical_field(field)
        if not hasattr(sample, target):
            raise AttributeError(f"Unknown field in negation_overrides: '{field}'.")
        if not _is_setable_bool_like(sample, target):
            raise TypeError(f"Field not settable via negation_overrides: '{field}' -> '{target}'")

    for item in data.get("value_patterns", []):
        field = item.get("field")
        if not field:
            raise ValueError("value_patterns item missing required key: 'field'")
        if not hasattr(sample, field):
            raise AttributeError(f"Unknown field in value_patterns: '{field}'")


@lru_cache(maxsize=1)
def _load_patterns() -> dict[str, Any]:
    with PATTERNS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_loaded_patterns(data)
    return data


def _has(text: str, patterns: list[str]) -> bool:
    for pattern in patterns or []:
        try:
            if re.search(pattern, text):
                return True
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {pattern}") from exc
    return False


def _safe_set_bool(f: ClinicalFeatures, field: str, value: bool = True) -> None:
    """Set a bool or FeatureValue field; for FeatureValue only toggles `present`."""
    original_field = field
    field = _canonical_field(field)

    if not hasattr(f, field):
        raise AttributeError(f"Unknown field: {original_field} -> {field}")

    current = getattr(f, field)
    if isinstance(current, FeatureValue):
        current.present = value
    elif isinstance(current, bool):
        setattr(f, field, value)
    else:
        raise TypeError(f"Field is not bool/FeatureValue: {field}")

    # Keep the alias (e.g. photophobia) in sync with its canonical field.
    if original_field != field and hasattr(f, original_field):
        alias_val = getattr(f, original_field)
        if isinstance(alias_val, FeatureValue):
            alias_val.present = value
        elif isinstance(alias_val, bool):
            setattr(f, original_field, value)


def _safe_set_value(f: ClinicalFeatures, field: str, value: Any) -> None:
    if not hasattr(f, field):
        raise AttributeError(f"Unknown field in value_patterns: {field}")
    setattr(f, field, value)


def extract_temperature(text: str) -> float | None:
    matches = re.findall(r"(\d{2}(?:\.\d)?)\s*(?:degree|degrees|°|c\b|celsius)?", text)
    temps = []
    for item in matches:
        try:
            value = float(item)
            if 30.0 <= value <= 45.0:  # plausible body-temperature range
                temps.append(value)
        except ValueError:
            continue
    return max(temps) if temps else None


def _number_token_to_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def _extract_count_near(text: str, symptom_words: list[str]) -> int | None:
    if not symptom_words:
        return None
    symptom_group = "|".join(re.escape(w) for w in symptom_words)
    patterns = [
        rf"({symptom_group}).{{0,60}}(\d+|one|once|two|twice|three|four|five|six|seven|eight|nine|ten).{{0,30}}(time|times|episode|episodes|today|since)?",
        rf"(\d+|one|once|two|twice|three|four|five|six|seven|eight|nine|ten).{{0,30}}(time|times|episode|episodes).{{0,60}}({symptom_group})",
        rf"(\d+|one|once|two|twice|three|four|five|six|seven|eight|nine|ten).{{0,30}}({symptom_group})",
    ]
    counts = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            flat = " ".join(match) if isinstance(match, tuple) else match
            token_match = re.search(
                r"\b(\d+|one|once|two|twice|three|four|five|six|seven|eight|nine|ten)\b", flat
            )
            if token_match:
                value = _number_token_to_int(token_match.group(1))
                if value is not None:
                    counts.append(value)
    return max(counts) if counts else None


def _extract_hours_without_urine(text: str) -> int | None:
    urine_terms = (
        r"(?:wet (?:nappy|nappies|diaper|diapers)|"
        r"dry (?:nappy|nappies|diaper|diapers)|"
        r"nappy|nappies|diaper|diapers|"
        r"pee|peed|wee|weed|urine|urinated|passed urine)"
    )
    number_group = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    absence_context = r"(?:no|not|hasn't|has not|haven't|have not|without|dry)"
    patterns = [
        rf"{absence_context}.{{0,40}}{urine_terms}.{{0,40}}{number_group}\s*hours?",
        rf"{urine_terms}.{{0,20}}{absence_context}.{{0,40}}{number_group}\s*hours?",
        rf"{absence_context}.{{0,40}}{urine_terms}.{{0,40}}(?:in|for|over)\s*{number_group}\s*hours?",
    ]
    hours = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            token = match if isinstance(match, str) else next((m for m in match if m), "")
            value = _number_token_to_int(token)
            if value is not None:
                hours.append(value)
    return max(hours) if hours else None


def _compute_dehydration_score(f: ClinicalFeatures) -> int:
    score = 0
    if f.age_months is not None and f.age_months <= 12:
        score += 1
    if f.diarrhea_count is not None and f.diarrhea_count >= 6:
        score += 1
    if f.vomiting_count is not None and f.vomiting_count >= 5:
        score += 1
    if f.reduced_urine or f.no_wet_diapers:
        score += 2
    if f.sunken_eyes:
        score += 2
    if f.sunken_fontanelle:
        score += 2
    if f.no_tears:
        score += 1
    if f.dry_mouth:
        score += 1
    if f.not_drinking or f.refusing_fluids:
        score += 2
    if f.lethargic or f.hard_to_wake:
        score += 2
    return score


def _apply_boolean_patterns(f: ClinicalFeatures, text: str) -> None:
    for field, patterns in _load_patterns().get("boolean_patterns", {}).items():
        if _has(text, patterns):
            _safe_set_bool(f, field, True)


def _apply_value_patterns(f: ClinicalFeatures, text: str) -> None:
    for item in _load_patterns().get("value_patterns", []):
        if _has(text, item.get("patterns", [])):
            _safe_set_value(f, item["field"], item["value"])


def _apply_negation_overrides(f: ClinicalFeatures, text: str) -> None:
    data = _load_patterns()
    for field, patterns in data.get("negation_overrides", {}).items():
        canonical = _canonical_field(field)
        if _has(text, patterns):
            # A measured temperature always wins over a negation phrase.
            if canonical == "has_fever" and f.temperature is not None:
                continue
            _safe_set_bool(f, field, False)
            f.negated_fields.add(canonical)


def _extract_special_numeric_and_negation_features(f: ClinicalFeatures, text: str) -> None:
    data = _load_patterns()

    f.temperature = extract_temperature(text)
    f.negated_fever = _has(text, data.get("negation_overrides", {}).get("has_fever", []))

    fever_tokens = data.get("tokens", {}).get("fever", [])
    f.has_fever = (
        f.temperature is not None
        or (not f.negated_fever and any(token in text for token in fever_tokens))
    )

    vomiting_terms = data.get("count_terms", {}).get("vomiting", [])
    negated_vomiting = _has(text, data.get("negation_overrides", {}).get("vomiting", []))
    f.vomiting = not negated_vomiting and any(term in text for term in vomiting_terms)

    diarrhea_terms = data.get("count_terms", {}).get("diarrhea", [])
    f.diarrhea_count = _extract_count_near(text, diarrhea_terms)
    f.vomiting_count = _extract_count_near(text, vomiting_terms)

    hours_no_urine = _extract_hours_without_urine(text)
    if hours_no_urine is not None and hours_no_urine >= REDUCED_URINE_HOURS_THRESHOLD:
        f.reduced_urine = True
        if f.age_months is not None and f.age_months <= 24:
            f.no_wet_diapers = True


# ── Severity hint lists for rich (FeatureValue) features ──

MILD_BURN_HINTS = [
    "small red mark", "small mark", "small red", "little red",
    "small patch", "slightly red", "small blister", "tiny blister",
    "a bit red", "small area",
]
SEVERE_BURN_HINTS = [
    "charred", "white and charred", "extensive blister", "large blister",
    "peeling", "skin is peeling", "all over", "whole", "big area",
    "deep", "pus", "oozing",
]

MILD_FALL_HINTS = [
    "bumped head while running", "tripped", "minor bump", "small bump",
    "now playing", "acting normally", "fine now", "playing normally",
]
SEVERE_FALL_HINTS = [
    "knocked out", "lost consciousness", "unconscious", "2 meters",
    "two meters", "concrete", "not moving", "won't wake",
]

MILD_WOUND_HINTS = [
    "small cut", "small graze", "tiny cut", "little scratch",
    "minor scrape", "shallow",
]
SEVERE_WOUND_HINTS = [
    "gaping", "won't stop bleeding", "deep gash", "bone visible",
    "large laceration", "needs stitches",
]

MILD_BITE_HINTS = [
    "small scratch", "didn't break skin", "barely broke skin",
    "tiny bite", "no bleeding",
]
SEVERE_BITE_HINTS = [
    "deep bite", "puncture wound", "bleeding heavily", "won't stop bleeding",
    "large wound", "torn skin",
]


def _compute_burn_severity(f: ClinicalFeatures, text: str) -> None:
    if not f.burn:
        return
    f.burn.modifiers["location"] = "sensitive" if f.burn_sensitive_area else None

    if _has(text, SEVERE_BURN_HINTS) or f.burn_infected:
        f.burn.severity = "severe"
    elif f.burn_blister and not any(h in text for h in MILD_BURN_HINTS):
        f.burn.severity = "moderate"
    elif any(h in text for h in MILD_BURN_HINTS):
        f.burn.severity = "mild"
    else:
        # Hot-source burn with no severity cues -> moderate, conservatively.
        f.burn.severity = "moderate"


def _compute_fall_severity(f: ClinicalFeatures, text: str) -> None:
    for feat in (f.fall_from_height, f.head_injury):
        if not feat:
            continue
        if any(h in text for h in SEVERE_FALL_HINTS) or f.vomiting_after_head_injury or f.drowsy_after_head_injury:
            feat.severity = "severe"
        elif any(h in text for h in MILD_FALL_HINTS):
            feat.severity = "mild"
        else:
            feat.severity = "moderate"


def _compute_hives_severity(f: ClinicalFeatures, text: str) -> None:
    if not f.hives:
        return
    if f.widespread_hives:
        f.hives.severity = "moderate"
    elif any(h in text for h in ["small patch", "few hives", "only on", "localized", "one spot"]):
        f.hives.severity = "mild"
    else:
        f.hives.severity = "moderate"


def _compute_foreign_body_severity(f: ClinicalFeatures, text: str) -> None:
    if not f.foreign_body_nose:
        return
    if any(h in text for h in ["can see it", "calm", "breathing normally", "playing"]):
        f.foreign_body_nose.severity = "mild"
    else:
        f.foreign_body_nose.severity = "moderate"


def _compute_deep_wound_severity(f: ClinicalFeatures, text: str) -> None:
    if not f.deep_wound:
        return
    if _has(text, SEVERE_WOUND_HINTS):
        f.deep_wound.severity = "severe"
    elif any(h in text for h in MILD_WOUND_HINTS):
        f.deep_wound.severity = "mild"
    else:
        f.deep_wound.severity = "moderate"


def _compute_animal_bite_severity(f: ClinicalFeatures, text: str) -> None:
    if not f.animal_bite:
        return
    if _has(text, SEVERE_BITE_HINTS):
        f.animal_bite.severity = "severe"
    elif any(h in text for h in MILD_BITE_HINTS):
        f.animal_bite.severity = "mild"
    else:
        f.animal_bite.severity = "moderate"


def _recompute_derived_features(f: ClinicalFeatures, text: str) -> None:
    data = _load_patterns()
    derived = data.get("derived_patterns", {})

    if f.temperature is not None:
        f.has_fever = True

    if f.photophobia:
        f.light_sensitivity = True
    if f.light_sensitivity:
        f.photophobia = True

    if f.non_blanching_rash or f.spreading_rash or f.rash_starting_on_face or f.measles_like_rash:
        f.has_rash = True

    if f.measles_like_rash:
        f.spreading_rash = True
        f.rash_starting_on_face = True

    if f.prolonged_seizure:
        f.seizure = True

    if not f.head_injury and (
        f.fall_from_height or ("head" in text and _has(text, derived.get("head_injury_context", [])))
    ):
        f.head_injury.present = True

    f.vomiting_after_head_injury = f.vomiting_after_head_injury or (bool(f.head_injury) and f.vomiting)
    f.drowsy_after_head_injury = f.drowsy_after_head_injury or (
        bool(f.head_injury) and _has(text, derived.get("drowsy_after_head_injury", []))
    )

    f.post_submersion_coughing = f.post_submersion_coughing or (
        f.water_submersion and _has(text, derived.get("post_submersion_coughing", []))
    )
    f.vomiting_after_allergen = f.vomiting_after_allergen or (f.allergen_exposure and f.vomiting)

    if f.appendicitis_signs:
        f.severe_abdominal_pain = True
    if f.strangulated_hernia_signs:
        f.severe_abdominal_pain = True
        f.testicular_pain = True
    if f.flank_pain:
        f.urinary_pain = True
    if f.cns_infection_red_flags:
        f.headache = True
        f.lethargic = True
    if f.severe_or_early_jaundice:
        f.jaundice_or_yellow = True
    if f.poor_feeding and f.age_months is not None and f.age_months <= 3:
        f.lethargic = True

    _compute_burn_severity(f, text)
    _compute_fall_severity(f, text)
    _compute_hives_severity(f, text)
    _compute_foreign_body_severity(f, text)
    _compute_deep_wound_severity(f, text)
    _compute_animal_bite_severity(f, text)

    f.dehydration_score = _compute_dehydration_score(f)

    _mark_medical_floor(f, text)


def _mark_medical_floor(f: ClinicalFeatures, text: str) -> None:
    """L4 floor gate: any mild medical symptom should be at least L4, not L5.

    Simple bools and mild/unknown FeatureValues trigger the floor. Moderate
    and severe FeatureValues do NOT — they must stay free to be escalated to
    L2/L3 by the triage rules instead of being pinned down to L4 here.
    """
    data = _load_patterns()

    if any(token in text for token in data.get("medical_floor_tokens", [])):
        f.mild_medical_symptom = True
        return

    for field_name in getattr(f, "__dataclass_fields__", {}):
        if field_name in EXCLUDED_MEDICAL_FLOOR_FIELDS:
            continue
        value = getattr(f, field_name, None)

        if isinstance(value, bool) and value is True:
            f.mild_medical_symptom = True
            return

        if isinstance(value, FeatureValue) and value.present and value.severity in ("mild", "unknown"):
            f.mild_medical_symptom = True
            return


def _build_debug(f: ClinicalFeatures) -> dict[str, Any]:
    debug: dict[str, Any] = {}
    for field_name in getattr(f, "__dataclass_fields__", {}):
        if field_name in {"raw_text", "text", "debug"}:
            continue
        value = getattr(f, field_name)
        if isinstance(value, FeatureValue):
            debug[field_name] = {
                "present": value.present,
                "severity": value.severity,
                "modifiers": value.modifiers,
            }
        else:
            debug[field_name] = value

    debug["semantic_feature_hits"] = (
        f.debug.get("semantic_feature_hits", []) if isinstance(f.debug, dict) else []
    )
    return debug


def extract_clinical_features(
    raw_text: str,
    normalized_text: str,
    age_months: int | None,
    feature_assist: dict | None = None,
) -> ClinicalFeatures:
    text = normalized_text or ""
    f = ClinicalFeatures(raw_text=raw_text, text=text, age_months=age_months)

    _extract_special_numeric_and_negation_features(f, text)
    _apply_boolean_patterns(f, text)
    _apply_value_patterns(f, text)

    f = apply_semantic_feature_detection(f, text)

    _apply_negation_overrides(f, text)

    # LLM feature assist merges after deterministic extraction + negation but
    # before derived/severity computation, so assist-added fields still get
    # proper severity from _recompute_derived_features.
    if feature_assist:
        f = merge_feature_assist(f, feature_assist)

    _recompute_derived_features(f, text)

    f.debug = _build_debug(f)
    return f