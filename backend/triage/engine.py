# backend/triage/engine.py

import re
from typing import Any

from backend.triage.constants import LABELS
from backend.triage.evidence import evaluate_rag_evidence
from backend.triage.extract_clinical_features import extract_clinical_features
from backend.triage.features import ClinicalFeatures, RuleResult
from backend.triage.normalizer import normalize_text
from backend.triage.rule_engine import apply_json_triage_rules
from backend.triage.semantic_backup import classify_non_emergency

from backend.triage.llm_orchestrator import (
    LLMLayerHandle,
    resolve_feature_assist,
    resolve_safety_net,
    start_llm_layer,
)
from backend.triage.safety_config import (
    get_llm_only_if_base_level_greater_than,
    llm_safety_net_enabled,
)


def _result(
    level: int,
    reason: str,
) -> RuleResult:
    """Clamp to the valid triage range and build a RuleResult."""
    level = max(1, min(5, level))
    title, message = LABELS[level]

    return RuleResult(
        level=level,
        title=title,
        message=message,
        reason=reason,
    )


def _coerce_to_rule_result(
    value: Any,
    default_reason: str = "triage decision",
) -> RuleResult | None:
    if value is None:
        return None

    if isinstance(value, RuleResult):
        return value

    if hasattr(value, "level"):
        return _result(
            int(value.level),
            getattr(value, "reason", default_reason),
        )

    if isinstance(value, tuple) and len(value) >= 1:
        return _result(
            int(value[0]),
            default_reason,
        )

    if isinstance(value, int):
        return _result(value, default_reason)

    raise TypeError(
        f"Unsupported triage result type: {type(value)}"
    )


def _has_any(
    text: str,
    terms: list[str],
) -> bool:
    return any(term in text for term in terms)


def _normalize_for_matching(text: str) -> str:
    t = re.sub(
        r"\s+",
        " ",
        (text or "").lower(),
    ).strip()

    t = t.replace("-", " ")
    t = t.replace("underwater", "under water")
    t = t.replace("nosebleed", "nose bleed")

    return t


def _critical_l1_override_reason(
    text: str,
    age_months: int | None,
) -> str | None:
    """Hard L1 floor: only for unambiguous life-threatening red flags."""
    t = _normalize_for_matching(text)

    if _has_any(
        t,
        [
            "not breathing",
            "stopped breathing",
            "isn't breathing",
            "cannot breathe",
        ],
    ):
        return "not breathing / stopped breathing"

    if _has_any(
        t,
        [
            "blue lips",
            "lips are turning blue",
            "turning blue",
        ],
    ) and _has_any(
        t,
        [
            "silent",
            "no sound",
            "choking",
        ],
    ):
        return "cyanosis with silent airway event"

    if _has_any(
        t,
        [
            "floppy",
            "limp body",
            "very limp",
        ],
    ) and _has_any(
        t,
        [
            "cannot wake",
            "can't wake",
            "hard to wake",
            "won't wake",
            "not responding",
        ],
    ):
        return "floppy child difficult to wake"

    if "button battery" in t:
        return "button battery ingestion"

    return None


def _unpack_safety_net_result(
    llm_res: Any,
) -> tuple[int | None, str, str | None]:
    if llm_res is None:
        return None, "clinical safety evaluation", None

    if isinstance(llm_res, tuple):
        if len(llm_res) >= 3:
            return (
                llm_res[0],
                str(llm_res[1] or "clinical safety evaluation"),
                (str(llm_res[2]).lower() if llm_res[2] else None),
            )
        if len(llm_res) == 2:
            return (
                llm_res[0],
                str(llm_res[1] or "clinical safety evaluation"),
                None,
            )
        if len(llm_res) == 1:
            return (llm_res[0], "clinical safety evaluation", None)

    if hasattr(llm_res, "level"):
        level = getattr(llm_res, "level", None)
        reason = getattr(llm_res, "reason", "clinical safety evaluation")
        confidence = getattr(llm_res, "confidence", None)
        return (
            level,
            str(reason or "clinical safety evaluation"),
            (str(confidence).lower() if confidence else None),
        )

    return (llm_res, "clinical safety evaluation", None)


def _apply_safety_net(
    base_result: RuleResult,
    text: str,
    age_months: int | None,
    decision_source: str,
    llm_handle: LLMLayerHandle,
) -> tuple[RuleResult, dict]:
    audit = {
        "base_level": base_result.level,
        "llm_level": None,
        "llm_confidence": None,
        "final_level": base_result.level,
        "adjusted": False,
        "called": False,
        "critical_override": None,
        "decision_source": decision_source,
    }

    # 1. Hard L1 check
    critical_reason = _critical_l1_override_reason(text, age_months)
    if critical_reason:
        audit["critical_override"] = critical_reason
        return _result(1, critical_reason), audit

    if base_result.level == 1:
        audit["skipped_reason"] = "base_is_L1_hard_floor"
        return base_result, audit

    if not llm_safety_net_enabled():
        audit["skipped_reason"] = "llm_disabled"
        return base_result, audit

    # 2. Get LLM recommendation
    audit["called"] = True
    llm_res = resolve_safety_net(llm_handle)
    llm_level, llm_reason, llm_confidence = _unpack_safety_net_result(llm_res)

    if llm_level is None:
        audit["skipped_reason"] = "llm_no_result"
        audit["final_level"] = base_result.level
        return base_result, audit

    llm_level = max(1, min(5, int(llm_level)))
    audit["llm_level"] = llm_level
    audit["llm_confidence"] = llm_confidence

    is_high_confidence = llm_confidence == "high"

    # 3. Decision Logic
    
    # A) Escalation (LLM says more urgent) -> Always Trust LLM
    if llm_level < base_result.level:
        audit["adjusted"] = True
        audit["final_level"] = llm_level
        return _result(llm_level, llm_reason), audit

    # B) Agreement -> Use base level, but keep LLM reason
    if llm_level == base_result.level:
        audit["final_level"] = base_result.level
        return _result(base_result.level, llm_reason), audit

    # C) De-escalation (LLM says less urgent)
    
    # Define Safe Floors
    # If base rule triggered L2 (Emergency), we need to be careful.
    if base_result.level == 2:
        if is_high_confidence:
            # If the LLM is HIGHLY confident that this is NOT an emergency (e.g. pink eye, minor sprain)
            # we allow it to downgrade fully to what it proposed. 
            safe_floor = 5
        else:
            # If not highly confident, we don't let it drop past Urgent (L3)
            safe_floor = 3
    else:
        safe_floor = 5

    if is_high_confidence:
        proposed = min(llm_level, safe_floor)
    else:
        one_step_down = base_result.level + 1
        proposed = min(llm_level, one_step_down, safe_floor)

    proposed = max(1, min(5, proposed))

    if proposed != base_result.level:
        audit["adjusted"] = True
        audit["final_level"] = proposed
        return _result(proposed, llm_reason), audit

    audit["final_level"] = base_result.level
    return _result(base_result.level, llm_reason), audit


def assess(
    text: str,
    age_months: int | None = None,
    citations=None,
    return_debug: bool = False,
):
    normalized = normalize_text(text)

    llm_handle = start_llm_layer(text, age_months)
    feature_assist = resolve_feature_assist(llm_handle)

    features: ClinicalFeatures = extract_clinical_features(
        raw_text=text,
        normalized_text=normalized,
        age_months=age_months,
        feature_assist=feature_assist,
    )

    rule_result = _coerce_to_rule_result(
        apply_json_triage_rules(features), "triage rule"
    )

    rag_result = _coerce_to_rule_result(
        evaluate_rag_evidence(citations) if citations else None, "rag evidence escalation"
    )

    fallback = _result(
        classify_non_emergency(normalized, features), "clinical safety evaluation"
    )

    if rule_result is not None:
        candidate, source = rule_result, "triage_rules"
    elif rag_result is not None:
        candidate, source = rag_result, "rag_evidence"
    else:
        candidate, source = fallback, "fallback_classifier"

    print(
        "[TRIAGE TRACE] "
        f"rule_level={rule_result.level if rule_result else None} | "
        f"rag_level={rag_result.level if rag_result else None} | "
        f"fallback_level={fallback.level} | "
        f"candidate_level={candidate.level} | "
        f"source={source}"
    )

    final_result, safety_audit = _apply_safety_net(
        candidate, text, age_months, decision_source=source, llm_handle=llm_handle,
    )

    print(
        "[TRIAGE TRACE] "
        f"base_level={safety_audit['base_level']} | "
        f"llm_level={safety_audit['llm_level']} | "
        f"llm_confidence={safety_audit.get('llm_confidence')} | "
        f"final_level={safety_audit['final_level']} | "
        f"adjusted={safety_audit['adjusted']}"
    )

    if return_debug:
        return {
            "result": final_result,
            "normalized": normalized,
            "features": features,
            "feature_assist": feature_assist,
            "decision_source": source,
            "safety_net": safety_audit,
        }

    return final_result