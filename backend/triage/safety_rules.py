# backend/triage/safety_rules.py

from backend.triage.features import ClinicalFeatures, RuleResult
from backend.triage.rule_engine import apply_json_triage_rules


def apply_deterministic_safety_rules(f: ClinicalFeatures) -> RuleResult | None:
    """
    Backward-compatible wrapper.

    قبلاً ruleهای deterministic داخل همین فایل hardcode شده بودند.
    الان ruleها در triage_rules.json هستند و این تابع فقط rule engine را صدا می‌زند.
    """
    return apply_json_triage_rules(f)