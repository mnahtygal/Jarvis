from dataclasses import FrozenInstanceError
import importlib
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from core.developer_agent import Workspace, execute_tool
from core.developer_agent.registry import list_tools
from core.developer_agent.tools.git_status import GIT_STATUS_COMMAND, git_status
from core.developer_agent.tools.list_files import list_files
from core.developer_agent.tools.read_file import read_file


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_list_files_succeeds_inside_workspace(tmp_path):
    (tmp_path / "README.md").write_text("Jarvis\n", encoding="utf-8")

    result = list_files(workspace=_workspace(tmp_path))

    assert result.success is True
    assert result.output == "README.md"
    assert result.metadata["path"] == "."


def test_recursive_list_is_bounded_sorted_and_ignores_noise(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")

    result = list_files(recursive=True, max_entries=3, workspace=_workspace(tmp_path))

    lines = result.output.splitlines()
    assert result.success is True
    assert lines == sorted(lines)
    assert len(lines) == 3
    assert result.metadata["truncated"] is True
    assert all("node_modules" not in line for line in lines)


def test_read_text_file_and_line_range(tmp_path):
    (tmp_path / "notes.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    workspace = _workspace(tmp_path)

    whole = read_file("notes.txt", workspace=workspace)
    ranged = read_file("notes.txt", start_line=2, end_line=2, workspace=workspace)

    assert whole.success is True
    assert whole.output == "1: one\n2: two\n3: three"
    assert ranged.success is True
    assert ranged.output == "2: two"


def test_read_directory_fails_safely(tmp_path):
    result = read_file(".", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "not_a_file"


def test_binary_file_is_refused(tmp_path):
    (tmp_path / "image.bin").write_bytes(b"jarvis\x00binary")

    result = read_file("image.bin", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "binary_file"


@pytest.mark.parametrize("operation", [list_files, read_file])
def test_parent_traversal_is_rejected(tmp_path, operation):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (tmp_path / "outside.txt").write_text("private", encoding="utf-8")

    result = operation("../outside.txt", workspace=_workspace(workspace_root))

    assert result.success is False
    assert result.error_code == "outside_workspace"


@pytest.mark.parametrize("operation", [list_files, read_file])
def test_absolute_path_outside_workspace_is_rejected(tmp_path, operation):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")

    result = operation(str(outside), workspace=_workspace(workspace_root))

    assert result.success is False
    assert result.error_code == "outside_workspace"


@pytest.mark.parametrize("operation", [list_files, read_file])
def test_symlink_escape_is_rejected(tmp_path, operation):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    (workspace_root / "escape").symlink_to(outside)

    result = operation("escape", workspace=_workspace(workspace_root))

    assert result.success is False
    assert result.error_code == "outside_workspace"


@pytest.mark.parametrize(
    "filename",
    [".env", ".env.local", "server.pem", "private.key", "credentials.json", "secrets.txt"],
)
def test_sensitive_file_policy_refuses_protected_names(tmp_path, filename):
    (tmp_path / filename).write_text("do not expose", encoding="utf-8")

    result = read_file(filename, workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "sensitive_file"


def test_git_status_uses_only_fixed_read_only_command(tmp_path, monkeypatch):
    calls = []
    git_status_module = importlib.import_module(
        "core.developer_agent.tools.git_status"
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(
            command,
            0,
            stdout="## feature/test\n M core/example.py\n?? notes.txt\n",
            stderr="",
        )

    monkeypatch.setattr(git_status_module.subprocess, "run", fake_run)

    result = git_status(workspace=_workspace(tmp_path))

    assert result.success is True
    assert result.metadata["branch"] == "feature/test"
    assert result.metadata["changed_files"] == ("core/example.py",)
    assert result.metadata["untracked_files"] == ("notes.txt",)
    assert len(calls) == 1
    command, options = calls[0]
    assert command == GIT_STATUS_COMMAND == ("git", "status", "--short", "--branch")
    assert options["cwd"] == tmp_path.resolve()
    assert options.get("shell", False) is False
    assert options["timeout"] == 5
    assert options["env"]["GIT_OPTIONAL_LOCKS"] == "0"


def test_invalid_arguments_are_rejected(tmp_path):
    workspace = _workspace(tmp_path)

    unknown = execute_tool("developer.delete_file", {}, workspace=workspace)
    invalid = execute_tool(
        "developer.list_files",
        {"recursive": "yes"},
        workspace=workspace,
    )
    unsupported = execute_tool(
        "developer.git_status",
        {"command": "git reset --hard"},
        workspace=workspace,
    )

    assert unknown.success is False
    assert unknown.error_code == "unknown_tool"
    assert invalid.success is False
    assert invalid.error_code == "invalid_arguments"
    assert unsupported.success is False
    assert unsupported.error_code == "invalid_arguments"


def test_registry_ids_are_unique_and_metadata_matches_phase_boundaries():
    tools = list_tools()
    tool_ids = tuple(tool.tool_id for tool in tools)

    assert tool_ids == (
        "developer.list_files",
        "developer.read_file",
        "developer.git_status",
        "developer.write_file",
        "developer.patch_file",
        "developer.run_command",
        "developer.git_stage",
        "developer.git_commit",
    )
    assert len(tool_ids) == len(set(tool_ids))
    assert all(tool.enabled for tool in tools)
    assert all(tool.read_only for tool in tools[:3])
    assert all(not tool.mutating for tool in tools[:3])
    assert all(not tool.requires_confirmation for tool in tools[:3])
    assert all(tool.executable for tool in tools[:3])
    assert all(not tool.read_only for tool in tools[3:])
    assert all(tool.mutating for tool in tools[3:])
    assert all(tool.requires_confirmation for tool in tools[3:])
    assert all(not tool.executable for tool in tools[3:])
    with pytest.raises(FrozenInstanceError):
        tools[0].enabled = False


def test_developer_agent_exposes_no_shell_or_unrestricted_command_execution():
    package_root = Path(__file__).parents[1] / "core" / "developer_agent"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package_root.rglob("*.py")
    )

    assert "shell=True" not in source.replace(" ", "")
    assert "delete_file" not in source
    assert "git add" not in source
    assert "git commit" not in source
    assert "git push" not in source
    assert "chmod" not in source
    assert "chown" not in source
    assert "eval(" not in source
    assert "exec(" not in source
