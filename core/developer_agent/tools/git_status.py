"""Fixed read-only Git status inspection for the workspace repository."""

from __future__ import annotations

import os
import subprocess

from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.git_status"
GIT_STATUS_COMMAND = ("git", "status", "--short", "--branch")
GIT_TIMEOUT_SECONDS = 5
MAX_OUTPUT_BYTES = 128 * 1024


def _bounded_output(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return value, False
    return encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore"), True


def git_status(*, workspace: Workspace | None = None) -> ToolResult:
    active_workspace = workspace or Workspace()
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            GIT_STATUS_COMMAND,
            cwd=active_workspace.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return failure_result(TOOL_ID, "timeout", "Git status timed out")
    except (OSError, subprocess.SubprocessError):
        return failure_result(TOOL_ID, "git_unavailable", "Git status could not run")

    if completed.returncode != 0:
        return failure_result(TOOL_ID, "git_error", "Git status failed")

    output, truncated = _bounded_output(completed.stdout.rstrip("\n"))
    lines = output.splitlines()
    branch = lines[0][3:] if lines and lines[0].startswith("## ") else ""
    changed_files: list[str] = []
    untracked_files: list[str] = []
    for line in lines[1:]:
        if len(line) < 4:
            continue
        path = line[3:]
        if line.startswith("?? "):
            untracked_files.append(path)
        else:
            changed_files.append(path)

    return success_result(
        TOOL_ID,
        output,
        metadata={
            "branch": branch,
            "changed_files": tuple(changed_files),
            "untracked_files": tuple(untracked_files),
            "truncated": truncated,
        },
    )
