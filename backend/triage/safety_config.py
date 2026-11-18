"""Pydantic-backed settings for optional API triage assistants."""

from backend.config import settings


def llm_safety_net_enabled() -> bool:
    return bool(settings.llm_safety_net)


def llm_feature_assist_enabled() -> bool:
    return bool(settings.llm_feature_assist)


def eager_safety_net_enabled() -> bool:
    return bool(settings.eager_safety_net)


def get_llm_timeout_seconds() -> float:
    return float(settings.llm_timeout_seconds)


def get_llm_debug() -> bool:
    return bool(settings.llm_debug)


def get_llm_only_if_base_level_greater_than() -> int:
    return int(settings.llm_only_if_base_level_greater_than)


def fallback_floor_enabled() -> bool:
    return bool(settings.fallback_floor_enabled)


# API failure must never be interpreted as a lower level of care.
LLM_FAILOPEN_LEVEL = 5
