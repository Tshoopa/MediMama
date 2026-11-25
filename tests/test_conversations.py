"""Regression coverage for the additive multi-turn conversation API."""

import time

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.config import settings
from backend.conversation_store import ConversationStore
from backend.triage.clarification_engine import feature_states


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_conversation_runtime(monkeypatch):
    """Keep tests deterministic and independent of provider/Qdrant services."""
    monkeypatch.setattr(main, "safe_translate_to_english", lambda text, source_lang="auto": text)
    monkeypatch.setattr(main, "safe_translate_to_target", lambda text, target_lang: text)
    monkeypatch.setattr(main, "is_safe_and_relevant", lambda text: (True, "Safe", None))
    monkeypatch.setattr(
        main,
        "safe_assess",
        lambda symptoms, age, citations=None: (4, "Semi-Urgent", "GP or clinic within 1–2 days", "test triage"),
    )
    monkeypatch.setattr(main, "safe_retrieve", lambda query: [])
    monkeypatch.setattr(main, "safe_expand", lambda query: query)
    monkeypatch.setattr(main, "safe_log_query", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings, "conversation_max_clarification_turns", 3)
    main.conversation_store = ConversationStore(ttl_seconds=60, max_sessions=20)
    yield


def _create(symptoms="My child has a fever and diarrhea.", language="en", age=24):
    return client.post(
        "/conversations",
        json={
            "symptoms": symptoms,
            "child_age_months": age,
            "language": language,
        },
    )


def _turn(conversation_id, question_id, answer):
    return client.post(
        f"/conversations/{conversation_id}/turn",
        json={"question_id": question_id, "answer": answer},
    )


def test_initial_request_can_return_a_follow_up_question():
    response = _create()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_clarification"
    assert data["follow_up_question"]["id"] == "symptom_duration"
    assert data["emergency_level"] is None
    assert data["verified"] is False
    assert len(data["follow_up_question"]["options"]) == 4


def test_multiple_turns_reassess_the_complete_case_and_finish():
    first = _create().json()
    conversation_id = first["conversation_id"]

    second = _turn(conversation_id, "symptom_duration", "less_than_24_hours")
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["status"] == "needs_clarification"
    assert second_data["follow_up_question"]["id"] == "hydration_status"

    final = _turn(conversation_id, "hydration_status", "usual")
    assert final.status_code == 200
    final_data = final.json()
    assert final_data["status"] == "completed"
    assert final_data["emergency_level"] == 4
    assert final_data["follow_up_question"] is None
    assert final_data["answer"]


def test_l1_and_l2_escalate_without_clarification(monkeypatch):
    for level in (1, 2):
        monkeypatch.setattr(
            main,
            "safe_assess",
            lambda symptoms, age, citations=None, level=level: (
                level, f"Level {level}", "Emergency care now", "emergency test",
            ),
        )
        response = _create("My child is unresponsive.")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "urgent_escalation"
        assert data["emergency_level"] == level
        assert data["follow_up_question"] is None


def test_l3_same_day_recommendation_is_not_delayed(monkeypatch):
    monkeypatch.setattr(
        main, "safe_assess",
        lambda symptoms, age, citations=None: (3, "Urgent", "Seek medical advice today", "L3 test"),
    )
    response = _create()
    data = response.json()
    assert data["status"] == "completed"
    assert data["emergency_level"] == 3
    assert data["follow_up_question"] is None


def test_maximum_clarification_limit_produces_incomplete_not_low_risk(monkeypatch):
    monkeypatch.setattr(settings, "conversation_max_clarification_turns", 1)
    first = _create().json()
    result = _turn(first["conversation_id"], "symptom_duration", "less_than_24_hours")
    data = result.json()
    assert data["status"] == "assessment_incomplete"
    assert data["emergency_level"] is None
    assert data["verified"] is False


def test_unknown_answer_is_not_converted_to_a_negative_finding():
    first = _create("My child has a fever.").json()
    result = _turn(first["conversation_id"], "symptom_duration", "unknown")
    data = result.json()
    assert data["status"] == "assessment_incomplete"
    assert data["emergency_level"] is None
    assert data["answer"]


def test_invalid_conversation_id_returns_404():
    response = _turn("not-a-real-id", "symptom_duration", "unknown")
    assert response.status_code == 404


def test_expired_conversation_returns_404():
    first = _create("My child has a fever.").json()
    state = main.conversation_store._sessions[first["conversation_id"]]
    state.updated_at = time.monotonic() - 120
    response = _turn(first["conversation_id"], "symptom_duration", "unknown")
    assert response.status_code == 404


def test_two_conversations_do_not_share_context():
    fever_case = _create("My child has a fever.").json()
    diarrhea_case = _create("My child has diarrhea.").json()
    assert fever_case["conversation_id"] != diarrhea_case["conversation_id"]

    fever_final = _turn(fever_case["conversation_id"], "symptom_duration", "less_than_24_hours")
    assert fever_final.json()["status"] == "completed"

    diarrhea_state = main.conversation_store._sessions[diarrhea_case["conversation_id"]]
    assert diarrhea_state.status == "needs_clarification"
    assert diarrhea_state.original_concern == "My child has diarrhea."
    assert diarrhea_state.turns == []


def test_persian_and_arabic_follow_up_templates_are_localized():
    persian = _create("My child has a fever.", language="fa").json()
    arabic = _create("My child has a fever.", language="ar").json()
    assert "از چه زمانی" in persian["follow_up_question"]["text"]
    assert "متى" in arabic["follow_up_question"]["text"]
    assert persian["follow_up_question"]["options"][0]["label"] == "کمتر از ۲۴ ساعت"
    assert arabic["follow_up_question"]["options"][0]["label"] == "أقل من ٢٤ ساعة"


def test_explicit_negation_and_unknown_feature_state_are_distinct():
    negative = feature_states("My child has no difficulty breathing.", 36)
    unmentioned = feature_states("My child has a fever.", 36)
    positive = feature_states("My child has difficulty breathing.", 36)

    assert negative["breathing_difficulty"] == "absent"
    assert positive["breathing_difficulty"] == "present"
    assert unmentioned["breathing_difficulty"] == "unknown"


def test_conflicting_explicit_answers_stop_completion():
    first = _create("My child has diarrhea but no fever.").json()
    result = _turn(first["conversation_id"], "symptom_duration", "My child has a fever")
    data = result.json()
    assert data["status"] == "assessment_incomplete"
    assert data["emergency_level"] is None
    assert "conflict" in data["answer"].lower()


def test_delete_conversation_clears_session():
    first = _create("My child has a fever.").json()
    response = client.delete(f"/conversations/{first['conversation_id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert _turn(first["conversation_id"], "symptom_duration", "unknown").status_code == 404


def test_initial_request_can_complete_without_follow_up():
    response = _create("My child has a mild runny nose and is playing normally.")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["emergency_level"] == 4
    assert data["follow_up_question"] is None
    assert data["answer"]


def test_custom_text_answer_is_preserved_in_the_same_case():
    first = _create("My child has a fever and diarrhea.").json()
    conversation_id = first["conversation_id"]
    result = _turn(conversation_id, "symptom_duration", "The fever started yesterday.")
    data = result.json()
    assert result.status_code == 200
    assert data["status"] == "needs_clarification"
    assert data["follow_up_question"]["id"] == "hydration_status"
    state = main.conversation_store._sessions[conversation_id]
    assert state.turns[0]["answer"] == "The fever started yesterday."


def test_conversation_refusal_is_not_rendered_as_completed_or_low_risk(monkeypatch):
    monkeypatch.setattr(main, "is_safe_and_relevant", lambda text: (False, "Out of scope", "scope"))
    response = _create("Tell me a joke.")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "refused"
    assert data["refusal"] is True
    assert data["emergency_level"] is None
    assert data["follow_up_question"] is None
