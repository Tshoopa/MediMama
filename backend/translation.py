"""
Mode-aware clinical translation.

Local mode uses Qwen3.
API mode uses OpenAI.

Translation failure raises TranslationError rather than passing
untranslated text into English-only triage and retrieval components.
"""

from backend.config import settings
from backend.openai_client import get_openai_client


class TranslationError(RuntimeError):
    pass


LANGUAGE_NAMES = {"en": "English", "fa": "Persian", "ar": "Arabic"}


def _translate(text: str, source_lang: str, target_lang: str) -> str:
    text = (text or "").strip()
    source_lang = (source_lang or "auto").lower()
    target_lang = (target_lang or "en").lower()
    if not text or target_lang == source_lang:
        return text
    if target_lang not in LANGUAGE_NAMES:
        raise TranslationError(f"Unsupported target language: {target_lang}")
    source_name = LANGUAGE_NAMES.get(source_lang, "the language of the input")
    target_name = LANGUAGE_NAMES[target_lang]

    instructions = f"""Translate the following pediatric health message from {source_name} to {target_name}.
This is a clinical translation task, not a medical interpretation task.
Preserve the exact meaning and every clinical detail. Never omit or change:
- negation (no/not/never), uncertainty, or conditional statements;
- symptom names, body parts, age, dates, durations, frequency, and numbers;
- temperatures, measurements, medication names, doses, and units;
- who has each symptom and when it started.
Do not add diagnoses, advice, explanations, or facts. If a phrase is ambiguous,
translate it as literally as possible without resolving the ambiguity. Return only
the translated text, with no quotation marks or commentary."""

    try:
        if settings.active_translation_backend == "local":
            # Import lazily so API-only deployments never load local ML modules.
            from backend.llm_provider import generate_local_completion

            translated = generate_local_completion(
                instructions,
                text,
                max_new_tokens=settings.local_translation_max_new_tokens,
                temperature=0.0,
            )
        else:
            response = get_openai_client().responses.create(
                model=settings.openai_translation_model,
                instructions=instructions,
                input=text,
                temperature=0,
                max_output_tokens=max(256, min(1200, len(text.split()) * 5 + 80)),
            )
            translated = (getattr(response, "output_text", "") or "").strip()
        if not translated:
            raise TranslationError("The translation model returned an empty result.")
        return translated
    except TranslationError:
        raise
    except Exception as exc:
        raise TranslationError(f"Translation request failed: {exc}") from exc


def translate_to_english(text: str, source_lang: str = "auto") -> str:
    return _translate(text, source_lang, "en")


def translate_to_target(text: str, target_lang: str) -> str:
    return _translate(text, "en", target_lang)
