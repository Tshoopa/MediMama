# backend/safety_checker.py

import re
from typing import Literal


RefusalType = Literal["safety_critical", "medication_misuse", "scope"]


SELF_HARM_OR_VIOLENCE_KEYWORDS = [
    "suicide", "kill myself", "want to die", "self harm", "self-harm",
    "hang myself", "cut myself", "kill him", "kill her", "murder", "abuse",
]

IRRELEVANT_KEYWORDS = [
    "politics", "weather", "recipe", "movie", "sports", "bitcoin",
    "stock market", "football", "election",
]

# If any of these appear, the text is likely a genuine medical question even
# when it also contains an "irrelevant" word (e.g. "fell playing football").
MEDICAL_CONTEXT_KEYWORDS = [
    # Injury / trauma
    "fell", "fall", "fallen", "injury", "injured", "hurt", "pain", "painful",
    "swollen", "swelling", "bleeding", "blood", "broken", "fracture", "sprain",
    "wound", "cut", "bruise", "burn", "hit",
    # Body parts common in injury descriptions
    "wrist", "ankle", "arm", "leg", "head", "neck", "chest", "stomach",
    "belly", "back", "shoulder", "elbow", "knee", "foot", "hand", "finger",
    # General pediatric symptoms
    "fever", "temperature", "vomit", "vomited", "vomiting", "diarrhea",
    "cough", "breathing", "breathe", "wheezing", "rash", "seizure", "choking",
    "unconscious", "unresponsive", "drowsy", "sleepy", "dizzy", "headache",
    "dehydration", "dehydrated", "allergic", "anaphylaxis", "sick", "ill",
    "symptom", "symptoms", "swallowed", "poison", "poisoning",
    # Child context
    "child", "baby", "infant", "toddler", "son", "daughter",
]

# Requests to intentionally give a child adult/prescription medication.
# NOTE: accidental-ingestion descriptions are deliberately NOT here — those
# must flow through to triage, not be refused.
MEDICATION_MISUSE_PATTERNS = [
    "give him my sleeping pill", "give her my sleeping pill",
    "give him my sleeping pills", "give her my sleeping pills",
    "give him my medication", "give her my medication",
    "give him my medicine", "give her my medicine",
    "give my child my medication", "give my child my medicine",
    "adult dose", "adult medicine", "adult medication",
]


def _contains_whole_word(text: str, phrase: str) -> bool:
    """Word-boundary match, so "cut" doesn't match "cute" and "football"
    matches "playing football"."""
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, flags=re.IGNORECASE) is not None


def _has_medical_context(text_lower: str) -> bool:
    return any(_contains_whole_word(text_lower, kw) for kw in MEDICAL_CONTEXT_KEYWORDS)


def is_safe_and_relevant(text_en: str) -> tuple[bool, str, RefusalType | None]:
    """Decide whether a request should continue into the triage pipeline.

    Returns (is_allowed, message, refusal_type). Safety principles:
    - Accidental poisoning/overdose descriptions must reach triage, not be
      blocked here.
    - Self-harm/violence content gets an immediate safety response.
    - Requests to intentionally misuse adult medication are refused.
    - An irrelevant keyword alone doesn't refuse when medical context exists.
    """
    text_lower = (text_en or "").strip().lower()

    if not text_lower:
        return False, "Please describe your child's symptoms or health concern.", "scope"

    # 1. Immediate harm / violence.
    for phrase in SELF_HARM_OR_VIOLENCE_KEYWORDS:
        if _contains_whole_word(text_lower, phrase):
            return False, (
                "This request may involve immediate danger or harm. Please contact "
                "local emergency services or a crisis support service immediately."
            ), "safety_critical"

    # 2. Intentional misuse of adult medication.
    for pattern in MEDICATION_MISUSE_PATTERNS:
        if pattern in text_lower:
            return False, (
                "Never give adult medications, sleeping pills, or prescription drugs "
                "to a child unless a pediatrician, pharmacist, or emergency service has "
                "explicitly instructed you to. Please seek professional medical guidance."
            ), "medication_misuse"

    # 3. Scope check, overridden when medical context is present.
    has_medical_context = _has_medical_context(text_lower)
    for keyword in IRRELEVANT_KEYWORDS:
        if not _contains_whole_word(text_lower, keyword):
            continue
        if has_medical_context:
            print(
                f"[safety_checker] irrelevant keyword '{keyword}' found alongside "
                f"medical context; allowing request through to triage."
            )
            continue
        return False, (
            "I am a pediatric health assistant. Please ask questions related to "
            "children's health."
        ), "scope"

    return True, "Safe", None