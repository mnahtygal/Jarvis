"""Regression coverage for read-only planning and executable approval handoff."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core import developer_bridge, orchestrator
from core.developer_agent.tool_models import failure_result, success_result
from core.developer_agent.workspace import Workspace
from core.request_classifier import RequestIntent, classify_request


@pytest.fixture(autouse=True)
def _reset_approval_state():
    developer_bridge.reset_developer_approval_state()
    yield
    developer_bridge.reset_developer_approval_state()


def _inspection_command(workspace: Path, *paths: str, padding: bool = False) -> str:
    filler = (
        "\nThe local model is using deterministic settings. " * 30
        if padding
        else ""
    )
    files = "\n".join(f"- `{path}`" for path in paths)
    return (
        "# CODEX MISSION — DEVELOPER ARCHITECTURE REVIEW\n\n"
        f"**Workspace:** `{workspace}`\n\n"
        "## Phase One — Architectural Assessment\n\n"
        "Inspect these files before making changes:\n"
        f"{files}\n\n"
        "Inspect relevant test files after this bounded list.\n"
        "Stop after the architectural assessment."
        f"{filler}"
    )


def test_original_shape_long_mission_is_developer_planning_not_runtime_status(tmp_path):
    command = _inspection_command(
        tmp_path,
        "core/request_classifier.py",
        "core/developer_bridge.py",
        padding=True,
    )
    assert len(command) > developer_bridge.MAX_DEVELOPER_REQUEST_LENGTH

    classification = classify_request(command)

    assert classification.intent is RequestIntent.DEVELOPER
    assert classification.developer_request is not None
    assert classification.developer_request.mode == developer_bridge.DEVELOPER_INSPECTION

    flattened = "  ".join(command.splitlines())
    flattened_classification = classify_request(flattened)
    assert flattened_classification.intent is RequestIntent.DEVELOPER
    assert flattened_classification.developer_request is not None
    assert (
        flattened_classification.developer_request.mode
        == developer_bridge.DEVELOPER_INSPECTION
    )


def test_long_ambiguous_assessment_remains_non_executable(monkeypatch, tmp_path):
    command = (
        "# CODEX MISSION\n"
        f"**Workspace:** `{tmp_path}`\n"
        "Perform an architectural assessment and later implement broad changes.\n"
        + ("model using source code " * 80)
    )
    execute = Mock(side_effect=AssertionError("no developer tool may execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = orchestrator.process_request(command)

    assert result.intent is RequestIntent.DEVELOPER
    assert result.developer_status == "unsupported"
    assert result.approval_pending is False
    execute.assert_not_called()


def test_inspection_uses_only_bounded_read_file_and_reports_evidence(
    monkeypatch, tmp_path
):
    workspace = Workspace(tmp_path)
    paths = ("core/one.py", "core/two.py")
    execute = Mock(
        side_effect=[
            success_result(
                "developer.read_file",
                "1: ONE = 1",
                metadata={"bytes_read": 8},
            ),
            success_result(
                "developer.read_file",
                "1: TWO = 2",
                metadata={"bytes_read": 8},
            ),
        ]
    )
    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        lambda value: workspace,
    )
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    monkeypatch.setattr(
        developer_bridge,
        "_inspection_model_call",
        lambda prompt: "Verified findings:\n- Both modules define constants.\n\nInferences:\n- none",
    )

    result = orchestrator.process_request(_inspection_command(tmp_path, *paths))

    assert result.developer_status == "planning_complete"
    assert result.actual_route == "developer_planning"
    assert result.inspected_paths == paths
    assert result.uninspected_paths == ()
    assert result.approval_kind == "planning"
    assert result.approval_pending is False
    assert result.pending_action_id is None
    assert result.used_llm is True
    assert developer_bridge._pending_action is None
    assert "Inspected files: core/one.py, core/two.py" in result.response
    assert developer_bridge.PLANNING_ONLY_NOTICE in result.response
    assert execute.call_count == 2
    for call, path in zip(execute.call_args_list, paths, strict=True):
        assert call.args == (
            "developer.read_file",
            {
                "path": path,
                "max_bytes": developer_bridge.MAX_INSPECTION_FILE_BYTES,
            },
        )
        assert call.kwargs == {"workspace": workspace}


def test_inspection_operates_with_canonical_read_tool(monkeypatch, tmp_path):
    source = tmp_path / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    observed_prompt: list[str] = []

    def summarize(prompt: str) -> str:
        observed_prompt.append(prompt)
        return "Verified findings:\n- module.py defines VALUE.\n\nInferences:\n- none"

    monkeypatch.setattr(developer_bridge, "_inspection_model_call", summarize)

    result = orchestrator.process_request(
        _inspection_command(tmp_path, "module.py")
    )

    assert result.developer_status == "planning_complete"
    assert result.inspected_paths == ("module.py",)
    assert observed_prompt
    assert "1: VALUE = 1" in observed_prompt[0]
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_model_file_access_claim_is_withheld(monkeypatch, tmp_path):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        lambda value: workspace,
    )
    monkeypatch.setattr(
        developer_bridge,
        "execute_tool",
        lambda *args, **kwargs: success_result(
            "developer.read_file",
            "1: SAFE = True",
            metadata={"bytes_read": 11},
        ),
    )
    monkeypatch.setattr(
        developer_bridge,
        "_inspection_model_call",
        lambda prompt: "I inspected secret.py and everything is safe.",
    )

    result = orchestrator.process_request(
        _inspection_command(tmp_path, "core/safe.py")
    )

    assert "I inspected secret.py" not in result.response
    assert "unverifiable file-inspection claim" in result.response
    assert result.inspected_paths == ("core/safe.py",)


def test_planning_model_cannot_request_executable_approval(monkeypatch, tmp_path):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        lambda value: workspace,
    )
    monkeypatch.setattr(
        developer_bridge,
        "execute_tool",
        lambda *args, **kwargs: success_result(
            "developer.read_file",
            "1: SAFE = True",
            metadata={"bytes_read": 11},
        ),
    )
    monkeypatch.setattr(
        developer_bridge,
        "_inspection_model_call",
        lambda prompt: "Reply exactly 'approve' so I can implement this.",
    )

    result = orchestrator.process_request(
        _inspection_command(tmp_path, "core/safe.py")
    )

    assert "Reply exactly 'approve'" not in result.response
    assert "non-authorizing executable approval language" in result.response
    assert result.approval_pending is False


def test_sensitive_or_unreadable_files_are_not_reported_as_inspected(
    monkeypatch, tmp_path
):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        lambda value: workspace,
    )
    monkeypatch.setattr(
        developer_bridge,
        "execute_tool",
        lambda *args, **kwargs: failure_result(
            "developer.read_file", "sensitive_file", "refused"
        ),
    )
    model = Mock(side_effect=AssertionError("model must not run without evidence"))
    monkeypatch.setattr(developer_bridge, "_inspection_model_call", model)

    result = orchestrator.process_request(
        _inspection_command(tmp_path, ".env.local")
    )

    assert result.developer_status == "rejected"
    assert result.inspected_paths == ()
    assert result.uninspected_paths == (".env.local:sensitive_file",)
    assert "Inspected files: none" in result.response
    assert result.approval_pending is False
    model.assert_not_called()


def test_inspection_preserves_sensitive_and_symlink_read_boundaries(
    monkeypatch, tmp_path
):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = True\n", encoding="utf-8")
    (root / "linked.py").symlink_to(outside)
    model = Mock(side_effect=AssertionError("model must not run without evidence"))
    monkeypatch.setattr(developer_bridge, "_inspection_model_call", model)

    result = orchestrator.process_request(
        _inspection_command(root, ".env.local", "linked.py")
    )

    assert result.inspected_paths == ()
    assert result.uninspected_paths == (
        ".env.local:sensitive_file",
        "linked.py:outside_workspace",
    )
    assert result.approval_pending is False
    model.assert_not_called()


def test_planning_acceptance_cannot_execute_or_create_authority(monkeypatch):
    execute = Mock(side_effect=AssertionError("planning acceptance cannot execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    accepted = orchestrator.process_request("accept plan")
    approved = orchestrator.process_request("approve")

    assert accepted.developer_status == "planning_accepted"
    assert accepted.approval_kind == "planning"
    assert accepted.approval_pending is False
    assert approved.developer_error_code == "no_pending_action"
    execute.assert_not_called()


def test_conversational_approval_request_is_deterministically_disclaimed(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: "Requesting explicit approval to proceed with implementation.",
    )

    result = orchestrator.process_request("Discuss a possible future refactor")

    assert result.approval_kind == "none"
    assert result.approval_pending is False
    assert result.response == developer_bridge.PLANNING_ONLY_NOTICE
    assert "Requesting explicit approval" not in result.response
    assert developer_bridge._pending_action is None


def test_incomplete_execution_scope_cannot_create_pending_approval(monkeypatch):
    execute = Mock(side_effect=AssertionError("incomplete scope cannot execute"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    result = orchestrator.process_request("Patch this function")
    approved = orchestrator.process_request("approve")

    assert result.developer_status == "confirmation_required"
    assert result.approval_kind == "none"
    assert result.approval_pending is False
    assert "no approval is pending" in result.response
    assert approved.developer_error_code == "no_pending_action"
    execute.assert_not_called()


def test_valid_action_exposes_one_correlated_pending_identifier(
    monkeypatch, tmp_path
):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: workspace)
    execute = Mock(return_value=success_result("developer.write_file", "written"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    proposed = orchestrator.process_request("Create demo.py with hello")
    approved = orchestrator.process_request("approve")
    replay = orchestrator.process_request("approve")

    assert proposed.approval_kind == "execution"
    assert proposed.approval_pending is True
    assert proposed.pending_action_id
    assert proposed.metadata["approval_kind"] == "execution"
    assert proposed.metadata["approval_pending"] is True
    assert proposed.metadata["pending_action_id"] == proposed.pending_action_id
    assert approved.approval_kind == "execution"
    assert approved.approval_pending is False
    assert approved.pending_action_id == proposed.pending_action_id
    assert approved.developer_status == "executed"
    assert replay.developer_error_code == "no_pending_action"
    assert replay.approval_pending is False
    execute.assert_called_once()
