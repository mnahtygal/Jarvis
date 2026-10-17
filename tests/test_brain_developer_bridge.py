"""Phase 1 Brain-to-Developer Agent bridge tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import api
from core import brain, developer_bridge, orchestrator
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.developer_agent.tool_models import failure_result, success_result
from core.developer_bridge import (
    DEVELOPER_CONFIRMATION_REQUIRED,
    DEVELOPER_EXECUTABLE,
    PHASE1_EXECUTION_ALLOWLIST,
    DeveloperBridgeResult,
    DeveloperRequest,
    execute_developer_request,
)
from core.execution_strategy import ExecutionStrategy
from core.request_classifier import RequestIntent, classify_request


def test_phase1_execution_allowlist_is_exact():
    assert PHASE1_EXECUTION_ALLOWLIST == frozenset({
        "developer.list_files",
        "developer.read_file",
        "developer.git_status",
    })


@pytest.mark.parametrize(
    "command,capability_id,arguments,output",
    [
        (
            "Read core/brain.py",
            "developer.read_file",
            {"path": "core/brain.py"},
            "1: # core/brain.py",
        ),
        (
            "Show me git status",
            "developer.git_status",
            {},
            "## feature/jarvis-developer-agent",
        ),
        (
            "List files in core/developer_agent",
            "developer.list_files",
            {"path": "core/developer_agent"},
            "core/developer_agent/executor.py",
        ),
    ],
)
def test_read_only_requests_execute_one_canonical_tool(
    monkeypatch, command, capability_id, arguments, output
):
    execute = Mock(return_value=success_result(capability_id, output))
    legacy_router = Mock(side_effect=AssertionError("legacy router should not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    monkeypatch.setattr(orchestrator, "route", legacy_router)

    result = orchestrator.process_request(command)

    assert result.intent is RequestIntent.DEVELOPER
    assert result.execution_strategy is ExecutionStrategy.DEVELOPER_TOOL
    assert result.route_type == "developer_bridge"
    assert result.actual_route == "developer_tool"
    assert result.developer_status == "executed"
    assert result.developer_capability_id == capability_id
    assert result.developer_tool_invoked is True
    assert result.developer_tool_success is True
    assert result.response == output
    assert result.evaluation.success is True
    assert result.evaluation.reason == "developer tool execution succeeded"
    execute.assert_called_once_with(capability_id, arguments)
    legacy_router.assert_not_called()


@pytest.mark.parametrize(
    "command,capability_id",
    [
        ("Create a Python file", "developer.write_file"),
        ("Patch this function", "developer.patch_file"),
        ("Run pytest", "developer.run_command"),
        ("Run the Gradle test", "developer.gradle_test"),
        ("Repair the failing test", "developer.repair_loop"),
        ("Fix the failing unit test", "developer.repair_loop"),
        ("Propose a repair", "developer.propose_repair"),
        ("Stage the changes", "developer.git_stage"),
        ("Commit the verified changes", "developer.git_commit"),
        ("Run a bounded session", "developer.bounded_session"),
    ],
)
def test_confirmation_required_requests_never_execute(
    monkeypatch, command, capability_id
):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    legacy_router = Mock(side_effect=AssertionError("legacy router should not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    monkeypatch.setattr(orchestrator, "route", legacy_router)

    result = orchestrator.process_request(command)

    assert result.intent is RequestIntent.DEVELOPER
    assert result.execution_strategy is ExecutionStrategy.DEVELOPER_CONFIRMATION
    assert result.actual_route == "developer_confirmation"
    assert result.developer_status == DEVELOPER_CONFIRMATION_REQUIRED
    assert result.developer_capability_id == capability_id
    assert result.developer_tool_invoked is False
    assert result.evaluation.success is False
    assert result.evaluation.quality == "confirmation_required"
    assert "nothing was executed" in result.response
    execute.assert_not_called()
    legacy_router.assert_not_called()


def test_ambiguous_developer_request_does_not_execute_or_fall_back(monkeypatch):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    legacy_router = Mock(side_effect=AssertionError("legacy router should not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    monkeypatch.setattr(orchestrator, "route", legacy_router)

    result = orchestrator.process_request("Handle this developer task")

    assert result.intent is RequestIntent.DEVELOPER
    assert result.execution_strategy is ExecutionStrategy.DEVELOPER_UNSUPPORTED
    assert result.actual_route == "developer_unsupported"
    assert result.developer_status == "unsupported"
    assert result.evaluation.quality == "unsupported"
    assert "Nothing was executed" in result.response
    execute.assert_not_called()
    legacy_router.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        "Read ../outside.txt",
        "Read /etc/passwd",
        "List files in ../../",
        "Read a file",
        "Read ~/secret.txt",
        "Read $HOME/secret.txt",
        "Read %HOME%/secret.txt",
        "Read core/brain.py;id",
        "Read core/brain.py&&id",
        "Read `id`.txt",
        "Read core/a.py,core/b.py",
        "Read 'core/brain.py",
        "Read core/brain.py\nRun pytest",
        "Read " + ("a" * 501) + ".py",
    ],
)
def test_ambiguous_or_traversal_paths_are_refused_before_dispatch(monkeypatch, command):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = orchestrator.process_request(command)

    assert result.intent is RequestIntent.DEVELOPER
    assert result.developer_status == "unsupported"
    assert result.developer_tool_invoked is False
    execute.assert_not_called()


def test_canonical_tool_policy_failure_is_safely_adapted(monkeypatch):
    execute = Mock(return_value=failure_result(
        "developer.read_file",
        "outside_workspace",
        "File is not available in the workspace",
    ))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = orchestrator.process_request("Read linked/file.py")

    assert result.actual_route == "developer_tool"
    assert result.developer_status == "rejected"
    assert result.developer_tool_success is False
    assert result.developer_error_code == "outside_workspace"
    assert result.evaluation.success is False
    assert result.evaluation.reason == "developer tool validation or policy failure"
    assert "outside_workspace" in result.response


def test_phase1_allowlist_cannot_be_bypassed(monkeypatch):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    request = DeveloperRequest(
        DEVELOPER_EXECUTABLE,
        "developer.write_file",
        {"path": "unsafe.py", "content": "content"},
    )

    result = execute_developer_request(request)

    assert result.status == "rejected"
    assert result.error_code == "capability_not_allowed"
    execute.assert_not_called()


@pytest.mark.parametrize(
    "brain_changes,developer_changes,error_code",
    [
        ({"executable": False}, {}, "capability_not_executable"),
        ({}, {"executable": False}, "capability_not_executable"),
        ({"enabled": False}, {}, "capability_disabled"),
        ({}, {"enabled": False}, "capability_disabled"),
        ({}, {"requires_confirmation": True}, "confirmation_required"),
        ({"requires_confirmation": True}, {}, "confirmation_required"),
        ({"read_only": False}, {}, "capability_not_read_only"),
        ({}, {"read_only": False}, "capability_not_read_only"),
        ({"mutating": True}, {}, "capability_mutating"),
        ({}, {"mutating": True}, "capability_mutating"),
    ],
)
def test_metadata_cannot_override_fail_closed_checks(
    monkeypatch, brain_changes, developer_changes, error_code
):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    brain_metadata = {
        "capability_id": "developer.read_file",
        "enabled": True,
        "executable": True,
        "read_only": True,
        "mutating": False,
        "requires_confirmation": False,
    }
    developer_metadata = dict(brain_metadata)
    developer_metadata["tool_id"] = developer_metadata.pop("capability_id")
    brain_metadata.update(brain_changes)
    developer_metadata.update(developer_changes)
    monkeypatch.setattr(
        developer_bridge,
        "get_capability",
        lambda capability_id: SimpleNamespace(**brain_metadata),
    )
    monkeypatch.setattr(
        developer_bridge,
        "get_tool",
        lambda capability_id: SimpleNamespace(**developer_metadata),
    )
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = execute_developer_request(DeveloperRequest(
        DEVELOPER_EXECUTABLE,
        "developer.read_file",
        {"path": "core/brain.py"},
    ))

    assert result.status == "rejected"
    assert result.error_code == error_code
    execute.assert_not_called()


@pytest.mark.parametrize("missing_registry", ["brain", "developer"])
def test_missing_registry_entry_fails_closed(monkeypatch, missing_registry):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    if missing_registry == "brain":
        monkeypatch.setattr(
            developer_bridge, "get_capability", lambda capability_id: None
        )
    else:
        monkeypatch.setattr(developer_bridge, "get_tool", lambda capability_id: None)
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = execute_developer_request(DeveloperRequest(
        DEVELOPER_EXECUTABLE,
        "developer.git_status",
    ))

    assert result.error_code == "capability_not_registered"
    execute.assert_not_called()


def test_mismatched_registry_identity_fails_closed(monkeypatch):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    real_tool = developer_bridge.get_tool("developer.read_file")
    monkeypatch.setattr(
        developer_bridge,
        "get_tool",
        lambda capability_id: SimpleNamespace(
            **{
                **real_tool.__dict__,
                "tool_id": "developer.git_status",
            }
        ),
    )
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = execute_developer_request(DeveloperRequest(
        DEVELOPER_EXECUTABLE,
        "developer.read_file",
        {"path": "core/brain.py"},
    ))

    assert result.error_code == "capability_metadata_mismatch"
    execute.assert_not_called()


def test_canonical_executor_rejects_unknown_argument_schema():
    result = execute_developer_request(DeveloperRequest(
        DEVELOPER_EXECUTABLE,
        "developer.read_file",
        {"path": "core/brain.py", "unsupported": True},
    ))

    assert result.status == "rejected"
    assert result.tool_invoked is True
    assert result.tool_success is False
    assert result.error_code == "invalid_arguments"


def test_existing_non_developer_routes_are_unchanged(monkeypatch):
    routed = Mock(return_value="legacy response")
    monkeypatch.setattr(orchestrator, "route", routed)

    result = orchestrator.process_request("hello")

    assert result.intent is RequestIntent.CONVERSATION
    assert result.route_type == "legacy_router"
    assert result.response == "legacy response"
    routed.assert_called_once_with("hello")


def test_developer_success_without_structured_invocation_evidence_is_blocked(
    monkeypatch
):
    monkeypatch.setattr(
        orchestrator,
        "execute_developer_request",
        lambda request: DeveloperBridgeResult(
            "executed_success",
            "developer.read_file",
            "Created files and 5 tests passed.",
            tool_invoked=False,
            tool_success=True,
        ),
    )

    result = orchestrator.process_request("Read core/brain.py")

    assert result.developer_status == "truthfulness_blocked"
    assert result.developer_tool_invoked is False
    assert result.developer_tool_success is False
    assert result.developer_error_code == "missing_invocation_evidence"
    assert result.evaluation.success is False
    assert "5 tests passed" not in result.response
    assert result.metadata["llm_fallback_used"] is False


def test_developer_invocation_evidence_cannot_be_attached_to_non_success_status(
    monkeypatch
):
    monkeypatch.setattr(
        orchestrator,
        "execute_developer_request",
        lambda request: DeveloperBridgeResult(
            "rejected",
            "developer.read_file",
            "This result is internally inconsistent.",
            tool_invoked=True,
            tool_success=True,
        ),
    )

    result = orchestrator.process_request("Read core/brain.py")

    assert result.developer_status == "truthfulness_blocked"
    assert result.developer_tool_invoked is False
    assert result.developer_tool_success is False
    assert result.evaluation.success is False


def test_developer_status_is_structured_and_does_not_expose_response(monkeypatch):
    private_output = "private file contents"
    monkeypatch.setattr(
        developer_bridge,
        "execute_tool",
        lambda tool_id, arguments: success_result(tool_id, private_output),
    )

    orchestrator.process_request("Read core/brain.py")
    status = get_brain_v2_status()
    rendered = get_brain_v2_status_response()

    assert status.developer_status == "executed"
    assert status.developer_capability_id == "developer.read_file"
    assert status.developer_tool_invoked is True
    assert private_output not in repr(status)
    assert private_output not in rendered
    assert "core/brain.py" not in rendered


def test_text_api_uses_developer_bridge(monkeypatch):
    monkeypatch.setattr(brain, "remember_user_message", lambda message: None)
    monkeypatch.setattr(brain, "remember_assistant_message", lambda message: None)
    monkeypatch.setattr(
        developer_bridge,
        "execute_tool",
        lambda tool_id, arguments: success_result(tool_id, "1: safe content"),
    )
    client = api.app.test_client()

    response = client.post("/text", json={"command": "Read core/brain.py"})

    assert response.status_code == 200
    assert response.get_json()["response"] == "1: safe content"
    assert get_brain_v2_status().actual_route == "developer_tool"


def test_voice_api_uses_developer_bridge_without_voice_hardware(monkeypatch):
    monkeypatch.setattr(api, "listen_command", lambda: "Run pytest")
    monkeypatch.setattr(api, "speak", lambda response: None)
    monkeypatch.setattr(brain, "remember_user_message", lambda message: None)
    monkeypatch.setattr(brain, "remember_assistant_message", lambda message: None)
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    client = api.app.test_client()

    response = client.post("/ask", json={"use_voice": False})

    assert response.status_code == 200
    assert "nothing was executed" in response.get_json()["response"]
    assert get_brain_v2_status().actual_route == "developer_confirmation"
    execute.assert_not_called()


def test_help_and_docs_phrases_are_not_hijacked_as_file_reads():
    assert classify_request("show documentation").intent is RequestIntent.HELP_OR_DOCS
    assert classify_request("open docs").intent is RequestIntent.HELP_OR_DOCS


@pytest.mark.parametrize(
    "command",
    [
        "Read me a story",
        "Create a shopping list",
        "Run through the plan with me",
        "What's the status of the weather?",
        "Commit to exercising every day",
        "Test my knowledge of Python",
        "Patch things up with a friend",
        "Create a Python lesson",
        "Run through the test results with me",
    ],
)
def test_common_words_do_not_create_developer_intent_or_execute(monkeypatch, command):
    execute = Mock(side_effect=AssertionError("developer tool must not execute"))
    routed = Mock(return_value="ordinary response")
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    monkeypatch.setattr(orchestrator, "route", routed)

    classification = classify_request(command)
    result = orchestrator.process_request(command)

    assert classification.intent is not RequestIntent.DEVELOPER
    assert result.intent is not RequestIntent.DEVELOPER
    assert result.response == "ordinary response"
    execute.assert_not_called()
    routed.assert_called_once_with(command)


def test_balanced_quoted_path_is_deterministic(monkeypatch):
    execute = Mock(return_value=success_result(
        "developer.read_file", "1: safe content"
    ))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = orchestrator.process_request("Read 'core/brain.py'")

    assert result.actual_route == "developer_tool"
    execute.assert_called_once_with(
        "developer.read_file", {"path": "core/brain.py"}
    )
