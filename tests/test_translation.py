from types import SimpleNamespace

from backend import translation


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


def test_persian_translation_uses_explicit_source_and_preserves_negation(monkeypatch):
    fake = FakeClient("My child does not have a fever but has been vomiting since morning.")
    monkeypatch.setattr(translation, "get_openai_client", lambda: fake)

    translated = translation.translate_to_english(
        "فرزندم تب ندارد اما از صبح استفراغ می‌کند", source_lang="fa"
    )

    assert "does not have a fever" in translated
    call = fake.responses.calls[0]
    assert "Persian to English" in call["instructions"]
    assert "negation" in call["instructions"]


def test_arabic_output_translation(monkeypatch):
    fake = FakeClient("يرجى مراجعة الطبيب فوراً.")
    monkeypatch.setattr(translation, "get_openai_client", lambda: fake)

    translated = translation.translate_to_target("Please see a doctor immediately.", "ar")
    assert translated.startswith("يرجى")
    assert "English to Arabic" in fake.responses.calls[0]["instructions"]


def test_translation_failure_is_not_silently_swallowed(monkeypatch):
    def fail():
        raise RuntimeError("API key missing")

    monkeypatch.setattr(translation, "get_openai_client", fail)
    try:
        translation.translate_to_english("طفلي لديه حمى", source_lang="ar")
    except translation.TranslationError:
        pass
    else:
        raise AssertionError("TranslationError should be raised")


def test_local_mode_translation_uses_medgemma_without_openai(monkeypatch):
    from backend.config import settings

    calls = []

    def fake_local(instructions, text, max_new_tokens=None, temperature=0.0):
        calls.append((instructions, text, max_new_tokens, temperature))
        return "My child does not have a fever."

    monkeypatch.setattr(settings, "inference_mode", "local")
    monkeypatch.setattr(settings, "translation_backend", "auto")
    monkeypatch.setattr(translation, "get_openai_client", lambda: (_ for _ in ()).throw(
        AssertionError("OpenAI must not be used by default in local mode")
    ))
    from backend import llm_provider
    monkeypatch.setattr(llm_provider, "generate_local_completion", fake_local)

    result = translation.translate_to_english("فرزندم تب ندارد", source_lang="fa")

    assert result == "My child does not have a fever."
    assert calls
    assert "Persian to English" in calls[0][0]
    assert calls[0][2] == settings.local_translation_max_new_tokens
