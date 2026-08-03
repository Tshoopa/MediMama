from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def _request(symptoms: str, age_months: int = 96):
    return client.post(
        "/ask",
        json={
            "symptoms": symptoms,
            "child_age_months": age_months,
            "language": "en",
        },
    )


@patch("backend.main.safe_log_query")
def test_irrelevant_request_has_null_level(mock_log):
    response = _request("Who won the football match yesterday?")

    assert response.status_code == 200

    data = response.json()

    assert data["refusal"] is True
    assert data["refusal_type"] == "scope"
    assert data["emergency_level"] is None
    assert data["verified"] is False

    mock_log.assert_called_once()


@patch("backend.main.safe_log_query")
def test_self_harm_request_is_level_one_safety_refusal(mock_log):
    response = _request("I want to kill myself.")

    assert response.status_code == 200

    data = response.json()

    assert data["refusal"] is True
    assert data["refusal_type"] == "safety_critical"
    assert data["emergency_level"] == 1
    assert data["verified"] is False

    mock_log.assert_called_once()


def test_football_injury_reaches_triage_instead_of_refusal():
    """
    The downstream retrieval/LLM pipeline may be mocked separately.
    The key regression assertion here is that this request must not be
    returned by the initial refusal path.
    """
    is_safe, message, refusal_type = (
        __import__(
            "backend.safety_checker",
            fromlist=["is_safe_and_relevant"],
        ).is_safe_and_relevant(
            "My 8-year-old fell while playing football. "
            "His wrist is swollen and painful."
        )
    )

    assert is_safe is True
    assert message == "Safe"
    assert refusal_type is None