from core import orchestrator
from core.request_classifier import RequestIntent, classify_request


def test_request_classification_examples():
    cases = {
        "what is my wife's name": (
            RequestIntent.MEMORY_RECALL,
            (True, False, False, False, "memory recall request"),
        ),
        "what did I tell you about Jarvis memory": (
            RequestIntent.MEMORY_RECALL,
            (True, True, True, False, "memory recall request"),
        ),
        "tell me more": (
            RequestIntent.CONVERSATION,
            (False, True, True, True, "follow-up conversation"),
        ),
        "brain status": (
            RequestIntent.RUNTIME_STATUS,
            (False, False, False, False, "runtime command"),
        ),
        "what is PostgreSQL": (
            RequestIntent.FACTUAL_QUESTION,
            (False, False, False, False, "general factual question"),
        ),
        "remember that my favorite color is blue": (
            RequestIntent.MEMORY_WRITE,
            (False, False, False, False, "memory write request"),
        ),
        "make something interesting": (
            RequestIntent.UNKNOWN,
            (False, False, False, False, "unknown request"),
        ),
    }

    for command, (intent, policy_values) in cases.items():
        result = classify_request(command)

        assert result.intent is intent
        assert (
            result.context_policy.use_exact_memory,
            result.context_policy.use_semantic_memory,
            result.context_policy.use_recent_history,
            result.context_policy.use_last_topic,
            result.context_policy.reason,
        ) == policy_values


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
    assert result.intent is RequestIntent.UNKNOWN
    assert result.context_policy.reason == "unknown request"


def test_brain_result_defaults_are_independent():
    first = orchestrator.BrainResult(response="one")
    second = orchestrator.BrainResult(response="two")

    assert first.response == "one"
    assert first.route_type == "legacy_router"
    assert first.intent is None
    assert first.context_policy is None
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


def test_classifier_does_not_call_database_or_llm(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("classifier called an external dependency")

    monkeypatch.setattr("core.db.get_connection", unexpected_call)
    monkeypatch.setattr("skills.llm_skill.ask_local_llm", unexpected_call)
    monkeypatch.setattr(orchestrator, "route", lambda command: "response")

    result = orchestrator.process_request("what is PostgreSQL")

    assert result.intent is RequestIntent.FACTUAL_QUESTION


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
