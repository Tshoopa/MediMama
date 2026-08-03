# backend/triage/llm_safety_net.py

import json
import os
import re
import time

from backend.triage.safety_config import (
    LLM_FAILOPEN_LEVEL,
    get_groq_api_key,
    get_groq_base_url,
    get_groq_model,
    get_llm_debug,
    get_llm_timeout_seconds,
    llm_safety_net_enabled,
)

_SYSTEM_PROMPT = """You are a warm, highly experienced pediatric triage nurse evaluating a parent's concern.
Your task is to determine the urgency level, write a reassuring explanation of the likely condition, and explain WHY this level of care is needed.

Levels:
1 = Life-threatening emergency (immediate resuscitation needed)
2 = Emergency department evaluation needed now
3 = Urgent same-day medical review (within hours)
4 = Semi-urgent clinic/GP appointment (within 1-2 days)
5 = Non-urgent (home care and routine monitoring)

Instructions for Level Selection:
- Choose L1/L2 only for clear, acute emergencies (e.g., severe breathing distress, unresponsive, button battery, severe fresh burns, anaphylaxis).
- Choose L3 for conditions needing prompt evaluation but not emergency room (e.g., earaches with fever, persistent vomiting, signs of a secondary infection like pus on an old burn, high fever).
- Choose L4 for minor symptomatic illnesses (e.g., mild croupy cough, minor superficial burns, controlled mild bleeding, localized rashes without fever).
- Choose L5 for routine developmental queries, teething, minor spit-ups, or mild cold symptoms where the child is active and well.

Instructions for "clinical_reason":
- Write this reason directly to a worried parent.
- Use a warm, gentle, and empathetic tone.
- Avoid scary clinical jargon (e.g., do not say "cellulitis" or "anaphylaxis"). Instead, say "signs of a possible infection" or "severe allergic reaction".
- Keep it short (maximum 15 words).
- Example: "the burn shows signs of a possible infection, such as pus, which needs a doctor's check today"

Instructions for "why_it_matters":
- Write a short, gentle sentence explaining to a worried parent WHY this level of care is needed.
- Reassure them while being clear and convincing.
- Example for infected burn: "Infections in burns can spread if not treated with antibiotics, so a doctor should look at it today."
- Example for dehydration: "Young children can lose fluids very quickly, so replacing them under medical guidance is important."

Return ONLY a JSON object:
{
  "suspected_level": 1|2|3|4|5,
  "clinical_reason": "warm, parent-friendly explanation in plain English",
  "why_it_matters": "gentle explanation of why this action/urgency is necessary",
  "confidence": "low|medium|high"
}
"""

# Sentinel used to pack reason + why_it_matters into a single string that
# the triage engine later splits back apart for the parent-facing response.
WHY_SEPARATOR = "||WHY||"


def _build_user_prompt(text: str, age_months: int | None) -> str:
    age = f"{age_months} months old" if age_months is not None else "unknown"
    return f"age_months: {age}\nparent_message: {text}"


def _parse_level_and_reason(raw: str) -> tuple[int, str, str, str, bool]:
    """Parse the model's JSON response.

    Returns (level, clinical_reason, why_it_matters, confidence, parsed_ok). 
    Tries strict JSON, then a first-object extraction, then a bare regex for the level.
    """
    default_reason = "clinical safety evaluation"
    default_why = ""
    default_confidence = "low"
    
    if not raw:
        return LLM_FAILOPEN_LEVEL, default_reason, default_why, default_confidence, False

    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()

    # Attempt 1: strict parse.
    try:
        data = json.loads(cleaned)
        lvl = int(data.get("suspected_level", -1))
        reason = data.get("clinical_reason", "").strip()
        why = data.get("why_it_matters", "").strip()
        confidence = str(data.get("confidence", "low")).strip().lower()
        if lvl in {1, 2, 3, 4, 5} and reason:
            return lvl, reason, why, confidence, True
    except Exception:
        pass

    # Attempt 2: extract the first JSON-looking object.
    try:
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            lvl = int(data.get("suspected_level", -1))
            reason = data.get("clinical_reason", "").strip()
            why = data.get("why_it_matters", "").strip()
            confidence = str(data.get("confidence", "low")).strip().lower()
            if lvl in {1, 2, 3, 4, 5} and reason:
                return lvl, reason, why, confidence, True
    except Exception:
        pass

    # Attempt 3: last-resort regex for just the level.
    try:
        match = re.search(r"suspected_level[\"'\s:]*([1-5])", cleaned, re.I)
        if match:
            return int(match.group(1)), default_reason, default_why, default_confidence, True
    except Exception:
        pass

    return LLM_FAILOPEN_LEVEL, default_reason, default_why, default_confidence, False


def _looks_truncated(raw: str) -> bool:
    if not raw:
        return True
    s = raw.strip()
    return (s.startswith("{") and not s.endswith("}")) or s.count("{") > s.count("}")


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _postprocess_level(raw_json_text: str, level: int, text: str, age_months: int | None) -> int:
    """Guard against a few known LLM failure modes before returning a level."""
    t = (text or "").lower()
    r = (raw_json_text or "").lower()

    # Model hallucinated "button battery" from an unrelated coin mention.
    if level == 1 and "button battery" in r:
        if "battery" not in t and "batteries" not in t and "coin" in t:
            return 5

    # Any fever in an infant under 3 months is at least an ED-level concern.
    if level > 2 and age_months is not None and age_months < 3:
        if _has_any(t, ["fever", "temp", "hot", "warm to touch"]):
            return 2

    # Don't let the model jump to L1 for "fever + altered consciousness"
    # unless the text actually contains hard altered-mental-status signs.
    if level == 1 and ("fever" in t or "temperature" in t):
        if "confusion" in r or "altered" in r or "consciousness" in r:
            hard_ams_terms = [
                "confused", "confusion", "can't recognize", "cannot recognize",
                "unresponsive", "hard to wake", "can't wake", "cannot wake", "won't wake",
            ]
            if not _has_any(t, hard_ams_terms):
                return 5

    return level


def _get_provider_settings() -> tuple[str | None, str, str, str]:
    """Resolve API key / base URL / model, falling back across
    Groq -> DeepSeek -> OpenAI env vars, and derive the provider label."""
    api_key = (
        get_groq_api_key()
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    base_url = (
        get_groq_base_url()
        or os.environ.get("DEEPSEEK_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.deepseek.com"
    )
    model = (
        get_groq_model()
        or os.environ.get("DEEPSEEK_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "deepseek-v4-flash"
    )

    base = base_url.lower()
    if "deepseek" in base:
        provider = "DeepSeek"
    elif "openai" in base:
        provider = "OpenAI"
    else:
        provider = "Groq"

    return api_key, base_url, model, provider


def assess_safety_net(text: str, age_months: int | None = None) -> tuple[int, str, str]:
    """Return (suspected_level, reason, confidence).

    The reason packs clinical_reason and why_it_matters into one string,
    separated by WHY_SEPARATOR. Fails open to (L5, default_reason, low) on any
    error, empty output, truncation, or unparseable response.
    """
    default_reason = "clinical safety evaluation"
    default_confidence = "low"
    
    if not llm_safety_net_enabled() or not text or not text.strip():
        return LLM_FAILOPEN_LEVEL, default_reason, default_confidence

    api_key, base_url, model, provider = _get_provider_settings()
    timeout = get_llm_timeout_seconds() or 20.0
    debug = get_llm_debug()

    if not api_key:
        if debug:
            print("[LLM Safety Net] Missing API key")
        return LLM_FAILOPEN_LEVEL, default_reason, default_confidence

    max_retries = 3
    initial_delay = 1.5

    for attempt in range(max_retries):
        try:
            from openai import OpenAI

            # max_retries=0: we run our own backoff loop below.
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

            request_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(text, age_months)},
                ],
                "temperature": 0.0,
                "max_tokens": 400,
            }

            # Prefer JSON mode; fall back to a plain call if the provider
            # doesn't support response_format.
            try:
                response = client.chat.completions.create(
                    **request_params, response_format={"type": "json_object"}
                )
            except Exception as json_mode_error:
                if debug:
                    print(f"[LLM Safety Net] {provider} json_mode failed: {repr(json_mode_error)}")
                response = client.chat.completions.create(**request_params)

            raw = response.choices[0].message.content or ""

            if debug:
                print(f"[LLM Safety Net] provider: {provider} | model: {model}")
                print(f"[LLM Safety Net] raw: {raw}")

            if not raw.strip() or _looks_truncated(raw):
                if attempt < max_retries - 1:
                    time.sleep(initial_delay * (2 ** attempt))
                    continue
                return LLM_FAILOPEN_LEVEL, default_reason, default_confidence

            level, reason, why, confidence, parsed_ok = _parse_level_and_reason(raw)

            if not parsed_ok:
                if attempt < max_retries - 1:
                    time.sleep(initial_delay * (2 ** attempt))
                    continue
                return LLM_FAILOPEN_LEVEL, default_reason, default_confidence

            level = _postprocess_level(raw, level, text, age_months)

            if debug:
                print(f"[LLM Safety Net] final level: {level} | reason: {reason} | why: {why} | conf: {confidence}")

            combined_reason = f"{reason} {WHY_SEPARATOR} {why}" if why else reason
            return level, combined_reason, confidence

        except Exception as e:
            if debug:
                print(f"[LLM Safety Net] error on attempt {attempt + 1}: {repr(e)}")
            if attempt < max_retries - 1:
                time.sleep(initial_delay * (2 ** attempt))
                continue
            break

    return LLM_FAILOPEN_LEVEL, default_reason, default_confidence