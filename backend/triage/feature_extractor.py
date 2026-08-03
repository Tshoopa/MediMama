# backend/triage/feature_extractor.py

"""
Backward-compatible wrapper.

The real slim extractor lives in:
backend/triage/extract_clinical_features.py
"""

from backend.triage.extract_clinical_features import (
    extract_clinical_features,
    extract_temperature,
)