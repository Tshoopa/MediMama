import pytest
from backend.translation import translate_to_english, translate_to_target

def test_translation_to_english():
    # تست تبدیل به انگلیسی (ورودی به RAG)
    persian_text = "کودک من تب بالایی دارد"
    english_output = translate_to_english(persian_text)
    # با توجه به اینکه ترجمه گوگل ممکن است کمی متفاوت باشد، کلمات کلیدی را چک می‌کنیم
    assert "fever" in english_output.lower() or "temperature" in english_output.lower()

def test_translation_to_target():
    # تست تبدیل خروجی انگلیسی به زبان کاربر
    english_text = "Please see a doctor immediately."
    arabic_output = translate_to_target(english_text, "ar")
    assert arabic_output != english_text
    assert arabic_output != ""
