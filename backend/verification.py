# backend/verification.py

"""Grounding verification: reject LLM answers that aren't supported by the
retrieved evidence, using a lightweight lexical-overlap heuristic with a simple
dependency-free stemmer."""

import re

from backend.models import Citation


REFUSAL_INDICATORS = [
    "do not contain enough information",
    "cannot answer",
    "i am not able to",
    "not enough information",
    "consult a doctor for more",
    "i don't have information",
]

# Common English + generic-medical words excluded from grounding so they don't
# inflate the overlap score (e.g. every answer mentions "child" or "doctor").
STOPWORDS = {
    "their", "there", "these", "those", "which", "while", "would", "could",
    "should", "about", "after", "before", "because", "although", "however",
    "therefore", "within", "important", "please", "provide", "including",
    "also", "other", "often", "usually", "typically", "generally", "always",
    "never", "every", "might", "where", "when",
    "child", "baby", "parent", "doctor", "symptom", "medical", "clinical",
    "pediatric", "months", "years", "old", "advice",
}

# Fraction of answer content words that must appear in the evidence. Tuned to
# catch hallucinations while tolerating paraphrasing.
GROUNDING_THRESHOLD = 0.48


def _stem(word: str) -> str:
    """Strip a few common English suffixes so "sprains"/"sprained" match
    "sprain", "vomited" matches "vomit", etc. Deliberately naive — no NLTK."""
    w = word.lower().strip()
    for suffix in ["ing", "ed", "es", "s", "al", "ic"]:
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def _content_words(text: str) -> set[str]:
    """Return the set of stemmed content words (>=3 chars, non-stopword)."""
    clean = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return {_stem(w) for w in clean.split() if len(w) >= 3 and w not in STOPWORDS}


def verify_answer(answer: str, citations: list[Citation] | None) -> tuple[bool, str]:
    """Return (is_grounded, message).

    Rejects empty answers, explicit refusals, and answers whose content-word
    overlap with the evidence falls below GROUNDING_THRESHOLD. Very short
    answers skip strict grounding. Fails closed (False) on unexpected errors.
    """
    try:
        ans_lower = (answer or "").lower().strip()
        if not ans_lower:
            return False, "Empty answer."

        if any(phrase in ans_lower for phrase in REFUSAL_INDICATORS):
            return False, "Model explicitly refused."

        if not citations:
            return False, "No evidence retrieved."

        answer_words = _content_words(answer)

        evidence_words: set[str] = set()
        for c in citations:
            chunk = getattr(c, "chunk", "") or getattr(c, "text", "") or ""
            evidence_words |= _content_words(chunk)

        if len(answer_words) < 5:
            return True, "Short answer; strict grounding skipped."

        if not evidence_words:
            return False, "No evidence words available."

        grounded = answer_words & evidence_words
        grounding_ratio = len(grounded) / max(1, len(answer_words))

        if grounding_ratio >= GROUNDING_THRESHOLD:
            return True, f"Verified. Grounding: {grounding_ratio:.0%}"

        ungrounded = answer_words - evidence_words
        return False, (
            f"Low grounding ({grounding_ratio:.0%} < {GROUNDING_THRESHOLD:.0%}); "
            f"possible hallucination: {list(ungrounded)[:5]}"
        )

    except Exception as e:
        print("[verification] failed unexpectedly:", repr(e))
        return False, "Verification error."