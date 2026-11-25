# backend/main.py

import copy
import logging
import re
import time
from typing import Any
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.audit_logger import log_query
from backend.config import settings
from backend.models import (
    QueryRequest, QueryResponse, ConversationCreateRequest,
    ConversationTurnRequest, ConversationResponse, FollowUpQuestion,
)
from backend.conversation_store import ConversationStore, ConversationState
from backend.triage.clarification_engine import (
    find_feature_conflicts, localized_question, resolve_option_label,
    select_next_question, is_uncertain_answer,
)
from backend.rag.retriever import retrieve
from backend.rag.vector_store import get_client
from backend.response_formatter import format_response
from backend.safety_checker import is_safe_and_relevant
from backend.translation import TranslationError, translate_to_english, translate_to_target
from backend.llm_provider import (
    generate_answer, initialize_generation_backend, generation_backend_status,
)
from backend.triage.engine import assess
from backend.triage.llm_safety_net import WHY_SEPARATOR
from backend.verification import verify_answer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("medimama")


app = FastAPI(title="MediMama API", version="5.4.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["Content-Type", "ngrok-skip-browser-warning"],
)

# ── Resource loading ──────────────────────────────────────────────

try:
    _qdrant = get_client()
    log.info("Qdrant client ready (%s).", settings.active_collection_name)
except Exception as exc:
    log.warning("Qdrant unavailable, retrieval disabled: %r", exc)
    _qdrant = None

try:
    initialize_generation_backend()
except Exception as exc:
    # Keep the API process available for health checks and deterministic
    # emergency responses. Readiness will report the generation backend error.
    log.warning("Generation backend is not ready; deterministic fallback only: %r", exc)


# ── Constants ─────────────────────────────────────────────────────

STOP_TOKENS = [
    "###", "\n\n\n", "\nQuestion:", "\nMedical Evidence:",
    "[/SYS]", "<</SYS>>", "<s>", "</s>", "[INST]", "[/INST]",
    "### Instruction:", "### Input:", "### Response:",
    "Source 1:", "Source 2:", "Source 3:",
    "Parent's Question:", "You are MediMama", "a warm and reassuring",
]

# Text that signals the model dumped research-paper boilerplate instead of
# answering — everything from the first hit onward is truncated.
GARBAGE_INDICATORS = [
    "# Discussion", "# Introduction", "The study also found",
    "The purpose of this study", "The results showed",
]

ANSWER_PREFIXES = [
    "Your final response:", "Final answer:", "Final response:",
    "Answer:", "Clinical Response:", "### Answer:",
]

EXPLICIT_REFUSAL_PHRASES = [
    "do not contain enough information", "cannot answer",
    "not enough information", "i don't have information",
]

# If >=2 of these appear, the model echoed the system prompt instead of
# answering; the output is discarded.
PROMPT_LEAK_INDICATORS = [
    "you are medimama", "warm and reassuring pediatric nurse",
    "using only the facts", "medical evidence", "do not invent",
    "maximum 4 sentences", "maximum 3 sentences", "answer the parent",
    "pediatric nurse", "do not repeat these instructions",
]

CONTEXT_TOP_N = 3

# Arabic script block, shared by Persian and Arabic.
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF]")
# Letters that exist in Persian but not in standard Arabic: پ چ ژ گ ک ی
_PERSIAN_ONLY = re.compile(r"[\u067E\u0686\u0698\u06AF\u06A9\u06CC]")

# Parent-friendly "why it matters" text, keyed by phrases that may appear in
# the triage reason. Used as a fallback when the LLM safety net didn't supply
# its own explanation.
CRITICAL_EMERGENCY_WHY = {
    "button battery": (
        "Button batteries can burn through the throat or gut in as little as "
        "1-2 hours, even if your child seems perfectly fine right now."
    ),
    "magnet": (
        "Swallowed magnets can pull together inside the gut and cause serious "
        "damage quickly, even without symptoms at first."
    ),
    "non-blanching": (
        "A rash that does not fade when pressed can be an early sign of a "
        "serious infection like meningitis, which needs treatment within minutes."
    ),
    "meningococcal": (
        "This type of rash can be an early sign of meningitis, which becomes "
        "dangerous very quickly, so early treatment is vital."
    ),
    "meningitis": (
        "Meningitis can progress very quickly, and early medical assessment and "
        "treatment make a huge difference to recovery."
    ),
    "not breathing": (
        "When breathing stops or is severely restricted, the brain and heart "
        "need oxygen restored immediately."
    ),
    "cyanosis": (
        "Blue lips or skin indicate a severe lack of oxygen, which is a "
        "life-threatening emergency."
    ),
    "anaphylaxis": (
        "A severe allergic reaction can close the airway within minutes, "
        "requiring immediate emergency treatment."
    ),
    "choking": (
        "A blocked airway stops oxygen reaching the lungs, so every second counts."
    ),
    "seizure": (
        "A prolonged seizure needs medication to stop it and protect the brain "
        "from damage."
    ),
    "testicular": (
        "Sudden, severe testicular pain can indicate testicular torsion, which "
        "requires urgent surgery within hours to save the testicle."
    ),
    "hernia": (
        "A strangulated hernia means part of the bowel is trapped and losing "
        "blood supply, which is a surgical emergency."
    ),
    "dka": (
        "Diabetic ketoacidosis (DKA) is a life-threatening complication of "
        "diabetes that requires immediate hospital treatment."
    ),
    "sepsis": (
        "A very young baby with a fever can develop a serious blood infection "
        "quickly, requiring immediate emergency evaluation."
    ),
    "dehydration": (
        "Babies and young children can become dangerously dehydrated very fast, "
        "which can lead to organ damage if not treated."
    ),
    "burn": (
        "Deep or large burns can lead to severe fluid loss and infection, "
        "requiring immediate specialist care."
    ),
    "head injury": (
        "After a significant head injury, doctors need to rule out any bleeding "
        "or swelling inside the skull."
    ),
    "poisoning": (
        "Ingested chemicals or poisons can cause rapid internal damage or "
        "breathing problems, requiring immediate assessment."
    ),
    "medication": (
        "Accidental drug ingestion can affect the heart, breathing, or brain, "
        "making immediate emergency evaluation critical."
    ),
    "animal bite": (
        "Animal bites carry a high risk of rabies or severe bacterial infection, "
        "requiring prompt wound care and assessment."
    ),
    "appendicitis": (
        "Appendicitis can lead to a ruptured appendix, causing a serious "
        "abdominal infection if not treated quickly."
    ),
}


# ── Health endpoints ──────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, Any]:
    """Readiness probe, including the selected generation mode."""
    generation = generation_backend_status()
    ready = _qdrant is not None and bool(generation.get("ready"))
    return {
        "status": "ready" if ready else "degraded",
        "inference_mode": settings.inference_mode,
        "qdrant_available": _qdrant is not None,
        "generation": generation,
        "active_collection": settings.active_collection_name,
        "embedding_backend": settings.active_embedding_backend,
    }


# ── Language detection ────────────────────────────────────────────

def detect_language(text: str, requested: str | None) -> str:
    """Resolve Persian/Arabic from script first, then use the UI selection.

    Persian-specific letters are stronger evidence than a stale UI selection.
    Arabic and Persian share most of the Unicode block, so for ambiguous text
    the requested UI language remains the tie-breaker.
    """
    requested = (requested or "en").lower()
    if _PERSIAN_ONLY.search(text or ""):
        return "fa"
    if _ARABIC_SCRIPT.search(text or ""):
        return requested if requested in {"fa", "ar"} else "ar"
    return requested if requested in {"en", "fa", "ar"} else "en"


# ── Safe wrappers (never crash /ask) ──────────────────────────────

def is_prompt_leak(text: str) -> bool:
    """True if the model echoed >=2 prompt fragments instead of answering."""
    if not text:
        return True
    lowered = text.lower()
    return sum(1 for ind in PROMPT_LEAK_INDICATORS if ind in lowered) >= 2


def safe_translate_to_english(text: str, source_lang: str = "auto") -> str:
    translated = translate_to_english(text, source_lang=source_lang)
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationError("The translation service returned an empty result.")
    return translated


def safe_translate_to_target(text: str, target_lang: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    if not text:
        return ""
    if not target_lang or target_lang == "en":
        return text
    try:
        translated = translate_to_target(text, target_lang)
        return translated if isinstance(translated, str) and translated.strip() else text
    except Exception as exc:
        log.warning("Translation to %s failed: %r", target_lang, exc)
        return text


def safe_log_query(*args: Any, **kwargs: Any) -> None:
    """Audit logging must never turn a valid medical answer into an HTTP 500."""
    try:
        log_query(*args, **kwargs)
    except Exception as exc:
        log.error("Audit logging failed: %r", exc)


def safe_expand(symptoms_en: str) -> str:
    if not settings.enable_query_expansion:
        return symptoms_en
    try:
        from backend.query_expansion import expand
        expanded = expand(symptoms_en)
        return expanded if isinstance(expanded, str) and expanded.strip() else symptoms_en
    except Exception as exc:
        log.warning("Query expansion failed: %r", exc)
        return symptoms_en


def safe_retrieve(query: str) -> list:
    if _qdrant is None:
        log.warning("Qdrant unavailable; returning no citations.")
        return []
    try:
        return retrieve(query, _qdrant) or []
    except Exception as exc:
        log.warning("Retrieval failed: %r", exc)
        return []


def safe_assess(
    symptoms_en: str,
    age_months: int,
    citations: list | None = None,
) -> tuple[int, str, str, str]:
    """Run the triage engine with a conservative fallback: on any internal
    error, return L3 (not L5) so a bug never de-escalates a real case."""
    try:
        result = assess(symptoms_en, age_months, citations=citations or [])
        level = int(result.level)
        if not 1 <= level <= 5:
            raise ValueError(f"invalid triage level from assess: {level}")
        return level, str(result.title), str(result.message), str(result.reason or "")
    except Exception as exc:
        log.error("Triage assessment failed, falling back to L3: %r", exc)
        return 3, "Urgent", "Please seek medical advice today.", "clinical safety evaluation"


# ── Citation handling ─────────────────────────────────────────────

def _get_citation_value(citation: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(citation, dict):
        return citation.get(field_name, default)
    return getattr(citation, field_name, default)


def _translate_citation_field(citation_copy: Any, field_name: str, target_lang: str) -> None:
    """Translate a single translatable field in place, for both dict and
    object citations."""
    value = _get_citation_value(citation_copy, field_name)
    if not (isinstance(value, str) and value.strip()):
        return
    translated = safe_translate_to_target(value, target_lang)
    if isinstance(citation_copy, dict):
        citation_copy[field_name] = translated
    else:
        setattr(citation_copy, field_name, translated)


def translate_citations(citations: list | None, target_lang: str) -> list:
    """Return translated copies of citations without mutating the retrieval
    originals. Falls back to the original citation if a copy/translate fails."""
    if not citations:
        return []
    if not target_lang or target_lang == "en":
        return list(citations)

    translated = []
    for citation in citations:
        try:
            if hasattr(citation, "model_copy"):
                citation_copy = citation.model_copy(deep=True)
            else:
                citation_copy = copy.deepcopy(citation)

            # Prefer "chunk"; fall back to "text" when chunk is absent.
            if _get_citation_value(citation_copy, "chunk"):
                _translate_citation_field(citation_copy, "chunk", target_lang)
            else:
                _translate_citation_field(citation_copy, "text", target_lang)
            _translate_citation_field(citation_copy, "topic", target_lang)

            translated.append(citation_copy)
        except Exception as exc:
            log.warning("Citation translation failed, keeping original: %r", exc)
            translated.append(citation)

    return translated


def filter_citations_for_display(citations: list | None) -> list:
    """Keep only citations at/above the display score threshold, capped at
    max_display_citations."""
    if not citations:
        return []

    max_n = int(settings.max_display_citations)
    threshold = float(settings.min_rerank_score_for_display)

    filtered = []
    for citation in citations:
        try:
            score_raw = _get_citation_value(citation, "score")
            if score_raw is None:
                continue
            if float(score_raw) >= threshold:
                filtered.append(citation)
        except Exception as exc:
            log.warning("Unparseable citation discarded: %r", exc)

    return filtered[:max_n]


def build_context(
    citations: list | None,
    max_chunks: int = CONTEXT_TOP_N,
    max_chars_per_chunk: int = 800,
) -> str:
    """Concatenate the top citation chunks into a numbered evidence block for
    the LLM prompt."""
    if not citations:
        return ""

    parts = []
    for citation in citations[:max_chunks]:
        chunk_text = (
            _get_citation_value(citation, "chunk")
            or _get_citation_value(citation, "text")
            or ""
        )
        if not isinstance(chunk_text, str):
            chunk_text = str(chunk_text)
        chunk_text = chunk_text[:max_chars_per_chunk].strip()
        if chunk_text:
            parts.append(f"Source {len(parts) + 1}:\n{chunk_text}")

    return "\n\n".join(parts)


# ── Text cleaning / processing ────────────────────────────────────

def _split_reason_and_why(clinical_reason: str) -> tuple[str, str]:
    """Split a "reason WHY_SEPARATOR why" string into (reason, why)."""
    if not clinical_reason:
        return "", ""
    if WHY_SEPARATOR in clinical_reason:
        reason, why = clinical_reason.split(WHY_SEPARATOR, 1)
        return reason.strip(), why.strip()
    return clinical_reason.strip(), ""


def _resolve_why(reason_raw: str, why_from_llm: str) -> str:
    """Prefer the LLM's own explanation; otherwise match a canned explanation
    by keyword from CRITICAL_EMERGENCY_WHY."""
    if why_from_llm:
        return why_from_llm
    reason_lower = (reason_raw or "").lower()
    for key, explanation in CRITICAL_EMERGENCY_WHY.items():
        if key in reason_lower:
            return explanation
    return ""


def clean_clinical_reason(reason: str) -> str:
    """Strip internal engineering labels so only parent-facing reason text
    remains (empty string if the reason was purely technical)."""
    if not reason:
        return ""

    technical_noise = {
        "triage rule", "rag evidence",
        "routine developmental or home-care query",
        "fallback_classifier", "clinical safety evaluation",
    }
    if reason.strip().lower() in technical_noise:
        return ""

    return re.sub(
        r"^(Critical L\d override|Fallback floor L\d|LLM Safety Net escalation):\s*",
        "",
        reason,
        flags=re.I,
    ).strip()


def remove_repeated_sentences(text: str) -> str:
    """Drop duplicate sentences repeated by a generative model."""
    seen = set()
    result = []
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        normalized = sentence.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(sentence.strip())
    return " ".join(result)


def truncate_to_core(text: str, max_sentences: int = 4) -> str:
    """Strip citation markers, collapse whitespace, drop trivial sentences,
    and cap the length. Also drops a trailing unfinished short fragment."""
    text = re.sub(r"\(\d+\)", "", text or "")
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    meaningful = [s.strip() for s in sentences if len(s.split()) > 3]

    if meaningful:
        last = meaningful[-1]
        if not re.search(r"[.!?]$", last):
            # Long enough to keep -> punctuate; too short -> drop as a fragment.
            if len(last.split()) > 6:
                meaningful[-1] = last + "."
            else:
                meaningful.pop()

    return " ".join(meaningful[:max_sentences])


def clean_llm_output(text: str) -> str:
    """Full post-processing of raw model output: strip quotes/prefixes/tags,
    reject prompt leaks, cut boilerplate, dedupe, and truncate."""
    text = (text or "").strip().strip('"').strip("'").strip("“").strip("”").strip()

    if is_prompt_leak(text):
        log.warning("Prompt leak detected in LLM output; discarding.")
        return ""

    text = re.sub(r"^(Dear Parent,?\s*)", "", text, flags=re.I).strip()

    for prefix in ANSWER_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    for tag in ["[/SYS]]", "[/SYS]", "<</SYS>>", "[/INST]", "[INST]", "<s>", "</s>"]:
        text = text.replace(tag, "").strip()

    for indicator in GARBAGE_INDICATORS:
        if indicator in text:
            text = text[:text.index(indicator)].strip()

    text = remove_repeated_sentences(text)
    text = truncate_to_core(text, max_sentences=4)

    return text.strip().strip('"').strip("'").strip("“").strip("”").strip()


# ── Deterministic clinical answer ─────────────────────────────────

def deterministic_triage_answer(level: int, clinical_reason: str = "") -> str:
    """Build the warm, parent-facing answer text for a given triage level,
    independent of the local LLM. This is the safety fallback used whenever
    LLM generation is skipped or rejected."""
    level = int(level)
    if not 1 <= level <= 5:
        raise ValueError(f"invalid deterministic triage level: {level}")

    reason_raw, why_from_llm = _split_reason_and_why(clinical_reason)
    reason_clean = clean_clinical_reason(reason_raw)
    why = _resolve_why(reason_raw, why_from_llm)

    if reason_clean:
        reason_clean = reason_clean[0].upper() + reason_clean[1:]

    if level == 1:
        message = (
            "I understand this is very frightening, and you are doing the right "
            "thing by acting quickly. "
        )
        if reason_clean:
            message += (
                f"The symptoms you describe — **{reason_clean}** — need emergency "
                "medical help right now. "
            )
        if why:
            message += f"Here's why this matters: {why} "
        message += (
            "Please call an ambulance (000 / 911) immediately, or if it is faster, "
            "go straight to the nearest emergency department. Stay calm and keep "
            "your child comfortable and upright while help arrives. You are not "
            "alone — emergency teams deal with this every day and know exactly "
            "what to do."
        )
        return message

    if level == 2:
        message = (
            "I know this is worrying, but try to stay calm — you are taking exactly "
            "the right step by checking. "
        )
        if reason_clean:
            message += (
                f"Based on what you describe — **{reason_clean}** — your child "
                "should be seen by a doctor urgently. "
            )
        if why:
            message += f"Here's why it's important not to wait: {why} "
        message += (
            "Please take your child to the nearest emergency department or urgent "
            "care centre now. It is much better to have this checked and be "
            "reassured than to wait at home. Bring any medicines your child takes, "
            "and try to keep them calm and comfortable on the way. The medical team "
            "will assess and care for your child as soon as you arrive."
        )
        return message

    if level == 3:
        message = (
            "This does not sound like an immediate emergency, so please don't panic "
            "— but it is something a doctor should look at today. "
        )
        if reason_clean:
            message += f"This is because of: **{reason_clean}**. "
        if why:
            message += f"{why} "
        message += (
            "Please book a same-day appointment with your GP, or visit an urgent "
            "care clinic today. Keep an eye on your child in the meantime, and if "
            "they suddenly get worse — for example much more unwell, very drowsy, "
            "breathing difficulty, or a rash that doesn't fade — go to the "
            "emergency department straight away."
        )
        return message

    if level == 4:
        message = (
            "Based on what you've described, this is usually not urgent, so you can "
            "relax a little. "
        )
        if reason_clean:
            message += f"This is typical of: **{reason_clean}**. "
        if why:
            message += f"{why} "
        message += (
            "It's a good idea to arrange a routine appointment with your GP or "
            "pharmacist in the next day or two. In the meantime, keep your child "
            "comfortable and watch how they're doing. If symptoms get noticeably "
            "worse or new concerning signs appear, seek care sooner."
        )
        return message

    # level == 5
    message = (
        "The good news is that this sounds like something you can usually manage "
        "safely at home. "
    )
    if reason_clean:
        message += f"This is common and typical of: **{reason_clean}**. "
    if why:
        message += f"{why} "
    message += (
        "Keep your child comfortable, offer plenty of fluids, and give them lots "
        "of reassurance and rest. You know your child best — if they become more "
        "unwell, develop a high fever, or you feel something isn't right, please "
        "don't hesitate to contact your GP or health line for advice."
    )
    return message


# ── Response builders ─────────────────────────────────────────────

def refusal_response(
    req: QueryRequest,
    msg: str,
    detected_lang: str,
    refusal_type: str,
    citations: list | None = None,
) -> QueryResponse:
    """Build a refusal response without secretly assigning L5.

    safety_critical   -> L1 (immediate danger)
    medication_misuse -> no level (ingestion not established)
    scope             -> no level (request was never triaged)
    """
    citations_for_log = list(citations or [])

    if refusal_type == "safety_critical":
        level = 1
        label_en = "Emergency safety warning"
        urgency_en = (
            "Contact local emergency services or an appropriate local crisis "
            "support service immediately."
        )
    elif refusal_type == "medication_misuse":
        level = None
        label_en = "Medication safety warning"
        urgency_en = (
            "Do not give the medication. Contact a pediatrician, pharmacist, "
            "poison information service, or emergency service for guidance."
        )
    else:
        refusal_type = "scope"
        level = None
        label_en = "Not clinically triaged"
        urgency_en = "Please submit a question related to your child's health."

    message_translated = safe_translate_to_target(msg, detected_lang)
    label_translated = safe_translate_to_target(label_en, detected_lang)
    urgency_translated = safe_translate_to_target(urgency_en, detected_lang)

    safe_log_query(
        req.symptoms, detected_lang, req.child_age_months, level,
        citations_for_log, message_translated,
        False, True, refusal_type=refusal_type,
    )

    log.info("Refused (%s) | level=%s", refusal_type, level)

    return QueryResponse(
        answer=message_translated,
        emergency_level=level,
        emergency_label=label_translated,
        citations=[],
        see_doctor_urgency=urgency_translated,
        verified=False,
        refusal=True,
        refusal_type=refusal_type,
    )


def deterministic_response(
    req: QueryRequest,
    detected_lang: str,
    level: int,
    label_en: str,
    urgency_en: str,
    citations_for_log: list | None = None,
    reason: str = "",
    clinical_reason: str = "",
    show_citations: bool = False,
) -> QueryResponse:
    """Build a deterministic (non-LLM) answer. Used for the L1/L2 fast-path and
    for every fallback: no citations, no LLM, generation failure, prompt leak,
    model refusal, or failed grounding verification.

    citations_for_log: original untranslated citations for the audit log.
    show_citations:    whether to translate and surface citations to the user.
    """
    citations_for_log = list(citations_for_log or [])

    try:
        validated_level = int(level)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid deterministic triage level: {level!r}") from exc

    if not 1 <= validated_level <= 5:
        raise ValueError(f"triage level must be 1-5; got {validated_level}.")

    final_label = safe_translate_to_target(label_en, detected_lang)
    final_urgency = safe_translate_to_target(urgency_en, detected_lang)

    answer_en = deterministic_triage_answer(validated_level, clinical_reason)
    final_answer = safe_translate_to_target(answer_en, detected_lang)

    formatted = format_response(final_answer, validated_level, final_label, final_urgency)

    display_citations = (
        translate_citations(citations_for_log, detected_lang)
        if show_citations and citations_for_log
        else []
    )

    safe_log_query(
        req.symptoms, detected_lang, req.child_age_months, validated_level,
        citations_for_log, formatted,
        True, False, refusal_type=None,
    )

    log.info("Deterministic answer L%d | %s", validated_level, reason or "n/a")

    return QueryResponse(
        answer=formatted,
        emergency_level=validated_level,
        emergency_label=final_label,
        citations=display_citations,
        see_doctor_urgency=final_urgency,
        verified=True,
        refusal=False,
        refusal_type=None,
    )


# ── Shared request preflight and answer pipeline ───────────────────

def _prepare_query(req: QueryRequest, force_language: str | None = None) -> dict[str, Any]:
    """Translate, scope-check, and assess once for both /ask and conversations."""
    detected_lang = force_language or detect_language(req.symptoms, req.language)
    try:
        symptoms_en = safe_translate_to_english(req.symptoms, source_lang=detected_lang)
    except TranslationError as exc:
        log.error("Input translation unavailable; refusing to triage: %r", exc)
        return {"kind": "translation_error", "detected_lang": detected_lang}

    try:
        safety_result = is_safe_and_relevant(symptoms_en)
        if not isinstance(safety_result, tuple) or len(safety_result) != 3:
            raise ValueError("is_safe_and_relevant must return (is_safe, message, refusal_type).")
        is_safe, safety_msg, refusal_type = safety_result
    except Exception as exc:
        log.error("Safety checker failed, refusing conservatively: %r", exc)
        return {
            "kind": "refusal",
            "detected_lang": detected_lang,
            "symptoms_en": symptoms_en,
            "message": (
                "I could not safely process this request. If your child may be "
                "seriously unwell or in immediate danger, contact emergency services now."
            ),
            "refusal_type": "safety_critical",
        }

    if not is_safe:
        return {
            "kind": "refusal",
            "detected_lang": detected_lang,
            "symptoms_en": symptoms_en,
            "message": safety_msg,
            "refusal_type": refusal_type or "scope",
        }

    level, label_en, urgency_en, clinical_reason = safe_assess(
        symptoms_en, req.child_age_months, citations=[]
    )
    level = int(level)
    log.info("Triage L%d (%s) | %s", level, label_en, clinical_reason)
    return {
        "kind": "assessment",
        "detected_lang": detected_lang,
        "symptoms_en": symptoms_en,
        "level": level,
        "label_en": label_en,
        "urgency_en": urgency_en,
        "clinical_reason": clinical_reason,
    }


def _process_query(
    req: QueryRequest,
    preflight: dict[str, Any] | None = None,
) -> QueryResponse:
    """Run the legacy evidence/answer pipeline using an optional shared preflight."""
    start_time = time.time()
    log.info("Request | message_chars=%s lang=%s", len(req.symptoms or ""), req.language)
    preflight = preflight or _prepare_query(req)
    detected_lang = str(preflight["detected_lang"])

    if preflight["kind"] == "translation_error":
        localized = {
            "en": "I cannot safely translate this message right now. Please try again shortly. If your child may be seriously unwell, seek urgent medical help.",
            "fa": "در حال حاضر امکان ترجمهٔ مطمئن پیام شما وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید. اگر حال کودک نگران‌کننده است، فوراً کمک پزشکی بگیرید.",
            "ar": "لا يمكنني ترجمة رسالتك بشكل موثوق حالياً. يرجى المحاولة مرة أخرى بعد قليل. إذا كانت حالة طفلك مقلقة، فاطلب المساعدة الطبية العاجلة.",
        }.get(detected_lang, "I cannot safely translate this message right now.")
        localized_label = {
            "en": "Translation unavailable",
            "fa": "ترجمه در دسترس نیست",
            "ar": "الترجمة غير متاحة",
        }.get(detected_lang, "Translation unavailable")
        return QueryResponse(
            answer=localized,
            emergency_level=None,
            emergency_label=localized_label,
            citations=[],
            see_doctor_urgency=localized,
            verified=False,
            refusal=True,
            refusal_type="translation_error",
        )

    if preflight["kind"] == "refusal":
        return refusal_response(
            req=req,
            msg=str(preflight["message"]),
            detected_lang=detected_lang,
            refusal_type=str(preflight["refusal_type"]),
        )

    symptoms_en = str(preflight["symptoms_en"])
    level = int(preflight["level"])
    label_en = str(preflight["label_en"])
    urgency_en = str(preflight["urgency_en"])
    clinical_reason = str(preflight["clinical_reason"])

    # L1/L2 emergency fast-path: skip RAG and answer generation entirely.
    if level <= 2:
        response = deterministic_response(
            req=req,
            detected_lang=detected_lang,
            level=level,
            label_en=label_en,
            urgency_en=urgency_en,
            citations_for_log=[],
            reason=f"emergency fast-path (L{level})",
            clinical_reason=clinical_reason,
            show_citations=False,
        )
        log.info("Emergency response in %.2fs", time.time() - start_time)
        return response

    # Semantic concept hints + retrieval.
    try:
        from backend.semantic_concepts import detect_concepts, get_retrieval_hint
        detected_concepts = detect_concepts(symptoms_en) or []
    except Exception as exc:
        log.warning("Semantic concept detection failed: %r", exc)
        detected_concepts = []

    enriched_query = symptoms_en
    if detected_concepts:
        hints = []
        for item in detected_concepts:
            try:
                concept_name, _score = item
                hint = get_retrieval_hint(concept_name)
                if hint:
                    hints.append(str(hint))
            except Exception as exc:
                log.warning("Invalid semantic concept skipped: %r", exc)
        if hints:
            enriched_query = f"{symptoms_en} (Keywords: {' '.join(hints)})"

    expanded_query = safe_expand(enriched_query)
    citations_raw = safe_retrieve(expanded_query)
    citations = filter_citations_for_display(citations_raw)
    log.info("Retrieved %d raw, %d displayable", len(citations_raw), len(citations))

    if not citations:
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=[], reason="no displayable citations",
            clinical_reason=clinical_reason, show_citations=False,
        )

    context = build_context(citations)
    if not context:
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=citations, reason="empty RAG context",
            clinical_reason=clinical_reason, show_citations=True,
        )

    # Generation via the selected backend (local MedGemma or OpenAI API).
    try:
        raw_answer_en = generate_answer(symptoms_en, context)
        if not raw_answer_en:
            raise ValueError("Generation backend returned an empty answer.")
    except Exception as exc:
        log.warning("Answer generation failed; using deterministic response: %r", exc)
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=citations, reason="answer generation failed",
            clinical_reason=clinical_reason, show_citations=True,
        )

    cleaned_answer = clean_llm_output(raw_answer_en)
    if not cleaned_answer or len(cleaned_answer.split()) < 5:
        log.warning("Empty or leaked LLM output; using deterministic fallback.")
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=citations, reason="empty or leaked LLM output",
            clinical_reason=clinical_reason, show_citations=True,
        )

    if any(phrase in cleaned_answer.lower() for phrase in EXPLICIT_REFUSAL_PHRASES):
        log.warning("LLM explicitly refused; using deterministic fallback.")
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=citations, reason="LLM explicit refusal",
            clinical_reason=clinical_reason, show_citations=True,
        )

    try:
        verified, verify_msg = verify_answer(cleaned_answer, citations)
    except Exception as exc:
        log.error("Grounding verification raised: %r", exc)
        verified, verify_msg = False, f"verification exception: {exc!r}"

    if not verified:
        log.warning("Grounding failed (%s); using deterministic fallback.", verify_msg)
        return deterministic_response(
            req=req, detected_lang=detected_lang, level=level,
            label_en=label_en, urgency_en=urgency_en,
            citations_for_log=citations, reason=f"verification failed: {verify_msg}",
            clinical_reason=clinical_reason, show_citations=True,
        )

    final_answer = safe_translate_to_target(cleaned_answer, detected_lang)
    final_label = safe_translate_to_target(label_en, detected_lang)
    final_urgency = safe_translate_to_target(urgency_en, detected_lang)
    final_citations = translate_citations(citations, detected_lang)
    formatted = format_response(final_answer, level, final_label, final_urgency)

    safe_log_query(
        req.symptoms, detected_lang, req.child_age_months, level,
        citations, formatted, True, False, refusal_type=None,
    )
    log.info("Grounded LLM answer L%d in %.2fs", level, time.time() - start_time)

    return QueryResponse(
        answer=formatted,
        emergency_level=level,
        emergency_label=final_label,
        citations=final_citations,
        see_doctor_urgency=final_urgency,
        verified=True,
        refusal=False,
        refusal_type=None,
    )


@app.post("/ask", response_model=QueryResponse)
def ask(req: QueryRequest) -> QueryResponse:
    """Backward-compatible single-turn endpoint used by Colab and existing clients."""
    return _process_query(req)


# ── Conversational workflow ────────────────────────────────────────

conversation_store = ConversationStore(
    ttl_seconds=max(1, settings.conversation_ttl_seconds),
    max_sessions=max(1, settings.conversation_max_sessions),
)

_CONVERSATION_COPY = {
    "pending_label": {
        "en": "Assessment pending", "fa": "ارزیابی در انتظار تکمیل", "ar": "التقييم قيد الانتظار",
    },
    "pending_urgency": {
        "en": "No triage level has been finalized while clarification is pending. This is not a low-risk result.",
        "fa": "تا زمان تکمیل اطلاعات، سطح تریاژ نهایی نشده است. این وضعیت به معنی کم‌خطر بودن نیست.",
        "ar": "لم يتم تحديد مستوى الفرز النهائي أثناء انتظار التوضيح. هذا لا يعني أن الحالة منخفضة الخطورة.",
    },
    "incomplete_label": {
        "en": "Assessment incomplete", "fa": "ارزیابی ناتمام", "ar": "التقييم غير مكتمل",
    },
    "incomplete_message": {
        "en": "I could not complete a reliable assessment from the information provided. I have not treated unknown information as a negative symptom. Please contact a qualified healthcare professional for an assessment, especially if your child is getting worse or you remain concerned. Seek emergency help immediately for severe or rapidly worsening symptoms.",
        "fa": "با اطلاعات فعلی نتوانستم ارزیابی قابل اتکایی را کامل کنم. موارد نامشخص را به‌عنوان نبودِ علامت در نظر نگرفته‌ام. برای ارزیابی با متخصص واجد صلاحیت تماس بگیرید، به‌ویژه اگر حال کودک رو به بدتر شدن است یا همچنان نگران هستید. در صورت بروز علائم شدید یا بدترشدن سریع، فوراً کمک اورژانسی بگیرید.",
        "ar": "لم أتمكن من إكمال تقييم موثوق بالمعلومات المتاحة. لم أعتبر المعلومات غير المعروفة دليلاً على غياب الأعراض. يرجى التواصل مع مختص صحي مؤهل للتقييم، خاصة إذا كانت حالة طفلك تسوء أو ما زلت قلقاً. اطلب المساعدة الطارئة فوراً عند ظهور أعراض شديدة أو تدهور سريع.",
    },
    "conflict_message": {
        "en": "Some information in this conversation conflicts with an earlier answer. I will not silently choose one version or complete a triage assessment from conflicting details. Please start a new conversation with the corrected current information, or contact a healthcare professional.",
        "fa": "بخشی از اطلاعات این گفتگو با پاسخ قبلی تناقض دارد. بدون روشن شدن تناقض، هیچ‌کدام را به‌صورت خودکار انتخاب نمی‌کنم و تریاژ را کامل نمی‌کنم. لطفاً با اطلاعات صحیح و فعلی گفتگوی جدیدی آغاز کنید یا با متخصص سلامت تماس بگیرید.",
        "ar": "تتعارض بعض المعلومات في هذه المحادثة مع إجابة سابقة. لن أختار إحدى الروايتين تلقائياً أو أكمل الفرز اعتماداً على معلومات متضاربة. يرجى بدء محادثة جديدة بالمعلومات الحالية المصححة أو التواصل مع مختص صحي.",
    },
}


def _localized_conversation_text(key: str, language: str) -> str:
    return _CONVERSATION_COPY[key].get(language, _CONVERSATION_COPY[key]["en"])


def _conversation_result(
    state: ConversationState,
    result: QueryResponse,
    status: str,
) -> ConversationResponse:
    state.status = status
    state.current_question_id = None
    state.triage_level = int(result.emergency_level) if result.emergency_level is not None else None
    return ConversationResponse(
        conversation_id=state.conversation_id,
        language=state.language,
        status=status,
        answer=result.answer,
        follow_up_question=None,
        emergency_level=result.emergency_level,
        emergency_label=result.emergency_label,
        citations=result.citations,
        see_doctor_urgency=result.see_doctor_urgency,
        verified=result.verified,
        refusal=result.refusal,
        refusal_type=result.refusal_type,
    )


def _incomplete_response(state: ConversationState, message_key: str = "incomplete_message") -> ConversationResponse:
    message = _localized_conversation_text(message_key, state.language)
    state.status = "assessment_incomplete"
    state.current_question_id = None
    state.triage_level = None
    return ConversationResponse(
        conversation_id=state.conversation_id,
        language=state.language,
        status="assessment_incomplete",
        answer=message,
        follow_up_question=None,
        emergency_level=None,
        emergency_label=_localized_conversation_text("incomplete_label", state.language),
        citations=[],
        see_doctor_urgency=message,
        verified=False,
        refusal=False,
        refusal_type=None,
    )


def _advance_conversation(state: ConversationState) -> ConversationResponse:
    combined_text = state.clinical_text()
    request = QueryRequest(
        symptoms=combined_text,
        child_age_months=state.child_age_months,
        language=state.language,
    )
    preflight = _prepare_query(request, force_language=state.language)

    if preflight["kind"] == "translation_error":
        result = _process_query(request, preflight)
        return _conversation_result(state, result, "error")

    if preflight["kind"] == "refusal":
        result = _process_query(request, preflight)
        if result.emergency_level is not None and int(result.emergency_level) <= 2:
            return _conversation_result(state, result, "urgent_escalation")
        return _conversation_result(state, result, "refused")

    level = int(preflight["level"])
    state.triage_level = level

    # Never delay L1/L2 escalation or an existing L3 same-day recommendation.
    if level <= 3:
        result = _process_query(request, preflight)
        status = "urgent_escalation" if result.emergency_level is not None and int(result.emergency_level) <= 2 else "completed"
        return _conversation_result(state, result, status)

    # Compare only explicit facts across turns. Default False remains UNKNOWN.
    if find_feature_conflicts(state.clinical_segments(), state.child_age_months):
        return _incomplete_response(state, "conflict_message")

    question_candidate = select_next_question(
        preflight["symptoms_en"],
        state.child_age_months,
        state.asked_question_ids,
    )
    if question_candidate is not None:
        max_turns = max(1, int(settings.conversation_max_clarification_turns))
        if len(state.asked_question_ids) >= max_turns:
            return _incomplete_response(state)

        question_id = str(question_candidate["id"])
        question = localized_question(question_id, state.language)
        if question is None:
            return _incomplete_response(state)
        state.asked_question_ids.append(question_id)
        state.current_question_id = question_id
        state.status = "needs_clarification"
        state.triage_level = None
        return ConversationResponse(
            conversation_id=state.conversation_id,
            language=state.language,
            status="needs_clarification",
            answer=None,
            follow_up_question=FollowUpQuestion(**question),
            emergency_level=None,
            emergency_label=_localized_conversation_text("pending_label", state.language),
            citations=[],
            see_doctor_urgency=_localized_conversation_text("pending_urgency", state.language),
            verified=False,
            refusal=False,
            refusal_type=None,
        )

    if state.uncertain_answers:
        return _incomplete_response(state)

    result = _process_query(request, preflight)
    if result.refusal:
        if result.emergency_level is not None and int(result.emergency_level) <= 2:
            return _conversation_result(state, result, "urgent_escalation")
        return _conversation_result(state, result, "refused")
    if result.emergency_level is None:
        return _incomplete_response(state)
    if int(result.emergency_level) <= 2:
        return _conversation_result(state, result, "urgent_escalation")
    return _conversation_result(state, result, "completed")


@app.post("/conversations", response_model=ConversationResponse)
def create_conversation(req: ConversationCreateRequest) -> ConversationResponse:
    """Create an isolated case and return either one clarification or a result."""
    full_initial = req.symptoms
    if req.additional_context:
        full_initial = f"{req.symptoms}\n{req.additional_context}"
    language = detect_language(full_initial, req.language)
    try:
        state = conversation_store.create(
            child_age_months=req.child_age_months,
            language=language,
            original_concern=req.symptoms,
            additional_context=req.additional_context or "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Conversation capacity reached. Please retry.") from exc
    return _advance_conversation(state)


@app.post("/conversations/{conversation_id}/turn", response_model=ConversationResponse)
def submit_conversation_turn(
    conversation_id: str,
    req: ConversationTurnRequest,
) -> ConversationResponse:
    with conversation_store.access(conversation_id) as state:
        if state is None:
            raise HTTPException(status_code=404, detail="Conversation not found or expired. Start a new conversation.")
        if state.status != "needs_clarification" or not state.current_question_id:
            raise HTTPException(status_code=409, detail="This conversation is no longer awaiting clarification.")
        if req.question_id != state.current_question_id:
            raise HTTPException(status_code=409, detail="The answer does not match the active follow-up question.")

        answer = req.answer.strip()
        option_label = resolve_option_label(req.question_id, answer, state.language)
        answer_text = option_label or answer
        uncertain = is_uncertain_answer(req.question_id, answer if option_label else None, answer_text)
        state.turns.append({
            "question_id": req.question_id,
            "answer": answer_text,
            "uncertain": uncertain,
        })
        if uncertain:
            state.uncertain_answers.append(req.question_id)
        state.current_question_id = None
        return _advance_conversation(state)


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, bool]:
    if not conversation_store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found or expired.")
    return {"deleted": True}


_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
    log.info("Serving frontend from %s", _FRONTEND_DIR)
else:
    log.info("No frontend directory at %s; running API-only.", _FRONTEND_DIR)