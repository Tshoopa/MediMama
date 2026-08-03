import pytest
from pydantic import ValidationError
from backend.models import QueryRequest

def test_query_request_validation_valid():
    # ورودی صحیح
    req = QueryRequest(symptoms="cough", child_age_months=24, language="fa")
    assert req.child_age_months == 24

def test_query_request_validation_invalid_age():
    # تست اعتبارسنجی سن (خارج از محدوده مجاز 0 تا 216)
    with pytest.raises(ValidationError):
        QueryRequest(symptoms="cough", child_age_months=-5, language="en")
        
def test_query_request_validation_invalid_language():
    # تست اعتبارسنجی زبان (زبانی غیر از en, fa, ar)
    with pytest.raises(ValidationError):
        QueryRequest(symptoms="cough", child_age_months=10, language="fr")
