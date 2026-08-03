# backend/triage/safety_config.py

"""Environment-driven configuration for the LLM safety net and feature assist.

Both LLM layers are escalation-only and fail open: on any failure the safety
net returns L5 and feature assist returns an all-"unknown" dict, so the
deterministic base result is never made worse by an LLM error.
"""

import os


def llm_safety_net_enabled() -> bool:
    return os.getenv("LLM_SAFETY_NET", "1") == "1"


def get_groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def get_groq_base_url() -> str:
    return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()


def get_groq_model() -> str:
    # llama-3.1-8b-instant: fast, usually enough for safety-net review.
    # llama-3.3-70b-versatile: stronger but slower / tighter rate limits.
    return os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()


def get_llm_timeout_seconds() -> float:
    return float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))


def get_llm_debug() -> bool:
    return os.getenv("LLM_DEBUG", "0") == "1"


def get_llm_only_if_base_level_greater_than() -> int:
    """Legacy skip threshold (default 2): skip the LLM for base L1/L2, call it
    for L3-L5. The deterministic Critical L1 overrides in engine.py run before
    this skip, so hard emergencies still escalate without an LLM call."""
    return int(os.getenv("LLM_ONLY_IF_BASE_LEVEL_GREATER_THAN", "2"))


def fallback_floor_enabled() -> bool:
    """Conservative floor: when no JSON rule matches and the fallback
    classifier is over-lenient, engine.py may raise symptomatic cases to L3/L4."""
    return os.getenv("FALLBACK_FLOOR_ENABLED", "1") == "1"


def llm_feature_assist_enabled() -> bool:
    """Master switch for the feature-assist call, independent from the safety
    net so either can be disabled alone (useful when isolating eval issues)."""
    return os.getenv("LLM_FEATURE_ASSIST", "1") == "1"


def eager_safety_net_enabled() -> bool:
    """When "1" (default), start the safety-net call right after normalize, in
    parallel with feature assist and rule evaluation — its result is usually
    ready when needed (~0 added latency), at the cost of an occasionally
    wasted Groq call for L1/L2 cases. When "0", run strictly sequentially and
    only call it if the base level requires it."""
    return os.getenv("EAGER_SAFETY_NET", "1") == "1"


# Fail-open level. On LLM failure the safety net returns L5; the engine's
# fail-safe adjustment treats a higher-than-base level as a candidate
# de-escalation bounded by safe limits, so a failed call never over-escalates.
LLM_FAILOPEN_LEVEL = 5