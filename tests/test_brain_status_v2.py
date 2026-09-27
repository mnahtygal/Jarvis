from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from core import brain_status_v2, orchestrator, router
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.memory_persistence import MemoryPersistenceResult


def _reset_status(monkeypatch):
    monkeypatch.setattr(brain_status_v2, "_latest_status", None)


def test_no_request_returns_idle_status(monkeypatch):
    _reset_status(monkeypatch)

    status = get_brain_v2_status()

    assert status.state == "idle"
    assert status.intent is None
    assert status.brain_version == "2.0-phase8"
    assert "no request processed" in get_brain_v2_status_response()


def test_factual_request_publishes_safe_status(monkeypatch):
    _reset_status(monkeypatch)
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")

    orchestrator.process_request("what is PostgreSQL")
    status = get_brain_v2_status()

    assert status.state == "complete"
    assert status.intent == "factual_question"
    assert status.execution_strategy == "llm"
    assert status.context_sources == ()
    assert status.evaluation_quality == "good"
    assert status.memory_type == "none"


def test_semantic_request_publishes_context_sources(monkeypatch):
    _reset_status(monkeypatch)
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")

    orchestrator.process_request("what did I tell you about Jarvis memory")
    status = get_brain_v2_status()

    assert status.context_sources == (
        "exact_memory",
        "semantic_memory",
        "recent_history",
    )
    assert status.memory_type == "none"


def test_project_note_publishes_memory_and_persistence_status(monkeypatch):
    _reset_status(monkeypatch)
    monkeypatch.setattr(orchestrator, "route", lambda command: "safe response")
    monkeypatch.setattr(
        orchestrator,
        "persist_project_note",
        lambda content, decision: MemoryPersistenceResult(
            False,
            "semantic_memory",
            "duplicate",
            "duplicate project note",
        ),
    )

    orchestrator.process_request("We should build satellite tracking someday.")
    status = get_brain_v2_status()

    assert status.memory_should_store is True
    assert status.memory_type == "project_note"
    assert status.memory_persistence_status == "duplicate"
    assert status.memory_persistence_target == "semantic_memory"


def test_deterministic_status_command_does_not_expose_request_content(monkeypatch):
    _reset_status(monkeypatch)
    monkeypatch.setattr(orchestrator, "route", lambda command: "private response")
    orchestrator.process_request("what is PostgreSQL")

    response = router.route("brain v2 status")

    assert "PostgreSQL" not in response
    assert "private response" not in response
    assert "Brain v2:" in response
    assert "Strategy: llm" in response


def test_route_exception_publishes_safe_failed_status(monkeypatch):
    _reset_status(monkeypatch)
    secret = "raw database password"
    monkeypatch.setattr(orchestrator, "route", lambda command: (_ for _ in ()).throw(RuntimeError(secret)))

    try:
        orchestrator.process_request("what is PostgreSQL")
    except RuntimeError:
        pass
    else:
        raise AssertionError("router exception was swallowed")

    status = get_brain_v2_status()
    assert status.state == "failed"
    assert status.evaluation_quality == "failed"
    assert secret not in repr(status)


def test_repeated_requests_replace_only_latest_snapshot(monkeypatch):
    monkeypatch.setattr(orchestrator, "route", lambda command: "response")

    orchestrator.process_request("what is PostgreSQL")
    orchestrator.process_request("brain status")

    status = get_brain_v2_status()
    assert status.intent == "runtime_status"
    assert status.execution_strategy == "system"
    assert status.state == "complete"


def test_legacy_brain_status_still_uses_existing_handler(monkeypatch):
    legacy = Mock(return_value="unchanged legacy health output")
    lifecycle = Mock(side_effect=AssertionError("unexpected v2 status call"))
    monkeypatch.setattr(router, "get_brain_status_response", legacy)
    monkeypatch.setattr(router, "get_brain_v2_status_response", lifecycle)

    assert router.route("brain status") == "unchanged legacy health output"
    legacy.assert_called_once_with()
    lifecycle.assert_not_called()


@pytest.mark.parametrize("command", ["brain v2 status", "jarvis brain v2 status"])
def test_v2_status_aliases_use_single_router_call(monkeypatch, command):
    _reset_status(monkeypatch)
    routed = Mock(wraps=router.route)
    monkeypatch.setattr(orchestrator, "route", routed)
    monkeypatch.setattr(router, "get_llm_response", Mock(side_effect=AssertionError("unexpected LLM call")))

    result = orchestrator.process_request(command)

    routed.assert_called_once_with(command)
    assert "idle (no request processed yet)" in result.response
    assert get_brain_v2_status().intent == "runtime_status"


def test_snapshot_is_immutable_and_replaced_without_mutating_previous(monkeypatch):
    _reset_status(monkeypatch)
    monkeypatch.setattr(orchestrator, "route", lambda command: "private response")
    orchestrator.process_request("what did I tell you about Jarvis memory")
    previous = get_brain_v2_status()
    with pytest.raises(FrozenInstanceError):
        previous.intent = "changed"

    orchestrator.process_request("what is PostgreSQL")
    current = get_brain_v2_status()
    assert current is not previous
    assert previous.context_sources == ("exact_memory", "semantic_memory", "recent_history")
    assert current.context_sources == ()
    assert "private response" not in repr(current)
