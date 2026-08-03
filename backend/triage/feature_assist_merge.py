# backend/triage/feature_assist_merge.py

"""Merge LLM feature-assist output into deterministically-extracted features.

Escalation-only, mirroring the triage-level safety net. Three guardrails
that are never violated:
  1. A deterministic "present" always wins — assist can't touch it.
  2. An explicit deterministic negation always wins — assist can't flip it.
  3. Assist may only fill a genuine gap: set a field present when the
     deterministic value is falsy, there's no explicit negation, and the
     assist state is "present" with confidence != "low".

Runs inside extract_clinical_features(), after _apply_negation_overrides and
before _recompute_derived_features, so any FeatureValue set here still gets
its severity computed by the normal pipeline.
"""

from backend.triage.features import ClinicalFeatures, FeatureValue
from backend.triage.llm_feature_assist import ASSIST_FIELDS


def _deterministic_is_present(features: ClinicalFeatures, field: str) -> bool:
    # Truthy for bool True and for FeatureValue(present=True) via __bool__.
    return bool(getattr(features, field, None))


def _has_explicit_negation(features: ClinicalFeatures, field: str) -> bool:
    return field in (getattr(features, "negated_fields", None) or set())


def _set_present_from_assist(features: ClinicalFeatures, field: str, evidence_quote: str) -> None:
    """Mark a field present. Severity is left as-is so the downstream
    _compute_*_severity() functions assign it later. Source is tagged for audit."""
    current = getattr(features, field, None)

    if isinstance(current, FeatureValue):
        current.present = True
        current.modifiers = {
            **(current.modifiers or {}),
            "source": "llm_feature_assist",
            "evidence_quote": evidence_quote,
        }
    else:
        setattr(features, field, True)


def merge_feature_assist(features: ClinicalFeatures, assist: dict) -> ClinicalFeatures:
    """Fill only the gaps the deterministic extractor left, subject to the
    three guardrails above. Mutates and returns `features`."""
    if not assist:
        return features

    for field in ASSIST_FIELDS:
        # Config drift must never crash triage — skip unknown fields silently.
        if not hasattr(features, field):
            continue

        entry = assist.get(field)
        if not isinstance(entry, dict):
            continue

        state = entry.get("state")
        confidence = entry.get("confidence", "low")
        quote = entry.get("evidence_quote", "") or ""

        # Only a confident "present" can fill a gap.
        if state != "present" or confidence == "low":
            continue
        if _deterministic_is_present(features, field):
            continue
        if _has_explicit_negation(features, field):
            continue

        _set_present_from_assist(features, field, quote)

    return features