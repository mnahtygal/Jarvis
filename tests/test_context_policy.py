from core import context, orchestrator, router
from core.brain_request_context import get_active_request_context
from core.request_classifier import RequestIntent


def _install_context_spies(monkeypatch, calls):
    monkeypatch.setattr(context, "build_memory_context", lambda: calls.append("exact") or "exact")
    monkeypatch.setattr(context, "search_semantic_memories", lambda *args, **kwargs: calls.append("semantic") or [])
    monkeypatch.setattr(context, "format_semantic_results", lambda results: "semantic")
    monkeypatch.setattr(context, "get_recent_history", lambda *args, **kwargs: calls.append("history") or [])
    monkeypatch.setattr(context, "get_last_topic", lambda: calls.append("topic") or "topic")


def test_general_factual_request_disables_all_context_sources(monkeypatch):
    calls = []
    _install_context_spies(monkeypatch, calls)
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: context.build_messages(command)[0]["content"],
    )

    result = orchestrator.process_request("what is PostgreSQL")

    assert result.intent is RequestIntent.FACTUAL_QUESTION
    assert calls == []
    assert "Exact long-term memory:" not in result.response
    assert "Semantic memory:" not in result.response
    assert "Recent conversation:" not in result.response
    assert "Last topic:" not in result.response
    assert result.metadata["context_sources"] == []


def test_semantic_recall_uses_allowed_memory_and_history(monkeypatch):
    calls = []
    _install_context_spies(monkeypatch, calls)
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: context.build_messages(command)[0]["content"],
    )

    result = orchestrator.process_request("what did I tell you about Jarvis memory")

    assert result.intent is RequestIntent.MEMORY_RECALL
    assert calls == ["exact", "semantic", "history"]
    assert "last_topic" not in result.metadata["context_sources"]


def test_follow_up_uses_recent_history_last_topic_and_semantic_memory(monkeypatch):
    calls = []
    _install_context_spies(monkeypatch, calls)
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: context.build_messages(command)[0]["content"],
    )

    result = orchestrator.process_request("tell me more")

    assert result.intent is RequestIntent.CONVERSATION
    assert calls == ["topic", "semantic", "history"]
    assert result.metadata["context_sources"] == [
        "semantic_memory",
        "recent_history",
        "last_topic",
    ]


def test_legacy_direct_context_calls_use_all_sources(monkeypatch):
    calls = []
    _install_context_spies(monkeypatch, calls)

    messages = context.build_messages("what is PostgreSQL")

    assert calls == ["topic", "exact", "semantic", "history"]
    assert "Exact long-term memory:" in messages[0]["content"]
    assert "Semantic memory:" in messages[0]["content"]
    assert "Recent conversation:" in messages[0]["content"]
    assert "Last topic:" in messages[0]["content"]


def test_policy_is_reset_after_success_and_failure(monkeypatch):
    def successful_route(command):
        assert get_active_request_context() is not None
        return "response"

    monkeypatch.setattr(orchestrator, "route", successful_route)
    orchestrator.process_request("what is PostgreSQL")
    assert get_active_request_context() is None

    def failing_route(command):
        assert get_active_request_context() is not None
        raise RuntimeError("expected test failure")

    monkeypatch.setattr(orchestrator, "route", failing_route)

    try:
        orchestrator.process_request("what is PostgreSQL")
    except RuntimeError:
        pass
    else:
        raise AssertionError("router exception was swallowed")

    assert get_active_request_context() is None


def test_high_level_regression_requests_preserve_router_responses(monkeypatch):
    monkeypatch.setattr(router, "recall", lambda key: "saved-value")
    monkeypatch.setattr(router, "get_llm_response", lambda command: "mocked llm response")
    monkeypatch.setattr(router, "get_brain_status_response", lambda: "mocked brain status")

    assert (
        orchestrator.process_request("what is my wife's name").response
        == "Based on your saved memory, your wife's name is saved-value, Marty."
    )
    assert (
        orchestrator.process_request("what database do I prefer").response
        == "Based on your saved memory, your preferred database is saved-value, Marty."
    )
    assert orchestrator.process_request("what is PostgreSQL").response == "mocked llm response"
    assert (
        orchestrator.process_request("what did I tell you about Jarvis memory").response
        == "mocked llm response"
    )
    assert orchestrator.process_request("tell me more").response == "mocked llm response"
    assert orchestrator.process_request("brain status").response == "mocked brain status"
