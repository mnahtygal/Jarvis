"""Fixed dispatcher for registered Developer Agent tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Callable

from core.developer_agent.registry import get_tool
from core.developer_agent.tool_models import ToolResult, failure_result
from core.developer_agent.tools import (
    git_status,
    list_files,
    patch_file,
    read_file,
    run_command,
    write_file,
)
from core.developer_agent.workspace import Workspace


_TOOL_ARGUMENTS = {
    "developer.list_files": frozenset({"path", "recursive", "max_entries"}),
    "developer.read_file": frozenset({"path", "start_line", "end_line", "max_bytes"}),
    "developer.git_status": frozenset(),
    "developer.write_file": frozenset({
        "path", "content", "overwrite", "create_parent_dirs",
    }),
    "developer.patch_file": frozenset({
        "path", "old_text", "new_text", "expected_matches",
    }),
    "developer.run_command": frozenset({
        "argv", "timeout_seconds", "max_output_bytes",
    }),
}


def _run_list_files(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return list_files(workspace=workspace, **arguments)


def _run_read_file(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return read_file(workspace=workspace, **arguments)


def _run_git_status(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return git_status(workspace=workspace, **arguments)


def _run_write_file(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return write_file(workspace=workspace, **arguments)


def _run_patch_file(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return patch_file(workspace=workspace, **arguments)


def _run_command(arguments: dict[str, object], workspace: Workspace) -> ToolResult:
    return run_command(workspace=workspace, **arguments)


_DISPATCH: dict[str, Callable[[dict[str, object], Workspace], ToolResult]] = {
    "developer.list_files": _run_list_files,
    "developer.read_file": _run_read_file,
    "developer.git_status": _run_git_status,
    "developer.write_file": _run_write_file,
    "developer.patch_file": _run_patch_file,
    "developer.run_command": _run_command,
}


def execute_tool(
    tool_id: str,
    arguments: Mapping[str, object],
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    """Execute one known read-only tool with explicitly bounded arguments."""

    definition = get_tool(tool_id)
    if definition is None or not definition.enabled or tool_id not in _DISPATCH:
        return failure_result(
            "developer.executor",
            "unknown_tool",
            "Tool is not registered or enabled",
        )
    if not isinstance(arguments, Mapping) or any(
        not isinstance(key, str) for key in arguments
    ):
        return failure_result(tool_id, "invalid_arguments", "Arguments must be a mapping")

    copied_arguments = dict(arguments)
    if set(copied_arguments) - _TOOL_ARGUMENTS[tool_id]:
        return failure_result(tool_id, "invalid_arguments", "Arguments are not supported")
    required_arguments = {
        "developer.read_file": frozenset({"path"}),
        "developer.write_file": frozenset({"path", "content"}),
        "developer.patch_file": frozenset({"path", "old_text", "new_text"}),
        "developer.run_command": frozenset({"argv"}),
    }
    if not required_arguments.get(tool_id, frozenset()).issubset(copied_arguments):
        return failure_result(tool_id, "invalid_arguments", "Required arguments are missing")

    try:
        return _DISPATCH[tool_id](copied_arguments, workspace or Workspace())
    except (TypeError, ValueError):
        return failure_result(tool_id, "invalid_arguments", "Arguments are invalid")
    except Exception:
        return failure_result(tool_id, "internal_error", "Tool execution failed safely")
