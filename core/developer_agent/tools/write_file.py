"""Controlled bounded UTF-8 file creation and replacement."""

from __future__ import annotations

from core.developer_agent.mutation import (
    MAX_FILE_BYTES,
    MutationError,
    atomic_write_text,
    encode_text,
    prepare_mutation_target,
    read_existing_text,
)
from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.write_file"


def write_file(
    path: str,
    content: str,
    overwrite: bool = False,
    create_parent_dirs: bool = False,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    active_workspace = workspace or Workspace()
    if not isinstance(overwrite, bool) or not isinstance(create_parent_dirs, bool):
        return failure_result(TOOL_ID, "invalid_arguments", "Write flags must be booleans")
    try:
        encoded = encode_text(content, max_bytes=MAX_FILE_BYTES)
        target = prepare_mutation_target(
            active_workspace,
            path,
            create_parent_dirs=create_parent_dirs,
        )
        if target.existed and not overwrite:
            raise MutationError("target_exists", "Target already exists")

        snapshot = None
        if target.existed:
            _, _, snapshot = read_existing_text(active_workspace, target)
        atomic_write_text(
            active_workspace,
            target,
            encoded,
            replace_existing=overwrite,
            expected_snapshot=snapshot,
        )
    except MutationError as exc:
        return failure_result(TOOL_ID, exc.code, exc.message)
    except Exception:
        return failure_result(TOOL_ID, "internal_error", "File write failed safely")

    return success_result(
        TOOL_ID,
        "File written successfully",
        metadata={
            "path": target.relative_path,
            "created": not target.existed,
            "overwritten": target.existed,
            "bytes_written": len(encoded),
        },
    )
