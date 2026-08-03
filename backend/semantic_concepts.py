# backend/semantic_concepts.py

"""Semantic concept detection for retrieval hints.

This layer is non-critical: it must never crash /ask, and it fails open
(returns empty / no hint) on any error. It runs on CPU by default so its
CUDA context can't collide with the local llama.cpp model in Colab.
"""

import os
from functools import lru_cache
from typing import Any

# Must be set before torch / sentence-transformers import. When the semantic
# device is CPU, we hide CUDA from this module entirely.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from backend.config import settings

if str(settings.semantic_device).lower() == "cpu":
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import torch
from sentence_transformers import SentenceTransformer, util


# Each concept: example phrasings (exemplars), a retrieval hint appended to the
# search query on a match, and an optional minimum triage level (advisory).
CLINICAL_CONCEPTS: dict[str, dict[str, Any]] = {
    "head_injury_fall": {
        "exemplars": [
            "the child fell off the bed onto the floor",
            "baby rolled off the changing table and hit their head",
            "toddler tumbled down and has a bump on the head",
            "child fell from a height and hit their head on the ground",
        ],
        "retrieval_hint": "head injury fall bump concussion assessment",
        "min_emergency_level": None,
    },
    "severe_dehydration": {
        "exemplars": [
            "the baby is not producing wet diapers or urine",
            "child has had many episodes of watery diarrhea today",
            "baby has sunken eyes, dry mouth, and no tears when crying",
            "child seems very lethargic after vomiting and diarrhea",
        ],
        "retrieval_hint": "dehydration diarrhea gastroenteritis fluid loss",
        "min_emergency_level": 2,
    },
    "anaphylaxis": {
        "exemplars": [
            "child's lips and face are swelling after eating a food",
            "child is having trouble breathing after an allergic exposure",
            "throat feels tight and child is wheezing after a bee sting",
        ],
        "retrieval_hint": "anaphylaxis allergic reaction emergency epipen",
        "min_emergency_level": 2,
    },
    "meningitis_signs": {
        "exemplars": [
            "child has a rash that does not fade when pressed with a glass",
            "baby has a stiff neck, high fever, and is very drowsy",
            "purple spots on the skin that do not disappear under pressure",
        ],
        "retrieval_hint": "meningococcal rash non-blanching emergency",
        "min_emergency_level": 1,
    },
    "respiratory_distress": {
        "exemplars": [
            "child is breathing very fast with chest pulling in",
            "baby's lips are turning blue and struggling to breathe",
            "child has a barking cough and harsh noise when breathing in",
        ],
        "retrieval_hint": "respiratory distress stridor croup breathing emergency",
        "min_emergency_level": 2,
    },
    "battery_ingestion": {
        "exemplars": [
            "child swallowed a small button battery from a toy",
            "toddler may have eaten a coin-shaped battery",
        ],
        "retrieval_hint": "button battery ingestion swallowed emergency",
        "min_emergency_level": 1,
    },
}


def _device() -> str:
    """Return the semantic device, defaulting to CPU. Keeping this off the GPU
    avoids CUDA "invalid argument" errors in Colab/FastAPI threadpools."""
    configured = str(settings.semantic_device or "cpu").lower().strip()
    return configured or "cpu"


@lru_cache(maxsize=1)
def _get_encoder() -> SentenceTransformer | None:
    """Lazy-load the encoder once. Returns None (never raises) on failure so
    the pipeline can continue without semantic hints."""
    try:
        model_name = settings.semantic_embedding_model
        device = _device()
        print(f"[semantic_concepts] loading encoder {model_name} on {device}")
        encoder = SentenceTransformer(model_name, device=device)
        encoder.eval()
        return encoder
    except Exception as e:
        print("[semantic_concepts] encoder load failed; disabled:", repr(e))
        return None


@lru_cache(maxsize=1)
def _get_concept_embeddings() -> dict[str, Any]:
    """Precompute and cache normalized concept embeddings on CPU. Returns {} on
    any failure."""
    encoder = _get_encoder()
    if encoder is None:
        return {}

    device = _device()
    try:
        with torch.inference_mode():
            return {
                name: encoder.encode(
                    data["exemplars"],
                    convert_to_tensor=True,
                    device=device,
                    normalize_embeddings=True,
                ).cpu()
                for name, data in CLINICAL_CONCEPTS.items()
            }
    except Exception as e:
        print("[semantic_concepts] concept embedding build failed:", repr(e))
        return {}


def detect_concepts(symptoms_en: str, top_k: int = 3) -> list[tuple[str, float]]:
    """Return the top-k (concept, similarity) pairs above the configured
    threshold. Fails open: returns [] on empty input or any error."""
    if not symptoms_en or not symptoms_en.strip():
        return []

    encoder = _get_encoder()
    concept_embeddings = _get_concept_embeddings()
    if encoder is None or not concept_embeddings:
        return []

    device = _device()
    try:
        with torch.inference_mode():
            query_emb = encoder.encode(
                symptoms_en,
                convert_to_tensor=True,
                device=device,
                normalize_embeddings=True,
            ).cpu()

        results = [
            (name, round(float(util.cos_sim(query_emb, embs)[0].max().item()), 3))
            for name, embs in concept_embeddings.items()
        ]
        results.sort(key=lambda x: -x[1])

        threshold = float(settings.semantic_similarity_threshold)
        detected = [(n, s) for n, s in results if s >= threshold]
        return detected[:top_k]

    except Exception as e:
        print("[semantic_concepts] detect_concepts failed:", repr(e))
        return []


def get_retrieval_hint(concept_name: str) -> str:
    try:
        return CLINICAL_CONCEPTS.get(concept_name, {}).get("retrieval_hint", "") or ""
    except Exception:
        return ""


def get_min_emergency_level(concept_name: str):
    try:
        return CLINICAL_CONCEPTS.get(concept_name, {}).get("min_emergency_level")
    except Exception:
        return None