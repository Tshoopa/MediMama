# backend/triage/semantic_backup.py

"""Legacy semantic layer, now scoped to L4/L5 non-emergency fallback only.

It no longer produces L1/L2 directly — red flags are handled by
semantic_feature_detector.py (which sets features) and triage_rules.json
(which makes the decision). This module only helps separate "mild medical"
(L4) from "routine/trivial" (L5) when nothing else fired.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer, util

from backend.triage.constants import NON_EMERGENCY_THRESHOLD
from backend.triage.features import ClinicalFeatures


NON_EMERGENCY_CONCEPTS = {
    "L4_mild_illness": {
        "exemplars": [
            "mild fever but child is active and eating well",
            "runny nose and mild cough for a few days",
            "earache or pulling at the ear with mild fever",
            "loose stools a few times but drinking well and active",
            "vomited once or twice but keeping down fluids",
            "eczema or itchy red skin patches",
            "fever with a rash but child is otherwise well",
            "constipation with straining but not distressed",
            "eye discharge and stuck-shut eyes in the morning",
            "mild sore throat but able to drink",
            "minor ankle injury but can walk",
        ],
        "level": 4,
    },
    "L5_minor_or_routine": {
        "exemplars": [
            "vomited once and is completely fine now",
            "brief choking on water but breathing normally now",
            "minor nosebleed that stopped quickly",
            "trivial bump on the head while running, now playing",
            "small cut or graze that can be managed at home",
            "reflux and spitting up but gaining weight",
            "sleep problems, feeding advice, or development questions",
            "general non-medical or parenting question",
            "behaviour, development, feeding, or routine parenting question",
            "teething and otherwise well",
        ],
        "level": 5,
    },
}


@lru_cache(maxsize=1)
def _get_encoder() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2", device="cpu")


@lru_cache(maxsize=1)
def _get_non_emergency_embeddings():
    encoder = _get_encoder()
    return {
        name: encoder.encode(data["exemplars"], convert_to_tensor=True)
        for name, data in NON_EMERGENCY_CONCEPTS.items()
    }


def detect_semantic_red_flag(text: str):
    """Deprecated: always returns None.

    This used to return L1/L2 directly, which caused severe over-triage.
    Red-flag detection now happens via feature extraction, not here.
    """
    return None


def classify_non_emergency(text: str, features: ClinicalFeatures) -> int:
    """Classify a non-emergency case as L4 or L5.

    Safety bias: any real medical symptom stays at L4 (never silently L5).
    L5 is reserved for routine/non-medical or clearly trivial cases.
    """
    if features.routine_or_nonmedical and not features.mild_medical_symptom:
        return 5

    if features.mild_medical_symptom:
        return 4

    encoder = _get_encoder()
    query_emb = encoder.encode(text, convert_to_tensor=True)

    best_level = 4
    best_score = NON_EMERGENCY_THRESHOLD

    for name, embs in _get_non_emergency_embeddings().items():
        max_sim = float(util.cos_sim(query_emb, embs)[0].max())
        if max_sim >= best_score:
            best_score = max_sim
            best_level = NON_EMERGENCY_CONCEPTS[name]["level"]

    # Guard: a mild medical symptom must never end up as L5.
    if best_level > 4 and features.mild_medical_symptom:
        best_level = 4

    return best_level