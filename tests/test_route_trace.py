"""Router compatibility and request-scoped attribution regressions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest

from core import orchestrator, router
from core.brain_request_context import get_active_request_context
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.route_trace import (
    begin_route_trace, get_actual_route, reset_route_trace, set_actual_route,
)


@pytest.mark.parametrize("command,handler,args,label", [
    ("remember that Kelly likes tea", "_store_semantic_note", ("Kelly likes tea",), "memory_write"),
    ("semantic search satellite", "get_semantic_search_response", ("satellite",), "semantic_memory"),
    ("brain status", "get_brain_status_response", (), "runtime_status"),
    ("brain v2 status", "get_brain_v2_status_response", (), "runtime_status"),
    ("help", "get_help_response", (), "help_docs"),
    ("jarvis docs", "get_docs_response", (), "help_docs"),
    ("hello", "get_chat_response", ("hello",), "chat"),
    ("what is PostgreSQL", "get_llm_response", ("what is PostgreSQL",), "llm_fallback"),
    ("xyzzy", "get_llm_response", ("xyzzy",), "llm_fallback"),
    ("what time is it", "get_time_response", (), "system"),
    ("I work at GM", "remember", ("my workplace", "GM"), "memory_write"),
    ("forget that color", "forget", ("color",), "memory_write"),
])
def test_router_returns_same_string_and_invokes_handler_once(monkeypatch, command, handler, args, label):
    expected = "  unchanged response\nwith spacing  "
    handler_mock = Mock(return_value=expected)
    monkeypatch.setattr(router, handler, handler_mock)
    traced_router = Mock(wraps=router.route)
    monkeypatch.setattr(orchestrator, "route", traced_router)

    result = orchestrator.process_request(command)

    assert isinstance(result.response, str)
    assert result.response == expected
    handler_mock.assert_called_once_with(*args)
    traced_router.assert_called_once_with(command)
    assert result.actual_route == label
    assert result.metadata["actual_route"] == label
    assert get_brain_v2_status().actual_route == label
    assert get_actual_route() == "unknown"


def test_exact_memory_response_unchanged(monkeypatch):
    recall = Mock(return_value="Kelly")
    monkeypatch.setattr(router, "recall", recall)
    result = orchestrator.process_request("what is my wife's name")
    assert result.response == "Based on your saved memory, your wife's name is Kelly, Marty."
    assert result.actual_route == "exact_memory"
    recall.assert_called_once_with("my wife's name")


def test_camera_status_response_unchanged(monkeypatch):
    camera = Mock(return_value={
        "active_role": "workbench", "active_camera": {"available": True},
    })
    monkeypatch.setattr(router, "get_camera_roles_status", camera)
    result = orchestrator.process_request("which camera is active")
    assert result.response == "The workbench camera is active."
    assert result.actual_route == "camera_vision"
    camera.assert_called_once_with()


def test_status_reports_expected_and_actual_route(monkeypatch):
    monkeypatch.setattr(router, "get_chat_response", lambda command: "Hello!")
    result = orchestrator.process_request("hello")
    assert result.execution_strategy.value == "llm"
    assert result.actual_route == "chat"
    assert "Actual route: chat" in get_brain_v2_status_response()


@pytest.mark.parametrize("label", [None, "llm_fallback"])
def test_exception_preserves_identity_and_cleans_both_contexts(monkeypatch, label):
    error = RuntimeError("private exception detail")

    def fail(command):
        if label:
            set_actual_route(label)
        raise error

    monkeypatch.setattr(orchestrator, "route", fail)
    with pytest.raises(RuntimeError) as caught:
        orchestrator.process_request("xyzzy")
    assert caught.value is error
    assert get_actual_route() == "unknown"
    assert get_active_request_context() is None
    assert get_brain_v2_status().actual_route == (label or "unknown")
    assert str(error) not in repr(get_brain_v2_status())
    monkeypatch.setattr(orchestrator, "route", lambda command: "unchanged")
    assert orchestrator.process_request("xyzzy").actual_route == "unknown"


def test_nested_requests_restore_outer_trace(monkeypatch):
    def nested_route(command):
        if command == "outer":
            set_actual_route("chat")
            assert orchestrator.process_request("inner").actual_route == "system"
            assert get_actual_route() == "chat"
        else:
            assert get_actual_route() == "unknown"
            set_actual_route("system")
        return "response"

    monkeypatch.setattr(orchestrator, "route", nested_route)
    assert orchestrator.process_request("outer").actual_route == "chat"
    assert get_actual_route() == "unknown"


def test_concurrent_requests_have_independent_traces(monkeypatch):
    barrier = Barrier(2)

    def concurrent_route(command):
        set_actual_route(command)
        barrier.wait(timeout=5)
        assert get_actual_route() == command
        return "response"

    monkeypatch.setattr(orchestrator, "route", concurrent_route)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(orchestrator.process_request, ["chat", "system"]))
    assert [result.actual_route for result in results] == ["chat", "system"]
    assert get_actual_route() == "unknown"


def test_legacy_direct_route_does_not_leave_trace(monkeypatch):
    monkeypatch.setattr(router, "get_chat_response", lambda command: "Hello!")
    assert router.route("hello") == "Hello!"
    assert get_actual_route() == "unknown"


def test_trace_rejects_non_internal_labels():
    token = begin_route_trace()
    try:
        with pytest.raises(ValueError, match="Unsupported route label"):
            set_actual_route("private command content")
        assert get_actual_route() == "unknown"
    finally:
        reset_route_trace(token)
