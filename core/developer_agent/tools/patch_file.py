"""Controlled exact-text replacement for bounded UTF-8 files."""

from __future__ import annotations

from core.developer_agent.mutation import (
    MAX_FILE_BYTES,
    MAX_PATCH_PAYLOAD_BYTES,
    MutationError,
    atomic_write_text,
    encode_text,
    prepare_mutation_target,
    read_existing_text,
)
from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.patch_file"
MAX_EXPECTED_MATCHES = 10_000


def patch_file(
    path: str,
    old_text: str,
    new_text: str,
    expected_matches: int = 1,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    active_workspace = workspace or Workspace()
    if (
        not isinstance(expected_matches, int)
        or isinstance(expected_matches, bool)
        or not 1 <= expected_matches <= MAX_EXPECTED_MATCHES
    ):
        return failure_result(
            TOOL_ID,
            "invalid_arguments",
            f"expected_matches must be an integer from 1 to {MAX_EXPECTED_MATCHES}",
        )

    try:
        encode_text(old_text, max_bytes=MAX_PATCH_PAYLOAD_BYTES, allow_empty=False)
        encode_text(new_text, max_bytes=MAX_PATCH_PAYLOAD_BYTES)
        target = prepare_mutation_target(
            active_workspace,
            path,
            require_exists=True,
        )
        text, before, snapshot = read_existing_text(active_workspace, target)
        actual_matches = text.count(old_text)
        if actual_matches != expected_matches:
            return ToolResult(
                False,
                TOOL_ID,
                "Exact match count did not meet the expectation",
                error_code="match_mismatch",
                metadata={
                    "path": target.relative_path,
                    "expected_matches": expected_matches,
                    "actual_matches": actual_matches,
                },
            )
        updated_text = text.replace(old_text, new_text)
        updated = encode_text(updated_text, max_bytes=MAX_FILE_BYTES)
        atomic_write_text(
            active_workspace,
            target,
            updated,
            replace_existing=True,
            expected_snapshot=snapshot,
        )
    except MutationError as exc:
        return failure_result(TOOL_ID, exc.code, exc.message)
    except Exception:
        return failure_result(TOOL_ID, "internal_error", "File patch failed safely")

    return success_result(
        TOOL_ID,
        "File patched successfully",
        metadata={
            "path": target.relative_path,
            "matches_replaced": actual_matches,
            "bytes_before": len(before),
            "bytes_after": len(updated),
        },
    )
