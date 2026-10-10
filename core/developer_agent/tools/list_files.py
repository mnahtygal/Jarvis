"""Bounded, deterministic workspace directory listing."""

from __future__ import annotations

import heapq
import os
from pathlib import Path

from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace, WorkspacePathError


TOOL_ID = "developer.list_files"
DEFAULT_MAX_ENTRIES = 200
MAX_ENTRIES = 1_000
MAX_SCANNED_ENTRIES_PER_DIRECTORY = 10_000
_NOISY_DIRECTORY_NAMES = frozenset({
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
})


class _DirectoryScanLimitError(RuntimeError):
    pass


def _display_path(workspace: Workspace, path: Path) -> str:
    relative = path.relative_to(workspace.root).as_posix()
    return f"{relative}/" if path.is_dir() else relative


def _safe_children(
    workspace: Workspace,
    directory: Path,
    *,
    include_noisy: bool,
) -> list[Path]:
    children: list[Path] = []
    with os.scandir(directory) as directory_entries:
        for scanned_count, entry in enumerate(directory_entries, start=1):
            if scanned_count > MAX_SCANNED_ENTRIES_PER_DIRECTORY:
                raise _DirectoryScanLimitError
            child = Path(entry.path)
            if not include_noisy and child.name in _NOISY_DIRECTORY_NAMES:
                continue
            try:
                workspace.resolve_path(str(child))
            except WorkspacePathError:
                continue
            children.append(child)
    return sorted(children, key=lambda item: _display_path(workspace, item))


def _recursive_entries(
    workspace: Workspace,
    directory: Path,
    *,
    include_noisy: bool,
):
    pending = [
        (_display_path(workspace, child), child)
        for child in _safe_children(
            workspace,
            directory,
            include_noisy=include_noisy,
        )
    ]
    heapq.heapify(pending)
    while pending:
        _, child = heapq.heappop(pending)
        yield child
        if child.is_dir() and not child.is_symlink():
            for descendant in _safe_children(
                workspace,
                child,
                include_noisy=include_noisy,
            ):
                heapq.heappush(
                    pending,
                    (_display_path(workspace, descendant), descendant),
                )


def list_files(
    path: str = ".",
    recursive: bool = False,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    active_workspace = workspace or Workspace()
    if not isinstance(recursive, bool):
        return failure_result(TOOL_ID, "invalid_arguments", "recursive must be a boolean")
    if (
        not isinstance(max_entries, int)
        or isinstance(max_entries, bool)
        or not 1 <= max_entries <= MAX_ENTRIES
    ):
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            f"max_entries must be an integer from 1 to {MAX_ENTRIES}",
        )

    try:
        directory = active_workspace.resolve_path(path)
    except WorkspacePathError as exc:
        return failure_result(TOOL_ID, exc.code, "Directory is not available in the workspace")
    if not directory.is_dir():
        return failure_result(TOOL_ID, "not_a_directory", "Path is not a directory")

    relative_directory = directory.relative_to(active_workspace.root)
    include_noisy = bool(
        relative_directory.parts
        and relative_directory.parts[0] in _NOISY_DIRECTORY_NAMES
    )
    try:
        entries = (
            _recursive_entries(
                active_workspace,
                directory,
                include_noisy=include_noisy,
            )
            if recursive
            else iter(_safe_children(
                active_workspace,
                directory,
                include_noisy=include_noisy,
            ))
        )
        collected: list[Path] = []
        for entry in entries:
            collected.append(entry)
            if len(collected) > max_entries:
                break
    except _DirectoryScanLimitError:
        return failure_result(
            TOOL_ID,
            "directory_too_large",
            "Directory exceeds the safe scan limit",
        )
    except OSError:
        return failure_result(TOOL_ID, "read_failed", "Directory could not be read")

    truncated = len(collected) > max_entries
    bounded = collected[:max_entries]
    output = "\n".join(_display_path(active_workspace, entry) for entry in bounded)
    return success_result(
        TOOL_ID,
        output,
        metadata={
            "path": active_workspace.relative_path(directory),
            "recursive": recursive,
            "entry_count": len(bounded),
            "max_entries": max_entries,
            "truncated": truncated,
        },
    )
