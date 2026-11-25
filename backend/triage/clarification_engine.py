"""Deterministic, controlled-template clinical clarification questions.

Questions collect context only; they do not diagnose, set urgency, or alter
clinical thresholds. A pediatric clinician must review the question bank and
its selection conditions before any real-world clinical use.
"""

from __future__ import annotations

import re
from dataclasses import fields
from typing import Any

from backend.triage.extract_clinical_features import extract_clinical_features
from backend.triage.features import FeatureValue
from backend.triage.normalizer import normalize_text


QUESTION_BANK: dict[str, dict[str, Any]] = {
    "symptom_duration": {
        "input_type": "single_choice",
        "text": {
            "en": "How long has the current symptom been present?",
            "fa": "این علامت از چه زمانی شروع شده است؟",
            "ar": "منذ متى بدأت الأعراض الحالية؟",
        },
        "options": [
            {
                "value": "less_than_24_hours",
                "label": {
                    "en": "Less than 24 hours",
                    "fa": "کمتر از ۲۴ ساعت",
                    "ar": "أقل من ٢٤ ساعة",
                },
            },
            {
                "value": "one_to_two_days",
                "label": {
                    "en": "1–2 days",
                    "fa": "۱ تا ۲ روز",
                    "ar": "يوم إلى يومين",
                },
            },
            {
                "value": "more_than_two_days",
                "label": {
                    "en": "More than 2 days",
                    "fa": "بیشتر از ۲ روز",
                    "ar": "أكثر من يومين",
                },
            },
            {
                "value": "unknown",
                "label": {
                    "en": "I'm not sure",
                    "fa": "مطمئن نیستم",
                    "ar": "لست متأكداً",
                },
            },
        ],
    },
    "hydration_status": {
        "input_type": "single_choice",
        "text": {
            "en": "Is your child drinking fluids and urinating as usual?",
            "fa": "آیا کودک مثل همیشه مایعات می‌نوشد و ادرار می‌کند؟",
            "ar": "هل يشرب طفلك السوائل ويتبول كالمعتاد؟",
        },
        "options": [
            {
                "value": "usual",
                "label": {
                    "en": "Drinking and urinating as usual",
                    "fa": "نوشیدن مایعات و ادرار مثل همیشه است",
                    "ar": "يشرب ويتبول كالمعتاد",
                },
            },
            {
                "value": "less_than_usual",
                "label": {
                    "en": "Drinking less than usual",
                    "fa": "کمتر از معمول مایعات می‌نوشد",
                    "ar": "يشرب سوائل أقل من المعتاد",
                },
            },
            {
                "value": "very_little_or_none",
                "label": {
                    "en": "Not drinking or passing much less urine",
                    "fa": "مایعات نمی‌نوشد یا ادرارش بسیار کمتر شده است",
                    "ar": "لا يشرب أو أصبح التبول أقل بكثير",
                },
            },
            {
                "value": "unknown",
                "label": {
                    "en": "I'm not sure",
                    "fa": "مطمئن نیستم",
                    "ar": "لست متأكداً",
                },
            },
        ],
    },
}

_DURATION_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:hours?|days?|weeks?)\b",
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:hours?|days?|weeks?)\b",
    r"\b(?:since yesterday|since this morning|started today|began today|since last night)\b",
]
_HYDRATION_CONTEXT = re.compile(
    r"\b(drink|drinking|fluids?|water|milk|urine|urinating|urinated|pee|peeing|wee|weeing|wet diapers?|wet napp(?:y|ies)|tears)\b",
    re.IGNORECASE,
)
_DURATION_CONTEXT = re.compile("|".join(f"(?:{p})" for p in _DURATION_PATTERNS), re.IGNORECASE)


# A field can only be PRESENT if extraction found it, ABSENT if the existing
# deterministic extractor explicitly recorded negation, otherwise UNKNOWN.
# Default False values are deliberately never treated as a denial.
def feature_states(text: str, age_months: int | None = None) -> dict[str, str]:
    normalized = normalize_text(text)
    features = extract_clinical_features(
        raw_text=text,
        normalized_text=normalized,
        age_months=age_months,
        feature_assist=None,
    )
    states: dict[str, str] = {}
    negated = set(features.negated_fields or set())
    for item in fields(features):
        name = item.name
        value = getattr(features, name)
        if isinstance(value, FeatureValue):
            if value.present:
                states[name] = "present"
            elif name in negated:
                states[name] = "absent"
            else:
                states[name] = "unknown"
        elif isinstance(value, bool):
            if value:
                states[name] = "present"
            elif name in negated:
                states[name] = "absent"
            else:
                states[name] = "unknown"
    return states


def _duration_is_known(text: str) -> bool:
    return bool(_DURATION_CONTEXT.search(text or ""))


def _hydration_is_mentioned(text: str) -> bool:
    return bool(_HYDRATION_CONTEXT.search(text or ""))


def select_next_question(
    clinical_text: str,
    age_months: int,
    asked_question_ids: list[str] | tuple[str, ...],
) -> dict[str, Any] | None:
    """Return at most one applicable prewritten template; never generate free-form questions."""
    normalized = normalize_text(clinical_text)
    states = feature_states(clinical_text, age_months)
    asked = set(asked_question_ids)

    duration_relevant = any(
        states.get(name) == "present"
        for name in ("has_fever", "diarrhea", "vomiting", "cough", "has_rash", "sore_throat", "headache")
    )
    if duration_relevant and not _duration_is_known(normalized) and "symptom_duration" not in asked:
        return _localized_question("symptom_duration", "en")

    gastrointestinal_symptom_present = (
        states.get("diarrhea") == "present" or states.get("vomiting") == "present"
    )
    if (
        gastrointestinal_symptom_present
        and not _hydration_is_mentioned(normalized)
        and "hydration_status" not in asked
    ):
        return _localized_question("hydration_status", "en")

    return None


def localized_question(question_id: str, language: str) -> dict[str, Any] | None:
    return _localized_question(question_id, language)


def _localized_question(question_id: str, language: str) -> dict[str, Any] | None:
    template = QUESTION_BANK.get(question_id)
    if not template:
        return None
    lang = language if language in {"en", "fa", "ar"} else "en"
    return {
        "id": question_id,
        "text": template["text"][lang],
        "input_type": template["input_type"],
        "options": [
            {"value": option["value"], "label": option["label"][lang]}
            for option in template["options"]
        ],
    }


def resolve_option_label(question_id: str, option_value: str, language: str) -> str | None:
    template = QUESTION_BANK.get(question_id)
    if not template:
        return None
    for option in template["options"]:
        if option["value"] == option_value:
            lang = language if language in {"en", "fa", "ar"} else "en"
            return str(option["label"][lang])
    return None


def is_uncertain_answer(question_id: str, answer_value: str | None, answer_text: str) -> bool:
    if answer_value == "unknown":
        return True
    text = normalize_text(answer_text)
    unknown_phrases = (
        "i am not sure", "i'm not sure", "not sure", "i do not know", "i don't know",
        "مطمئن نیستم", "نمی دانم", "نمی‌دانم", "لا اعرف", "لست متأكداً", "لست متأكد",
    )
    return any(phrase in text for phrase in unknown_phrases)


def find_feature_conflicts(segments: list[str], age_months: int) -> list[str]:
    """Detect only explicit present-vs-explicitly-negated conflicts across turns."""
    observed: dict[str, set[str]] = {}
    for segment in segments:
        if not segment or not segment.strip():
            continue
        for feature, state in feature_states(segment, age_months).items():
            if state in {"present", "absent"}:
                observed.setdefault(feature, set()).add(state)
    return sorted(feature for feature, values in observed.items() if len(values) > 1)
