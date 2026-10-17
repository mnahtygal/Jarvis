"""Phase 2 explicit-approval continuation security tests."""

from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import api
from core import brain, developer_bridge, orchestrator
from core.brain_status_v2 import get_brain_v2_status
from core.developer_agent import git_safety
from core.developer_agent.command_policy import CommandPolicyError
from core.developer_agent.tool_models import failure_result, success_result
from core.developer_agent.workspace import Workspace


@pytest.fixture(autouse=True)
def _reset_approval_state():
    developer_bridge.reset_developer_approval_state()
    yield
    developer_bridge.reset_developer_approval_state()


@pytest.fixture
def isolated_workspace(monkeypatch, tmp_path):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: workspace)
    return workspace


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    )


def _init_git(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Jarvis Test")
    _git(root, "config", "user.email", "jarvis@example.invalid")


def test_phase2_approval_allowlist_is_exact():
    assert developer_bridge.PHASE2_APPROVAL_ALLOWLIST == frozenset({
        "developer.write_file",
        "developer.patch_file",
        "developer.run_command",
        "developer.gradle_test",
        "developer.git_stage",
        "developer.git_commit",
    })


def test_write_requires_confirmation_and_approval_executes_once(isolated_workspace):
    target = isolated_workspace.root / "demo.py"

    proposed = orchestrator.process_request("Create demo.py with hello world")
    assert proposed.developer_status == "confirmation_required"
    assert proposed.actual_route == "developer_confirmation"
    assert not target.exists()

    approved = orchestrator.process_request("approve")
    assert approved.developer_status == "executed"
    assert approved.actual_route == "developer_tool"
    assert target.read_text(encoding="utf-8") == "hello world"

    replay = orchestrator.process_request("approve")
    assert replay.developer_tool_invoked is False
    assert replay.developer_error_code == "no_pending_action"
    assert target.read_text(encoding="utf-8") == "hello world"


def test_destination_appearing_before_write_approval_fails(isolated_workspace):
    target = isolated_workspace.root / "demo.py"
    orchestrator.process_request("Create demo.py with proposed")
    target.write_text("external\n", encoding="utf-8")

    refused = orchestrator.process_request("approve")
    assert refused.developer_status == "validation_failed"
    assert refused.developer_error_code == "target_exists"
    assert target.read_text() == "external\n"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_failed_execution_cannot_restore_pending_authority(
    isolated_workspace, monkeypatch
):
    execute = Mock(return_value=failure_result(
        "developer.write_file", "write_failed", "write failed safely"
    ))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    orchestrator.process_request("Create demo.py with proposed")

    failed = orchestrator.process_request("approve")
    replay = orchestrator.process_request("approve")

    assert failed.developer_status == "rejected"
    assert failed.developer_tool_invoked is True
    assert replay.developer_error_code == "no_pending_action"
    assert execute.call_count == 1


def test_two_concurrent_approvals_invoke_at_most_once(
    isolated_workspace, monkeypatch
):
    started = threading.Event()
    release = threading.Event()
    results = []

    def execute(tool_id, arguments, *, workspace):
        started.set()
        assert release.wait(timeout=5)
        return success_result(tool_id, "done")

    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    orchestrator.process_request("Create demo.py with proposed")
    first = threading.Thread(
        target=lambda: results.append(orchestrator.process_request("approve")),
        daemon=True,
    )
    first.start()
    assert started.wait(timeout=5)
    second = orchestrator.process_request("approve")
    release.set()
    first.join(timeout=5)

    assert not first.is_alive()
    assert len(results) == 1
    assert results[0].developer_tool_invoked is True
    assert second.developer_tool_invoked is False
    assert second.developer_error_code == "no_pending_action"

def test_cancel_and_unrelated_conversation_clear_pending(isolated_workspace, monkeypatch):
    target = isolated_workspace.root / "demo.py"
    orchestrator.process_request("Create demo.py with hello world")
    cancelled = orchestrator.process_request("never mind")
    assert cancelled.developer_status == "cancelled"
    assert cancelled.actual_route == "developer_confirmation"
    assert not target.exists()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"

    orchestrator.process_request("Create demo.py with hello world")
    route = Mock(return_value="12:00")
    monkeypatch.setattr(orchestrator, "route", route)
    ordinary = orchestrator.process_request("What time is it?")
    assert ordinary.developer_error_code == "approval_not_recognized"
    assert "nothing was executed" in ordinary.response
    route.assert_not_called()
    assert not target.exists()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_new_developer_request_replaces_pending_action(isolated_workspace):
    orchestrator.process_request("Create first.py with first")
    orchestrator.process_request("Create second.py with second")
    result = orchestrator.process_request("approve")

    assert result.developer_capability_id == "developer.write_file"
    assert not (isolated_workspace.root / "first.py").exists()
    assert (isolated_workspace.root / "second.py").read_text() == "second"


@pytest.mark.parametrize(
    "command",
    [
        "Create ../outside.py with unsafe",
        "Create audio_pipeline_tester.py with unsafe",
    ],
)
def test_write_path_policy_blocks_before_pending(isolated_workspace, command):
    result = orchestrator.process_request(command)
    assert result.developer_tool_invoked is False
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_patch_is_exact_revalidated_and_not_replayed(isolated_workspace):
    target = isolated_workspace.root / "demo.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    proposed = orchestrator.process_request(
        'Patch demo.py replacing "VALUE = 1" with "VALUE = 2"'
    )
    assert proposed.developer_status == "confirmation_required"
    approved = orchestrator.process_request("execute it")
    assert approved.developer_status == "executed"
    assert target.read_text() == "VALUE = 2\n"
    duplicate = orchestrator.process_request("approve")
    assert duplicate.developer_error_code == "no_pending_action"
    assert target.read_text() == "VALUE = 2\n"


def test_patch_mismatch_and_source_change_fail_safely(isolated_workspace):
    target = isolated_workspace.root / "demo.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    mismatch = orchestrator.process_request(
        'Patch demo.py replacing "missing" with "replacement"'
    )
    assert mismatch.developer_error_code == "match_mismatch"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"

    orchestrator.process_request('Patch demo.py replacing "VALUE = 1" with "VALUE = 2"')
    target.write_text("VALUE = 3\n", encoding="utf-8")
    changed = orchestrator.process_request("approve")
    assert changed.developer_status == "validation_failed"
    assert changed.developer_tool_invoked is False
    assert target.read_text() == "VALUE = 3\n"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_patch_protected_path_is_blocked(isolated_workspace):
    target = isolated_workspace.root / "audio_pipeline_tester.py"
    target.write_text("VALUE = 1\n")
    refused = orchestrator.process_request(
        'Patch audio_pipeline_tester.py replacing "VALUE = 1" with "VALUE = 2"'
    )
    assert refused.developer_error_code == "protected_file"
    assert target.read_text() == "VALUE = 1\n"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_allowed_command_executes_only_after_approval(isolated_workspace):
    proposed = orchestrator.process_request("Run command: pwd")
    assert proposed.developer_status == "confirmation_required"
    result = orchestrator.process_request("run it")
    assert result.developer_status == "executed"
    assert result.response == str(isolated_workspace.root)


@pytest.mark.parametrize(
    "command",
    [
        "Run command: git push",
        "Run command: python arbitrary.py",
        "Run command: pwd ; id",
        "Run command: pytest *",
    ],
)
def test_command_policy_cannot_be_bypassed_by_approval(isolated_workspace, command):
    result = orchestrator.process_request(command)
    assert result.developer_tool_invoked is False
    assert result.developer_status in {"validation_failed", "unsupported"}
    approval = orchestrator.process_request("approve")
    assert approval.developer_error_code == "no_pending_action"


def test_command_policy_is_rerun_at_approval(isolated_workspace, monkeypatch):
    execute = Mock(side_effect=AssertionError("executor must not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    orchestrator.process_request("Run command: pwd")
    monkeypatch.setattr(
        developer_bridge,
        "validate_command",
        Mock(side_effect=CommandPolicyError("policy_changed", "policy changed")),
    )

    refused = orchestrator.process_request("approve")
    assert refused.developer_status == "validation_failed"
    assert refused.developer_error_code == "policy_changed"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"
    execute.assert_not_called()


def test_gradle_approval_uses_fixed_arguments(monkeypatch, isolated_workspace):
    policy = SimpleNamespace(version="8.0")
    monkeypatch.setattr(
        developer_bridge,
        "validate_gradle_project",
        lambda project_path, workspace: (workspace.root, policy, workspace.root),
    )
    execute = Mock(return_value=success_result(
        "developer.gradle_test",
        "tests passed",
        metadata={"command_family": "gradle_test", "exit_code": 0},
    ))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)

    proposed = orchestrator.process_request("Run Gradle test in .")
    assert proposed.developer_status == "confirmation_required"
    approved = orchestrator.process_request("approve")
    assert approved.developer_status == "executed"
    execute.assert_called_once_with(
        "developer.gradle_test",
        {"project_path": ".", "approved": True},
        workspace=isolated_workspace,
    )
    injected = orchestrator.process_request("Run Gradle test in . --stacktrace")
    assert injected.developer_status == "confirmation_required"
    assert "no approval is pending" in injected.response


def test_git_stage_only_explicit_unchanged_files(isolated_workspace):
    _init_git(isolated_workspace.root)
    one = isolated_workspace.root / "one.py"
    two = isolated_workspace.root / "two.py"
    one.write_text("ONE = 1\n")
    two.write_text("TWO = 2\n")

    proposed = orchestrator.process_request("Git stage one.py")
    assert proposed.developer_status == "confirmation_required"
    approved = orchestrator.process_request("approve")
    assert approved.developer_status == "executed"
    assert _git(isolated_workspace.root, "diff", "--cached", "--name-only").stdout == "one.py\n"

    assert "two.py" not in _git(isolated_workspace.root, "diff", "--cached", "--name-only").stdout


@pytest.mark.parametrize(
    "command",
    ["Git stage .", "Git stage -A", "Git stage --all", "Git stage *.py", "Git stage :(glob)"],
)
def test_git_stage_rejects_broad_pathspecs(isolated_workspace, command):
    _init_git(isolated_workspace.root)
    (isolated_workspace.root / "safe.py").write_text("SAFE = True\n")
    result = orchestrator.process_request(command)
    assert result.developer_tool_invoked is False
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_git_stage_detects_worktree_change_before_approval(isolated_workspace):
    _init_git(isolated_workspace.root)
    target = isolated_workspace.root / "safe.py"
    target.write_text("SAFE = 1\n")
    orchestrator.process_request("Git stage safe.py")
    target.write_text("SAFE = 2\n")
    result = orchestrator.process_request("approve")
    assert result.developer_status == "validation_failed"
    assert _git(isolated_workspace.root, "diff", "--cached", "--name-only").stdout == ""


def test_git_commit_requires_current_verification_and_never_auto_stages(isolated_workspace):
    _init_git(isolated_workspace.root)
    target = isolated_workspace.root / "safe.py"
    target.write_text("SAFE = True\n")
    without_evidence = orchestrator.process_request("Commit with message Safe checkpoint")
    assert without_evidence.developer_error_code == "verification_required"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"
    assert _git(isolated_workspace.root, "status", "--short").stdout == "?? safe.py\n"

    orchestrator.process_request("Git stage safe.py")
    assert orchestrator.process_request("approve").developer_status == "executed"
    orchestrator.process_request("Run command: python -m py_compile safe.py")
    assert orchestrator.process_request("approve").developer_status == "executed"
    proposed = orchestrator.process_request("Commit with message Safe checkpoint")
    assert proposed.developer_status == "confirmation_required"
    committed = orchestrator.process_request("approve")
    assert committed.developer_status == "executed"
    assert _git(isolated_workspace.root, "log", "-1", "--pretty=%s").stdout.strip() == "Safe checkpoint"


def test_git_commit_rejects_restaged_content_after_confirmation(isolated_workspace):
    _init_git(isolated_workspace.root)
    target = isolated_workspace.root / "safe.py"
    target.write_text("SAFE = 1\n")
    _git(isolated_workspace.root, "add", "safe.py")
    _git(isolated_workspace.root, "commit", "-q", "-m", "Base")
    target.write_text("SAFE = 2\n")
    orchestrator.process_request("Git stage safe.py")
    assert orchestrator.process_request("approve").developer_status == "executed"
    orchestrator.process_request("Run command: python -m py_compile safe.py")
    assert orchestrator.process_request("approve").developer_status == "executed"
    assert orchestrator.process_request(
        "Commit with message Safe checkpoint"
    ).developer_status == "confirmation_required"

    target.write_text("SAFE = 3\n")
    _git(isolated_workspace.root, "add", "safe.py")
    refused = orchestrator.process_request("approve")
    assert refused.developer_status == "validation_failed"
    assert refused.developer_tool_invoked is False
    assert _git(isolated_workspace.root, "log", "-1", "--pretty=%s").stdout.strip() == "Base"


def test_git_fingerprint_binds_untracked_contents_and_fails_closed_on_overflow(
    isolated_workspace, monkeypatch
):
    _init_git(isolated_workspace.root)
    target = isolated_workspace.root / "untracked.txt"
    target.write_text("one\n")
    first, error = git_safety.repository_state_fingerprint(isolated_workspace)
    assert error is None
    target.write_text("two\n")
    second, error = git_safety.repository_state_fingerprint(isolated_workspace)
    assert error is None
    assert first != second

    monkeypatch.setattr(
        git_safety,
        "_run_fixed",
        lambda workspace, arguments: git_safety.FixedGitResult(
            "output_too_large", None, b""
        ),
    )
    fingerprint, error = git_safety.repository_state_fingerprint(isolated_workspace)
    assert fingerprint is None
    assert error == "output_too_large"


def test_git_fingerprint_length_delimits_each_untracked_file(isolated_workspace):
    _init_git(isolated_workspace.root)
    first_path = isolated_workspace.root / "a"
    second_path = isolated_workspace.root / "b"
    second_marker = len(b"b").to_bytes(8, "big") + b"b"

    first_path.write_bytes(b"left")
    second_path.write_bytes(b"x" + second_marker + b"y")
    first, error = git_safety.repository_state_fingerprint(isolated_workspace)
    assert error is None

    first_path.write_bytes(b"left" + second_marker + b"x")
    second_path.write_bytes(b"y")
    second, error = git_safety.repository_state_fingerprint(isolated_workspace)
    assert error is None
    assert first != second


@pytest.mark.parametrize(
    "command",
    ["Repair the failing test", "Propose a repair", "Run a bounded session"],
)
def test_approval_cannot_dispatch_repair_or_session_tools(monkeypatch, command):
    execute = Mock(side_effect=AssertionError("blocked capability must not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    proposed = orchestrator.process_request(command)
    assert proposed.developer_status == "confirmation_required"
    assert "no approval is pending" in proposed.response
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"
    execute.assert_not_called()


def test_expired_pending_action_is_single_use(monkeypatch, isolated_workspace):
    clock = iter((100.0, 100.0 + developer_bridge.PENDING_ACTION_TTL_SECONDS + 1))
    monkeypatch.setattr(developer_bridge.time, "monotonic", lambda: next(clock))
    orchestrator.process_request("Create demo.py with hello")
    expired = orchestrator.process_request("approve")
    assert expired.developer_status == "expired"
    assert not (isolated_workspace.root / "demo.py").exists()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_registry_change_between_confirmation_and_approval_fails_closed(monkeypatch, isolated_workspace):
    orchestrator.process_request("Create demo.py with hello")
    real = developer_bridge.get_tool("developer.write_file")
    monkeypatch.setattr(
        developer_bridge,
        "get_tool",
        lambda tool_id: SimpleNamespace(**{**real.__dict__, "enabled": False}),
    )
    result = orchestrator.process_request("approve")
    assert result.developer_status == "policy_blocked"
    assert result.developer_tool_invoked is False


def test_registry_identity_and_dispatch_drift_fail_closed(
    monkeypatch, isolated_workspace
):
    orchestrator.process_request("Create demo.py with hello")
    real = developer_bridge.get_tool("developer.write_file")
    monkeypatch.setattr(
        developer_bridge,
        "get_tool",
        lambda tool_id: SimpleNamespace(
            **{**real.__dict__, "tool_id": "developer.patch_file"}
        ),
    )
    mismatch = orchestrator.process_request("approve")
    assert mismatch.developer_error_code == "capability_metadata_mismatch"
    assert mismatch.developer_tool_invoked is False

    monkeypatch.undo()
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: isolated_workspace)
    orchestrator.process_request("Create second.py with hello")
    monkeypatch.setattr(
        developer_bridge,
        "is_tool_dispatchable",
        lambda capability_id: False,
    )
    missing_handler = orchestrator.process_request("approve")
    assert missing_handler.developer_error_code == "capability_not_dispatchable"
    assert missing_handler.developer_tool_invoked is False


def test_pending_payload_and_contents_do_not_enter_brain_status(isolated_workspace):
    secret = "do-not-persist-this-value"
    result = orchestrator.process_request(f"Create demo.py with {secret}")
    status = get_brain_v2_status()
    assert result.memory_persisted is False
    assert secret not in repr(status)
    assert "demo.py" not in repr(status)
    assert not (isolated_workspace.root / "demo.py").exists()


def test_developer_prompts_and_approval_bypass_durable_session_history(
    isolated_workspace, monkeypatch, capsys
):
    remember_user = Mock()
    remember_assistant = Mock()
    monkeypatch.setattr(brain, "remember_user_message", remember_user)
    monkeypatch.setattr(brain, "remember_assistant_message", remember_assistant)

    secret = "do-not-log-this-content"
    brain.think(f"Create demo.py with {secret}")
    brain.think("cancel")

    remember_user.assert_not_called()
    remember_assistant.assert_not_called()
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert "[BRAIN] Heard developer request" in captured.out


@pytest.mark.parametrize(
    "response",
    [
        "yes",
        "yes approve",
        "sure",
        "okay",
        "go ahead and explain it",
        "approve all",
        "approve!",
        "yes, but change the file first",
        "run something else",
        "proceed with the next task",
    ],
)
def test_non_exact_affirmation_is_not_approval(
    isolated_workspace, monkeypatch, response
):
    orchestrator.process_request("Create demo.py with hello")
    route = Mock(return_value="ordinary yes")
    monkeypatch.setattr(orchestrator, "route", route)
    result = orchestrator.process_request(response)
    assert result.developer_status == "rejected"
    assert result.developer_error_code == "approval_not_recognized"
    assert "nothing was executed" in result.response
    route.assert_not_called()
    assert not (isolated_workspace.root / "demo.py").exists()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


@pytest.mark.parametrize(
    "approval",
    ["approve", "APPROVE", "yes, approve", "proceed", "execute it", "run it"],
)
def test_exact_approval_phrases_are_supported(
    isolated_workspace, monkeypatch, approval
):
    execute = Mock(return_value=success_result("developer.write_file", "done"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    orchestrator.process_request("Create demo.py with hello")
    result = orchestrator.process_request(approval)
    assert result.developer_status == "executed"
    assert execute.call_count == 1


@pytest.mark.parametrize(
    "cancellation",
    ["cancel", "never mind", "don't run it", "stop"],
)
def test_exact_cancellation_phrases_clear_pending(
    isolated_workspace, cancellation
):
    orchestrator.process_request("Create demo.py with hello")
    cancelled = orchestrator.process_request(cancellation)
    assert cancelled.developer_status == "cancelled"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_text_api_continues_one_pending_action(isolated_workspace, monkeypatch):
    monkeypatch.setattr(brain, "remember_user_message", lambda message: None)
    monkeypatch.setattr(brain, "remember_assistant_message", lambda message: None)
    client = api.app.test_client()

    proposed = client.post("/text", json={"command": "Create demo.py with hello"})
    assert proposed.status_code == 200
    assert "Confirmation required" in proposed.get_json()["response"]
    assert not (isolated_workspace.root / "demo.py").exists()

    approved = client.post("/text", json={"command": "approve"})
    assert approved.status_code == 200
    assert approved.get_json()["response"] == "File written successfully"
    assert (isolated_workspace.root / "demo.py").read_text() == "hello"
