# backend/triage/semantic_feature_detector.py

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer, util

from backend.triage.features import ClinicalFeatures, FeatureValue


CONCEPTS_PATH = Path(__file__).resolve().parent / "triage_semantic_concepts.json"


@lru_cache(maxsize=1)
def _load_concept_data() -> dict[str, Any]:
    with CONCEPTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _get_encoder() -> SentenceTransformer:
    model_name = _load_concept_data().get("model", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def _get_concept_embeddings() -> dict[str, Any]:
    encoder = _get_encoder()
    output: dict[str, Any] = {}

    for concept in _load_concept_data().get("concepts", []):
        concept_id = concept.get("id")
        exemplars = concept.get("exemplars", [])
        if not concept_id or not exemplars:
            continue
        output[concept_id] = {
            "concept": concept,
            "embeddings": encoder.encode(exemplars, convert_to_tensor=True),
        }

    return output


def _blocked_by_negative_pattern(text: str, patterns: list[str]) -> bool:
    """True if any concept-specific hard-negative pattern matches, in which
    case the concept is skipped regardless of similarity."""
    for pattern in patterns or []:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except re.error:
            pass
    return False


def _safe_set_bool_feature(f: ClinicalFeatures, name: str) -> None:
    """Set a bool or FeatureValue field present. Severity is computed later in
    extract_clinical_features. Crashes loudly on unknown/unsupported fields so
    a concept-JSON typo can't become a silent bug."""
    if not hasattr(f, name):
        raise AttributeError(
            f"Unknown ClinicalFeatures field from semantic concept: '{name}'."
        )

    current = getattr(f, name)
    if isinstance(current, FeatureValue):
        current.present = True
    elif isinstance(current, bool):
        setattr(f, name, True)
    else:
        raise TypeError(
            f"Cannot set field '{name}' via set_features (type={type(current).__name__}). "
            f"Only bool and FeatureValue are allowed; use set_values otherwise."
        )


def _safe_set_value(f: ClinicalFeatures, name: str, value: Any) -> None:
    if not hasattr(f, name):
        raise AttributeError(f"Unknown ClinicalFeatures field in set_values: '{name}'.")
    setattr(f, name, value)


def apply_semantic_feature_detection(f: ClinicalFeatures, text: str) -> ClinicalFeatures:
    """Set features (never make triage decisions) by matching the text against
    each concept's exemplars via cosine similarity.

    Safety: this layer can only add feature coverage. It can never clear a
    deterministic red flag — triage_rules.json makes the final decision.
    """
    text = text or ""
    concepts = _load_concept_data().get("concepts", [])
    if not concepts:
        return f

    encoder = _get_encoder()
    query_emb = encoder.encode(text, convert_to_tensor=True)
    concept_embeddings = _get_concept_embeddings()

    semantic_hits: list[dict[str, Any]] = []

    for concept in concepts:
        concept_id = concept.get("id")
        if not concept_id:
            continue

        item = concept_embeddings.get(concept_id)
        if not item:
            continue

        # Cheap negative-pattern check before the (costlier) similarity.
        if _blocked_by_negative_pattern(text, concept.get("negative_patterns", [])):
            continue

        threshold = float(concept.get("threshold", 0.60))
        score = float(util.cos_sim(query_emb, item["embeddings"])[0].max())
        if score < threshold:
            continue

        features_set = []
        for feature_name in concept.get("set_features", []):
            _safe_set_bool_feature(f, feature_name)
            features_set.append(feature_name)

        values_set = {}
        for feature_name, value in concept.get("set_values", {}).items():
            _safe_set_value(f, feature_name, value)
            values_set[feature_name] = value

        # medical_signal concepts raise the L4 floor.
        if concept.get("medical_signal", False):
            f.mild_medical_symptom = True

        semantic_hits.append({
            "concept": concept_id,
            "score": round(score, 4),
            "threshold": threshold,
            "set_features": features_set,
            "set_values": values_set,
        })

    existing_debug = f.debug if isinstance(f.debug, dict) else {}
    f.debug = {
        **existing_debug,
        "semantic_feature_hits": existing_debug.get("semantic_feature_hits", []) + semantic_hits,
    }

    return f