"""Fixed registry for the controlled Developer Agent tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    description: str
    read_only: bool
    mutating: bool
    requires_confirmation: bool
    enabled: bool
    executable: bool


_TOOLS = (
    ToolDefinition(
        "developer.list_files", "List bounded workspace directory entries",
        True, False, False, True, True,
    ),
    ToolDefinition(
        "developer.read_file", "Read bounded UTF-8 text from the workspace",
        True, False, False, True, True,
    ),
    ToolDefinition(
        "developer.git_status", "Inspect workspace Git status",
        True, False, False, True, True,
    ),
    ToolDefinition(
        "developer.write_file", "Write bounded workspace text files",
        False, True, True, True, False,
    ),
    ToolDefinition(
        "developer.patch_file", "Patch exact text in workspace files",
        False, True, True, True, False,
    ),
    ToolDefinition(
        "developer.run_command", "Run an allowlisted workspace command",
        False, True, True, True, False,
    ),
)

_TOOLS_BY_ID = {tool.tool_id: tool for tool in _TOOLS}


def list_tools() -> tuple[ToolDefinition, ...]:
    return _TOOLS


def get_tool(tool_id: str) -> ToolDefinition | None:
    if not isinstance(tool_id, str):
        return None
    return _TOOLS_BY_ID.get(tool_id)
