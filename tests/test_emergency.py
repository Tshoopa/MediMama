import pytest
from backend.emergency_detector import assess 

def test_critical_symptoms():
    # تست سطح ۱ (احیا)
    symptoms = "child has blue lips and is unconscious"
    age = 12
    level, label, urgency = assess(symptoms, age)
    assert level == 1
    assert label == "Resuscitation"

def test_routine_symptoms():
    # تست سطح ۴ (نیمه فوری)
    symptoms = "child has a mild fever and cough"
    age = 24
    level, label, urgency = assess(symptoms, age)
    assert level == 4
    assert label == "Semi-Urgent"

def test_infant_fever_modifier():
    # تست حساسیت سن: نوزاد زیر ۳ ماه با تب باید سطح ۲ (اورژانس) شود
    symptoms = "mild fever"
    age = 2 # ۲ ماهه
    level, label, urgency = assess(symptoms, age)
    assert level == 2
    assert label == "Emergency (Infant Fever)"
