# backend/translation.py

from deep_translator import GoogleTranslator


def translate_to_english(text: str) -> str:
    """Translate arbitrary input to English. Returns the original text on
    failure so the pipeline never breaks on a translation error."""
    try:
        return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        return text


def translate_to_target(text: str, target_lang: str) -> str:
    """Translate English text to the target language (no-op for English).
    Returns the original text on failure."""
    if target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception:
        return text