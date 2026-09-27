from core import orchestrator


def test_process_request_delegates_to_existing_router(monkeypatch):
    calls = []

    def fake_route(command):
        calls.append(command)
        return "router response"

    monkeypatch.setattr(orchestrator, "route", fake_route)

    result = orchestrator.process_request("  test command  ")

    assert calls == ["test command"]
    assert result.response == "router response"
    assert result.route_type == "legacy_router"


def test_brain_result_defaults_are_independent():
    first = orchestrator.BrainResult(response="one")
    second = orchestrator.BrainResult(response="two")

    assert first.response == "one"
    assert first.route_type == "legacy_router"
    assert first.intent is None
    assert first.used_llm is None
    assert first.metadata == {}
    assert second.metadata == {}
    assert first.metadata is not second.metadata


def test_process_request_preserves_router_response_exactly(monkeypatch):
    expected = "  response with spacing and punctuation!  "
    monkeypatch.setattr(orchestrator, "route", lambda command: expected)

    result = orchestrator.process_request("command")

    assert result.response == expected


def test_process_request_does_not_write_session_memory(monkeypatch):
    session_calls = []
    monkeypatch.setattr(
        "core.session.remember_user_message",
        lambda *args, **kwargs: session_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "core.session.remember_assistant_message",
        lambda *args, **kwargs: session_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(orchestrator, "route", lambda command: "response")

    orchestrator.process_request("command")

    assert session_calls == []


def test_router_exceptions_propagate(monkeypatch):
    expected = RuntimeError("router failed")

    def failing_route(command):
        raise expected

    monkeypatch.setattr(orchestrator, "route", failing_route)

    try:
        orchestrator.process_request("command")
    except RuntimeError as error:
        assert error is expected
    else:
        raise AssertionError("router exception was swallowed")
