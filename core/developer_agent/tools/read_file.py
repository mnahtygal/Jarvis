"""Bounded UTF-8 text reads within the approved workspace."""

from __future__ import annotations

import codecs
from pathlib import Path

from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace, WorkspacePathError


TOOL_ID = "developer.read_file"
DEFAULT_MAX_BYTES = 64 * 1024
MAX_BYTES = 1024 * 1024
MAX_LINE_RANGE = 2_000


def _is_sensitive(path: Path) -> bool:
    name = path.name.casefold()
    return (
        name == ".env"
        or name.startswith(".env.")
        or path.suffix.casefold() in {".pem", ".key"}
        or name.startswith("credentials")
        or name.startswith("secrets")
    )


def _valid_line_number(value: int | None) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and value >= 1
    )


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    active_workspace = workspace or Workspace()
    if not _valid_line_number(start_line) or not _valid_line_number(end_line):
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            "Line numbers must be positive integers",
        )
    first_line = start_line or 1
    if end_line is not None and end_line < first_line:
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            "end_line must not be before start_line",
        )
    if end_line is not None and end_line - first_line + 1 > MAX_LINE_RANGE:
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            f"A line range may contain at most {MAX_LINE_RANGE} lines",
        )
    if (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or not 1 <= max_bytes <= MAX_BYTES
    ):
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            f"max_bytes must be an integer from 1 to {MAX_BYTES}",
        )

    try:
        requested_name = Path(path) if isinstance(path, str) else Path("")
        resolved = active_workspace.resolve_path(path)
    except WorkspacePathError as exc:
        return failure_result(TOOL_ID, exc.code, "File is not available in the workspace")
    if resolved.is_dir():
        return failure_result(TOOL_ID, "not_a_file", "Path is a directory")
    if not resolved.is_file():
        return failure_result(TOOL_ID, "not_a_file", "Path is not a regular file")
    if _is_sensitive(requested_name) or _is_sensitive(resolved):
        return failure_result(TOOL_ID, "sensitive_file", "Sensitive files cannot be read")

    try:
        file_size = resolved.stat().st_size
        with resolved.open("rb") as file_handle:
            data = file_handle.read(max_bytes)
    except OSError:
        return failure_result(TOOL_ID, "read_failed", "File could not be read")

    if b"\x00" in data:
        return failure_result(TOOL_ID, "binary_file", "Binary files cannot be read")

    truncated_by_bytes = file_size > len(data)
    try:
        if truncated_by_bytes:
            decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
            text = decoder.decode(data, final=False)
        else:
            text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return failure_result(TOOL_ID, "binary_file", "File is not valid UTF-8 text")

    lines = text.splitlines()
    requested_end = end_line or len(lines)
    selected = lines[first_line - 1:requested_end]
    numbered = "\n".join(
        f"{line_number}: {line}"
        for line_number, line in enumerate(selected, start=first_line)
    )
    return success_result(
        TOOL_ID,
        numbered,
        metadata={
            "path": active_workspace.relative_path(resolved),
            "start_line": first_line,
            "end_line": first_line + len(selected) - 1 if selected else None,
            "bytes_read": len(data),
            "file_size": file_size,
            "truncated": truncated_by_bytes or requested_end < len(lines),
        },
    )
