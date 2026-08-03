# backend/triage/normalizer.py

import re

# Order matters: curly apostrophes are first folded to straight ones, then
# contractions are expanded so downstream negation patterns can rely on the
# full "does not" / "cannot" forms.
_REPLACEMENTS = {
    "diarrhoea": "diarrhea",

    "doesn’t": "doesn't",
    "don’t": "don't",
    "won’t": "won't",
    "can’t": "can't",
    "isn’t": "isn't",
    "hasn’t": "hasn't",
    "haven’t": "haven't",
    "couldn’t": "couldn't",
    "shouldn’t": "shouldn't",

    "doesn't": "does not",
    "don't": "do not",
    "won't": "will not",
    "can't": "cannot",
    "isn't": "is not",
    "hasn't": "has not",
    "haven't": "have not",
    "couldn't": "could not",
    "shouldn't": "should not",
}


def normalize_text(text: str) -> str:
    """Lowercase, expand contractions, and collapse whitespace so feature
    extraction sees a consistent form. Makes no clinical decision."""
    if not text:
        return ""

    text = text.lower().strip()
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)

    return re.sub(r"\s+", " ", text)