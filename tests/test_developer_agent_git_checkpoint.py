from pathlib import Path
import subprocess

import pytest

from core.developer_agent import VerificationEvidence, Workspace, execute_tool, get_tool
from core.developer_agent.tools.git_commit import git_commit
from core.developer_agent.tools.git_stage import git_stage
from core.developer_agent.tools.run_command import run_command
from core.developer_agent.tool_models import ToolResult


PROTECTED_CHECKPOINT_FILES = (
    "testbrain.py",
    "audio_pipeline_tester.py",
    "audio_pipeline_tester_jarvis.py",
    "audio_pipeline_tester_jarvis_v2.py",
)


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
    )


def _repository(tmp_path: Path) -> tuple[Path, Workspace]:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Jarvis Test")
    _git(root, "config", "user.email", "jarvis@example.invalid")
    return root, Workspace(root)


def _baseline_commit(root: Path, filename: str = "tracked.txt") -> Path:
    target = root / filename
    target.write_text("original\n", encoding="utf-8")
    _git(root, "add", "--", filename)
    _git(root, "commit", "-q", "-m", "Initial fixture")
    return target


def _evidence(
    *,
    successful: bool = True,
    command_family: str = "pytest",
    exit_code: int = 0,
) -> VerificationEvidence:
    result = ToolResult(
        successful,
        "developer.run_command",
        "diagnostic output must not survive evidence reduction",
        error_code=None if successful else "command_failed",
        metadata={
            "command_family": command_family,
            "exit_code": exit_code,
            "timed_out": False,
        },
    )
    return VerificationEvidence.from_tool_result(result)


def _cached_names(root: Path) -> tuple[str, ...]:
    output = _git(root, "diff", "--cached", "--name-only").stdout
    return tuple(line for line in output.splitlines() if line)


def test_stage_without_approval_performs_no_git_mutation(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "new.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = git_stage(["new.py"], approved=False, workspace=workspace)

    assert result.success is False
    assert result.error_code == "approval_required"
    assert _cached_names(root) == ()


def test_stage_explicit_modified_file(tmp_path):
    root, workspace = _repository(tmp_path)
    target = _baseline_commit(root)
    target.write_text("modified\n", encoding="utf-8")

    result = git_stage(["tracked.txt"], approved=True, workspace=workspace)

    assert result.success is True
    assert result.metadata["staged_file_count"] == 1
    assert _cached_names(root) == ("tracked.txt",)


def test_stage_explicit_new_file(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "new.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = git_stage(["new.py"], approved=True, workspace=workspace)

    assert result.success is True
    assert _cached_names(root) == ("new.py",)


@pytest.mark.parametrize(
    "path",
    [".", "-A", "--all", "*.py", "file?.py", ":(glob)*", "!excluded.py"],
)
def test_stage_rejects_shortcuts_options_and_pathspecs(tmp_path, path):
    root, workspace = _repository(tmp_path)

    result = git_stage([path], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "pathspec_not_allowed"
    assert _cached_names(root) == ()


@pytest.mark.parametrize("kind", ["traversal", "absolute"])
def test_stage_rejects_outside_paths(tmp_path, kind):
    root, workspace = _repository(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    path = "../outside.py" if kind == "traversal" else str(outside)

    result = git_stage([path], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "path_not_relative"
    assert _cached_names(root) == ()


@pytest.mark.parametrize("filename", PROTECTED_CHECKPOINT_FILES)
def test_stage_rejects_protected_personal_files(tmp_path, filename):
    root, workspace = _repository(tmp_path)
    (root / filename).write_text("protected\n", encoding="utf-8")

    result = git_stage([filename], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "protected_path"
    assert _cached_names(root) == ()


@pytest.mark.parametrize(
    "filename",
    [".env", ".env.local", "private.pem", "private.key", "credentials.json", "secrets.txt"],
)
def test_stage_rejects_sensitive_files(tmp_path, filename):
    root, workspace = _repository(tmp_path)
    (root / filename).write_text("private\n", encoding="utf-8")

    result = git_stage([filename], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "protected_path"


def test_stage_rejects_tracked_deletion(tmp_path):
    root, workspace = _repository(tmp_path)
    target = _baseline_commit(root)
    target.unlink()

    result = git_stage(["tracked.txt"], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "path_not_found"
    assert _cached_names(root) == ()


def test_stage_rejects_symlink_path(tmp_path):
    root, workspace = _repository(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    (root / "linked.py").symlink_to(outside)

    result = git_stage(["linked.py"], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "outside_workspace"


def test_stage_rejects_preexisting_staged_file_outside_approved_scope(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "one.py").write_text("ONE = 1\n", encoding="utf-8")
    (root / "two.py").write_text("TWO = 2\n", encoding="utf-8")
    _git(root, "add", "--", "one.py")

    result = git_stage(["two.py"], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "staged_scope_mismatch"
    assert _cached_names(root) == ("one.py",)


def test_stage_rejects_external_clean_filter_without_executing_it(tmp_path):
    root, workspace = _repository(tmp_path)
    marker = root / "filter-ran"
    (root / ".gitattributes").write_text("filtered.txt filter=unsafe\n", encoding="utf-8")
    (root / "filtered.txt").write_text("content\n", encoding="utf-8")
    _git(root, "config", "filter.unsafe.clean", f"touch {marker}")

    result = git_stage(["filtered.txt"], approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "external_filter_not_allowed"
    assert not marker.exists()


def test_commit_without_approval_creates_nothing(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "safe.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "--", "safe.py")

    result = git_commit("Safe checkpoint", _evidence(), approved=False, workspace=workspace)

    assert result.success is False
    assert result.error_code == "approval_required"
    assert _git(root, "rev-parse", "--verify", "HEAD", check=False).returncode != 0


@pytest.mark.parametrize("message", ["", "   ", "bad\nmessage", "bad\x00message", "bad\tmessage"])
def test_commit_rejects_invalid_message(tmp_path, message):
    _, workspace = _repository(tmp_path)

    result = git_commit(message, _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "invalid_message"


def test_commit_rejects_no_staged_changes(tmp_path):
    _, workspace = _repository(tmp_path)

    result = git_commit("Safe checkpoint", _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "no_staged_changes"


@pytest.mark.parametrize(
    "evidence",
    [True, None, _evidence(successful=False, exit_code=1)],
)
def test_commit_requires_structured_successful_verification(tmp_path, evidence):
    root, workspace = _repository(tmp_path)
    (root / "safe.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "--", "safe.py")

    result = git_commit("Safe checkpoint", evidence, approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "verification_required"


def test_nonverification_run_command_cannot_become_successful_evidence():
    result = ToolResult(
        True,
        "developer.run_command",
        "",
        metadata={"command_family": "pwd", "exit_code": 0, "timed_out": False},
    )

    evidence = VerificationEvidence.from_tool_result(result)

    assert evidence.successful is False


def test_verification_evidence_cannot_be_caller_instantiated():
    with pytest.raises(TypeError):
        VerificationEvidence(True, "pytest", 0, "developer.run_command")


def test_commit_refuses_manually_staged_protected_file(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "testbrain.py").write_text("protected\n", encoding="utf-8")
    _git(root, "add", "--", "testbrain.py")

    result = git_commit("Unsafe checkpoint", _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "protected_staged_path"
    assert _git(root, "rev-parse", "--verify", "HEAD", check=False).returncode != 0


def test_commit_refuses_manually_staged_deletion(tmp_path):
    root, workspace = _repository(tmp_path)
    target = _baseline_commit(root)
    target.unlink()
    _git(root, "add", "--", "tracked.txt")
    original_head = _git(root, "rev-parse", "HEAD").stdout.strip()

    result = git_commit("Unsafe deletion", _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "unsupported_staged_status"
    assert _git(root, "rev-parse", "HEAD").stdout.strip() == original_head


def test_commit_refuses_manually_staged_symlink(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "target.txt").write_text("target\n", encoding="utf-8")
    (root / "linked.txt").symlink_to("target.txt")
    _git(root, "add", "--", "linked.txt")

    result = git_commit("Unsafe symlink", _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "unsupported_staged_mode"


def test_commit_refuses_cached_diff_check_failure(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "bad.py").write_text("VALUE = 1   \n", encoding="utf-8")
    _git(root, "add", "--", "bad.py")

    result = git_commit("Whitespace failure", _evidence(), approved=True, workspace=workspace)

    assert result.success is False
    assert result.error_code == "cached_diff_check_failed"


def test_valid_verified_local_checkpoint_returns_sha_and_disables_hooks(tmp_path):
    root, workspace = _repository(tmp_path)
    source = root / "safe.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    unrelated = root / "unrelated.txt"
    unrelated.write_text("not approved\n", encoding="utf-8")
    hooks = root / ".git" / "hooks"
    hook_marker = root / "hook-ran"
    for name in ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"):
        hook = hooks / name
        hook.write_text(f"#!/bin/sh\ntouch '{hook_marker}'\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

    verification = run_command(
        ["python", "-m", "py_compile", "safe.py"],
        workspace=workspace,
    )
    evidence = VerificationEvidence.from_tool_result(verification)
    staged = git_stage(["safe.py"], approved=True, workspace=workspace)
    committed = git_commit(
        "Add safe fixture",
        evidence,
        approved=True,
        workspace=workspace,
    )

    assert verification.success is evidence.successful is staged.success is True
    assert committed.success is True
    assert committed.metadata["commit_created"] is True
    assert len(committed.metadata["commit_sha"]) == 40
    assert committed.metadata["commit_sha"] == _git(root, "rev-parse", "HEAD").stdout.strip()
    assert committed.metadata["branch"] in {"main", "master"}
    assert committed.metadata["staged_file_count"] == 1
    assert _git(root, "show", "--format=", "--name-only", "HEAD").stdout.strip() == "safe.py"
    assert unrelated.exists()
    assert not hook_marker.exists()
    assert _cached_names(root) == ()


def test_executor_and_registries_keep_git_mutation_manual(tmp_path):
    root, workspace = _repository(tmp_path)
    (root / "safe.py").write_text("VALUE = 1\n", encoding="utf-8")

    staged = execute_tool(
        "developer.git_stage",
        {"paths": ["safe.py"], "approved": True},
        workspace=workspace,
    )
    rejected_extra = execute_tool(
        "developer.git_commit",
        {
            "message": "Safe checkpoint",
            "verification_evidence": _evidence(),
            "approved": True,
            "amend": True,
        },
        workspace=workspace,
    )

    assert staged.success is True
    assert rejected_extra.success is False
    assert rejected_extra.error_code == "invalid_arguments"
    for tool_id in ("developer.git_stage", "developer.git_commit"):
        definition = get_tool(tool_id)
        assert definition.enabled is True
        assert definition.read_only is False
        assert definition.mutating is True
        assert definition.requires_confirmation is True
        assert definition.executable is False


def test_git_checkpoint_source_has_no_dangerous_git_or_autonomy_paths():
    repository_root = Path(__file__).parents[1]
    implementation = "\n".join(
        (repository_root / path).read_text(encoding="utf-8")
        for path in (
            "core/developer_agent/git_safety.py",
            "core/developer_agent/tools/git_stage.py",
            "core/developer_agent/tools/git_commit.py",
        )
    )
    autonomous_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repository_root / "core").glob("*.py")
        if path.name != "capability_registry.py"
    )

    assert "shell=True" not in implementation.replace(" ", "")
    for operation in (
        "push",
        "pull",
        "fetch",
        "merge",
        "rebase",
        "cherry-pick",
        "reset",
        "clean",
        "checkout",
        "restore",
        "switch",
        "tag",
        "stash",
        "rm",
        "mv",
        "amend",
    ):
        assert f'"{operation}"' not in implementation
    assert '("branch",' not in implementation
    assert "developer.git_stage" not in autonomous_source
    assert "developer.git_commit" not in autonomous_source
    assert "ask_local_llm" not in implementation
    assert "llm_skill" not in implementation
