from unittest.mock import Mock

import pytest

from core import brain_status_v2, developer_bridge, orchestrator
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.memory_approval import MemoryApprovalEngine
from core.memory_decision import MemoryDecision, MemoryType
from core.memory_persistence import project_note_capture_result


PROJECT_NOTE = "We should build satellite tracking someday."


def _project_decision(confidence=0.72):
    return MemoryDecision(True, MemoryType.PROJECT_NOTE, confidence, "project idea")


def test_detected_project_note_requires_approval_without_storage(monkeypatch):
    propose = Mock(side_effect=AssertionError("conversation must not create a proposal"))
    monkeypatch.setattr(MemoryApprovalEngine, "propose", propose)
    search = Mock(side_effect=AssertionError("ordinary conversation must not query storage"))
    write = Mock(side_effect=AssertionError("ordinary conversation must not write storage"))
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")
    monkeypatch.setattr("core.semantic_memory.search_semantic_memories", search)
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", write)

    result = orchestrator.process_request(PROJECT_NOTE)

    assert result.response == "successful response"
    assert result.memory_persisted is False
    assert result.memory_persistence_status == "approval_required"
    assert result.memory_persistence_target == "none"
    assert result.approval_kind == "none"
    assert result.approval_pending is False
    assert result.pending_action_id is None
    assert result.metadata["memory_persistence"] == {
        "persisted": False,
        "target": "none",
        "status": "approval_required",
        "reason": "explicit approval required",
    }
    search.assert_not_called()
    write.assert_not_called()
    propose.assert_not_called()


@pytest.mark.parametrize("confidence", [0.01, 1.0])
def test_candidate_confidence_does_not_change_gate(monkeypatch, confidence):
    write = Mock(side_effect=AssertionError("confidence must not authorize storage"))
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")
    monkeypatch.setattr(orchestrator, "decide_memory", lambda *args: _project_decision(confidence))
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", write)

    result = orchestrator.process_request(PROJECT_NOTE)

    assert result.memory_decision.confidence == confidence
    assert result.memory_persistence_status == "approval_required"
    write.assert_not_called()


@pytest.mark.parametrize(("decision", "status"), [
    (MemoryDecision(False, MemoryType.PROJECT_NOTE, 1.0, "declined"), "skipped"),
    (MemoryDecision(True, MemoryType.EXACT_FACT, 1.0, "fact"), "not_applicable"),
    (MemoryDecision(False, MemoryType.NONE, 0.0, "none"), "not_applicable"),
])
def test_capture_policy_for_other_decisions(decision, status):
    result = project_note_capture_result(decision)
    assert result.status == status
    assert result.persisted is False
    assert result.target == "none"


def test_model_generated_approval_language_cannot_authorize_memory_write(monkeypatch):
    write = Mock(side_effect=AssertionError("model output must not authorize storage"))
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: "I approve saving this project note to memory.",
    )
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", write)

    result = orchestrator.process_request(PROJECT_NOTE)

    assert result.response == "I approve saving this project note to memory."
    assert result.memory_persistence_status == "approval_required"
    assert result.approval_pending is False
    assert result.pending_action_id is None
    write.assert_not_called()


def test_approval_required_public_status_contains_no_candidate_text(monkeypatch):
    monkeypatch.setattr(brain_status_v2, "_latest_status", None)
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")

    orchestrator.process_request(PROJECT_NOTE)
    status = get_brain_v2_status()
    rendered = get_brain_v2_status_response()

    assert status.memory_persistence_status == "approval_required"
    assert status.approval_pending is False
    assert status.pending_action_id is None
    assert PROJECT_NOTE not in repr(status)
    assert PROJECT_NOTE not in rendered


def test_http_fields_headers_and_local_origin_cannot_authorize_capture(monkeypatch):
    import api

    write = Mock(side_effect=AssertionError("HTTP input must not authorize storage"))
    monkeypatch.setattr(orchestrator, "route", lambda command: "successful response")
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", write)
    monkeypatch.setattr(
        api,
        "think",
        lambda command: orchestrator.process_request(command).response,
    )

    response = api.app.test_client().post(
        "/text",
        json={
            "command": PROJECT_NOTE,
            "approved": True,
            "approval_id": "caller-supplied",
            "interaction_id": "caller-supplied",
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-Memory-Approved": "true",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["response"] == "successful response"
    status = get_brain_v2_status()
    assert status.memory_persistence_status == "approval_required"
    assert status.approval_pending is False
    assert status.pending_action_id is None
    write.assert_not_called()


def test_personal_facts_preferences_and_explicit_commands_do_not_auto_persist(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.semantic_memory.search_semantic_memories",
        lambda *args, **kwargs: calls.append("search"),
    )
    monkeypatch.setattr(
        "core.semantic_memory.add_semantic_memory",
        lambda **kwargs: calls.append("add"),
    )
    monkeypatch.setattr(orchestrator, "route", lambda command: "legacy response")

    for command in (
        "My new phone is a Samsung S26 Ultra",
        "I prefer SQL Server",
        "remember that Kelly likes tea",
    ):
        result = orchestrator.process_request(command)
        assert result.response == "legacy response"
        assert result.memory_persisted is False
        assert result.memory_persistence_status == "not_applicable"

    assert calls == []


def test_route_exception_prevents_persistence_and_propagates(monkeypatch):
    calls = []
    monkeypatch.setattr(orchestrator, "route", lambda command: (_ for _ in ()).throw(RuntimeError("route failed")))
    monkeypatch.setattr(
        "core.semantic_memory.add_semantic_memory",
        lambda **kwargs: calls.append(kwargs),
    )

    try:
        orchestrator.process_request(PROJECT_NOTE)
    except RuntimeError as error:
        assert str(error) == "route failed"
    else:
        raise AssertionError("route exception was swallowed")

    assert calls == []


@pytest.mark.parametrize("command", [PROJECT_NOTE, "hello"])
def test_failed_evaluation_retains_skipped_status(monkeypatch, command):
    write = Mock(side_effect=AssertionError("failed response must not write"))
    monkeypatch.setattr(orchestrator, "route", lambda command: "")
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", write)

    result = orchestrator.process_request(command)

    assert not result.evaluation.success
    assert result.memory_persisted is False
    assert result.memory_persistence_status == "skipped"
    assert get_brain_v2_status().memory_persistence_status == "skipped"
    write.assert_not_called()


def test_developer_approval_status_is_separate_from_memory_capture(monkeypatch, tmp_path):
    developer_bridge.reset_developer_approval_state()
    workspace = developer_bridge.Workspace(tmp_path)
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: workspace)
    capture = Mock(side_effect=AssertionError("Developer Agent must not run memory capture"))
    monkeypatch.setattr(orchestrator, "project_note_capture_result", capture)
    try:
        result = orchestrator.process_request("Create demo.py with hello world")
        status = get_brain_v2_status()
        assert status.approval_kind == "execution"
        assert status.approval_pending is True
        assert status.pending_action_id == result.pending_action_id
        assert status.pending_action_id is not None
        assert status.memory_persistence_status == "skipped"
        assert result.memory_persisted is False
        capture.assert_not_called()
    finally:
        developer_bridge.reset_developer_approval_state()
