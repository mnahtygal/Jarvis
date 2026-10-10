"""Explicit-path Git staging for controlled local checkpoints."""

from __future__ import annotations

from pathlib import Path
import unicodedata

from core.developer_agent.git_safety import (
    inspect_staged,
    stage_paths,
    validate_no_external_clean_filters,
    validate_repository,
)
from core.developer_agent.policy import git_protection_code
from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace, WorkspacePathError


TOOL_ID = "developer.git_stage"
MAX_STAGE_PATHS = 100
MAX_PATH_BYTES = 4096
MAX_TOTAL_PATH_BYTES = 32 * 1024
_PATHSPEC_CHARACTERS = frozenset("*?[")


def _validate_paths(paths: object, workspace: Workspace) -> tuple[str, ...] | ToolResult:
    if not isinstance(paths, (list, tuple)) or not paths:
        return failure_result(TOOL_ID, "invalid_paths", "Paths must be a non-empty list")
    if len(paths) > MAX_STAGE_PATHS:
        return failure_result(TOOL_ID, "too_many_paths", "Too many paths were requested")

    validated: list[str] = []
    total_bytes = 0
    for path in paths:
        if not isinstance(path, str) or not path or "\x00" in path:
            return failure_result(TOOL_ID, "invalid_path", "A stage path is invalid")
        if any(unicodedata.category(character).startswith("C") for character in path):
            return failure_result(TOOL_ID, "invalid_path", "Control characters are not allowed")
        try:
            path_bytes = len(path.encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            return failure_result(TOOL_ID, "invalid_path", "A stage path is invalid")
        total_bytes += path_bytes
        if path_bytes > MAX_PATH_BYTES or total_bytes > MAX_TOTAL_PATH_BYTES:
            return failure_result(TOOL_ID, "path_too_long", "Stage paths exceed safe bounds")
        if path == "." or path.startswith(('-', ':', '!')):
            return failure_result(TOOL_ID, "pathspec_not_allowed", "Git pathspec syntax is not allowed")
        if any(character in path for character in _PATHSPEC_CHARACTERS):
            return failure_result(TOOL_ID, "pathspec_not_allowed", "Git pathspec syntax is not allowed")

        requested = Path(path)
        if (
            requested.is_absolute()
            or ".." in requested.parts
            or requested.as_posix() != path
        ):
            return failure_result(TOOL_ID, "path_not_relative", "Paths must be canonical and repo-relative")
        if git_protection_code(requested) is not None:
            return failure_result(TOOL_ID, "protected_path", "A protected path cannot be staged")
        try:
            resolved = workspace.resolve_path(path)
        except WorkspacePathError as exc:
            return failure_result(TOOL_ID, exc.code, "A stage path is unavailable")
        expected = workspace.root / requested
        if resolved != expected:
            return failure_result(TOOL_ID, "symlink_not_allowed", "Symlinked stage paths are not allowed")
        if not resolved.is_file():
            return failure_result(TOOL_ID, "not_a_file", "Only explicit files can be staged")
        relative = Path(resolved.relative_to(workspace.root).as_posix())
        if git_protection_code(requested, relative) is not None:
            return failure_result(TOOL_ID, "protected_path", "A protected path cannot be staged")
        validated.append(path)

    if len(validated) != len(set(validated)):
        return failure_result(TOOL_ID, "duplicate_path", "Duplicate stage paths are not allowed")
    return tuple(validated)


def git_stage(
    paths: object,
    approved: object = False,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    """Stage only explicitly approved additions or modifications."""

    if not isinstance(approved, bool):
        return failure_result(TOOL_ID, "invalid_approval", "Approval must be a boolean")
    if not approved:
        return failure_result(TOOL_ID, "approval_required", "Explicit approval is required")

    active_workspace = workspace or Workspace()
    validated = _validate_paths(paths, active_workspace)
    if isinstance(validated, ToolResult):
        return validated
    repository_error = validate_repository(active_workspace)
    if repository_error is not None:
        return failure_result(TOOL_ID, repository_error, "Workspace is not an approved Git repository")
    filter_error = validate_no_external_clean_filters(active_workspace)
    if filter_error is not None:
        return failure_result(TOOL_ID, filter_error, "Repository Git filters are not allowed")

    before = inspect_staged(active_workspace)
    if not before.valid:
        return failure_result(TOOL_ID, before.status, "Existing staged changes are unsafe")
    approved_paths = set(validated)
    if not set(before.paths).issubset(approved_paths):
        return failure_result(TOOL_ID, "staged_scope_mismatch", "Other files are already staged")

    revalidated = _validate_paths(validated, active_workspace)
    if isinstance(revalidated, ToolResult) or revalidated != validated:
        return failure_result(TOOL_ID, "path_changed", "A stage path changed during validation")
    stage_error = stage_paths(active_workspace, validated)
    if stage_error is not None:
        return failure_result(TOOL_ID, stage_error, "Explicit Git staging failed safely")

    after = inspect_staged(active_workspace)
    if not after.valid:
        return failure_result(TOOL_ID, after.status, "Staged changes failed safety inspection")
    if not set(after.paths).issubset(approved_paths):
        return failure_result(TOOL_ID, "staged_scope_mismatch", "Unexpected files are staged")
    if after.file_count == 0:
        return failure_result(TOOL_ID, "no_staged_changes", "No file changes were staged")
    return success_result(
        TOOL_ID,
        f"Staged {after.file_count} explicit file(s)",
        metadata={"staged_file_count": after.file_count},
    )
