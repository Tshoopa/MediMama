# backend/triage/llm_feature_assist.py

"""Groq LLM feature assist, scoped to 11 ambiguous clinical fields.

Assist-only, never a source of truth: it fills gaps the deterministic
extractor leaves and never overrides a deterministic "present" or an
explicit negation. Fail-open — any error returns an all-"unknown" dict.

Field names match ClinicalFeatures attributes exactly, so the merge layer
needs no translation table.

Anti-hallucination: every present/absent claim must include an
evidence_quote that is an actual substring of the parent's message;
ungrounded claims are downgraded to "unknown".
"""

import json
import re

from backend.triage.safety_config import (
    get_groq_api_key,
    get_groq_base_url,
    get_groq_model,
    get_llm_debug,
    get_llm_timeout_seconds,
    llm_feature_assist_enabled,
)


# 6 rich FeatureValue fields + 5 negation-prone booleans.
# dehydration is intentionally excluded — it's a multi-signal score,
# too sensitive to leave to an LLM guess.
ASSIST_FIELDS = [
    "hives",
    "burn",
    "fall_from_height",
    "deep_wound",
    "animal_bite",
    "foreign_body_nose",
    "has_fever",
    "breathing_difficulty",
    "vomiting",
    "lethargic",
    "has_rash",
]

_FIELD_DEFINITIONS = """
- hives: itchy raised welts/bumps on the skin (NOT the same as a flat rash)
- burn: skin injury from heat, hot liquid/object, or chemical (redness, blister)
- fall_from_height: fell from a bed, stairs, furniture, playground equipment, etc.
- deep_wound: a cut/laceration/puncture that looks deep or may need stitches
- animal_bite: bitten or stung by an animal or insect (dog, cat, snake, bee, spider, etc.)
- foreign_body_nose: an object stuck/lodged inside the nose
- has_fever: caregiver reports fever or elevated temperature (word or numeric temp)
- breathing_difficulty: labored/fast/noisy breathing, wheeze, chest retractions, struggling to breathe
- vomiting: throwing up / vomited
- lethargic: unusually tired, sluggish, low-energy, hard to engage compared to normal
- has_rash: a skin rash, spots, or discoloration (flat — NOT raised welts, see hives)
"""

_SYSTEM_PROMPT = f"""You are a pediatric triage FEATURE ASSIST reviewer.

Task: For each of the fields below, decide if the parent's message
supports "present", "absent", or "unknown" (not mentioned / not clear).
Do not diagnose. Do not give advice. Only report what the text supports.

Fields:
{_FIELD_DEFINITIONS}

Rules:
- "present" requires a direct textual basis. Include an evidence_quote
  that is an EXACT substring copied from the parent's message.
- "absent" requires explicit negation in the text (e.g. "no fever",
  "not vomiting", "breathing is fine"). Put the exact negation phrase in
  evidence_quote.
- If a field is not mentioned or is ambiguous, use "unknown" and set
  evidence_quote to "".
- Do NOT infer "present" from a merely related symptom. Example: "red
  cheeks" alone does NOT make has_rash present.
- Distinguish hives (raised itchy welts) from has_rash (flat rash/spots).
- Never contradict an explicit negation found in the text.
- confidence: "high" = explicit/unambiguous, "medium" = fairly clear but
  indirect, "low" = weak/inferred.

Return ONLY a JSON object whose keys are exactly the field names listed
above, each mapping to an object with "state", "evidence_quote",
"confidence". No extra text, no extra keys.

Example shape:
{{
  "hives": {{"state": "unknown", "evidence_quote": "", "confidence": "low"}},
  "burn": {{"state": "present", "evidence_quote": "touched the hot pan", "confidence": "high"}}
}}
"""


def _build_user_prompt(text: str, age_months: int | None) -> str:
    age = f"{age_months} months old" if age_months is not None else "unknown"
    return f"age_months: {age}\nparent_message: {text}"


def _empty_result() -> dict:
    return {
        field: {"state": "unknown", "evidence_quote": "", "confidence": "low"}
        for field in ASSIST_FIELDS
    }


def _extract_json_block(raw: str) -> dict | None:
    if not raw:
        return None

    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Fallback: grab the first {...} block if the model wrapped it in prose.
    try:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    return None


def _is_grounded(text: str, quote: str) -> bool:
    if not quote or not quote.strip():
        return False
    return quote.strip().lower() in (text or "").lower()


def _sanitize_result(raw: str, text: str) -> dict:
    """Field-by-field parse and validation. Missing, malformed, or ungrounded
    entries are downgraded to "unknown" — fail-open at the field level."""
    result = _empty_result()

    data = _extract_json_block(raw)
    if not isinstance(data, dict):
        return result

    for field in ASSIST_FIELDS:
        entry = data.get(field)
        if not isinstance(entry, dict):
            continue

        state = entry.get("state")
        quote = entry.get("evidence_quote", "") or ""
        confidence = entry.get("confidence", "low")

        if state not in {"present", "absent", "unknown"}:
            continue
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"

        # Downgrade ungrounded present/absent claims to unknown.
        if state in {"present", "absent"} and not _is_grounded(text, quote):
            state, quote, confidence = "unknown", "", "low"

        result[field] = {"state": state, "evidence_quote": quote, "confidence": confidence}

    return result


def assess_feature_assist(text: str, age_months: int | None = None) -> dict:
    """Return {field -> {state, evidence_quote, confidence}} for the 11 fields.

    Fail-open: any error (missing key, timeout, API/parse failure) returns an
    all-"unknown" dict, which the merge layer treats as "no assist".
    """
    if not llm_feature_assist_enabled() or not text or not text.strip():
        return _empty_result()

    api_key = get_groq_api_key()
    debug = get_llm_debug()

    if not api_key:
        if debug:
            print("[LLM Feature Assist] Missing GROQ_API_KEY")
        return _empty_result()

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=get_groq_base_url(),
            timeout=get_llm_timeout_seconds(),
        )

        response = client.chat.completions.create(
            model=get_groq_model(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(text, age_months)},
            ],
            temperature=0.0,
            max_tokens=500,
        )

        raw = response.choices[0].message.content or ""
        result = _sanitize_result(raw, text)

        if debug:
            print("[LLM Feature Assist] model:", get_groq_model())
            print("[LLM Feature Assist] raw:", raw)
            print("[LLM Feature Assist] sanitized:", result)

        return result

    except Exception as e:
        if debug:
            print("[LLM Feature Assist] Groq error:", repr(e))
        return _empty_result()