# backend/triage/llm_orchestrator.py

"""Orchestrates the two LLM calls (feature assist + safety net) with an
"eager-fire, conditional-await" strategy.

Why a shared long-lived executor instead of `with ThreadPoolExecutor()`:
a context-manager executor blocks on exit until every submitted future
finishes — including ones we no longer care about — which would defeat
the point of firing the safety net early and only awaiting it if needed.
Here, submit() returns immediately and we only block on the futures we
actually decide to read.

Cost/latency trade-off:
- EAGER_SAFETY_NET=1 (default): the safety-net call starts right after
  normalize, in parallel with feature assist and rule evaluation. When the
  rule engine resolves to L1/L2 and doesn't need it, the call still
  completes and spends a Groq request — no added wall-clock latency, but
  real API cost.
- EAGER_SAFETY_NET=0: strictly sequential (skip-if-not-needed), the
  original cost-saving behavior.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from backend.triage.llm_feature_assist import assess_feature_assist
from backend.triage.llm_safety_net import assess_safety_net
from backend.triage.safety_config import LLM_FAILOPEN_LEVEL, eager_safety_net_enabled


# One shared executor for the whole process so submit() never blocks the
# caller. Each in-flight request uses at most 2 workers (feature assist +
# safety net), so 8 workers supports several concurrent requests.
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm-layer")


@dataclass
class LLMLayerHandle:
    text: str
    age_months: int | None
    feature_assist_future: Future
    safety_net_future: Future | None  # None = not started eagerly


def start_llm_layer(text: str, age_months: int | None = None) -> LLMLayerHandle:
    """Fire the LLM calls as early as possible, right after normalize.

    Feature assist always starts eagerly (feature extraction needs it
    regardless of triage level). Safety net starts eagerly only when
    EAGER_SAFETY_NET is enabled; otherwise it's deferred to
    resolve_safety_net().
    """
    feature_future = _EXECUTOR.submit(assess_feature_assist, text, age_months)

    safety_future: Future | None = None
    if eager_safety_net_enabled():
        safety_future = _EXECUTOR.submit(assess_safety_net, text, age_months)

    return LLMLayerHandle(
        text=text,
        age_months=age_months,
        feature_assist_future=feature_future,
        safety_net_future=safety_future,
    )


def resolve_feature_assist(handle: LLMLayerHandle) -> dict[str, Any]:
    """Block until feature assist is ready. assess_feature_assist() fails
    open internally, but we guard here too in case the future itself errored."""
    try:
        return handle.feature_assist_future.result()
    except Exception as e:
        print(f"[llm_orchestrator] feature assist future error: {repr(e)}")
        from backend.triage.llm_feature_assist import _empty_result
        return _empty_result()


def resolve_safety_net(handle: LLMLayerHandle) -> Any:
    """Return the LLM's suspected level, reason, and confidence.

    Eager path: the call was already started after normalize and has likely
    finished by now -> near-zero added latency. Lazy path: start it now and
    block, matching the original sequential behavior.
    
    Returns Any (expected to be a 3-tuple: level, reason, confidence)
    so engine.py can unpack it safely.
    """
    if handle.safety_net_future is not None:
        try:
            return handle.safety_net_future.result()
        except Exception as e:
            print(f"[llm_orchestrator] safety net future error: {repr(e)}")
            return LLM_FAILOPEN_LEVEL

    try:
        return assess_safety_net(handle.text, handle.age_months)
    except Exception as e:
        print(f"[llm_orchestrator] safety net lazy error: {repr(e)}")
        return LLM_FAILOPEN_LEVEL