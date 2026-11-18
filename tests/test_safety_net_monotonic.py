from backend.triage import engine


def test_llm_cannot_downgrade_deterministic_urgency(monkeypatch):
    monkeypatch.setattr(engine, "llm_safety_net_enabled", lambda: True)
    monkeypatch.setattr(engine, "resolve_safety_net", lambda _handle: (5, "low concern", "high"))

    base = engine._result(2, "deterministic emergency rule")
    result, audit = engine._apply_safety_net(
        base_result=base,
        text="example symptoms",
        age_months=24,
        decision_source="triage_rules",
        llm_handle=object(),
    )

    assert result.level == 2
    assert audit["ignored_deescalation"] is True


def test_llm_can_escalate_deterministic_urgency(monkeypatch):
    monkeypatch.setattr(engine, "llm_safety_net_enabled", lambda: True)
    monkeypatch.setattr(engine, "resolve_safety_net", lambda _handle: (2, "possible emergency", "medium"))

    base = engine._result(4, "deterministic mild concern")
    result, audit = engine._apply_safety_net(
        base_result=base,
        text="example symptoms",
        age_months=24,
        decision_source="triage_rules",
        llm_handle=object(),
    )

    assert result.level == 2
    assert audit["adjusted"] is True
