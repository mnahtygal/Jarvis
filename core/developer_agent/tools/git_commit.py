"""Verification-gated local Git commit for controlled checkpoints."""

from __future__ import annotations

import unicodedata

from core.developer_agent.git_safety import (
    create_commit,
    current_branch,
    current_commit_sha,
    inspect_staged,
    validate_repository,
)
from core.developer_agent.tool_models import ToolResult, failure_result, success_result
from core.developer_agent.verification import is_successful_verification
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.git_commit"
MAX_COMMIT_MESSAGE_BYTES = 200


def _validated_message(message: object) -> str | None:
    if not isinstance(message, str) or "\x00" in message:
        return None
    normalized = message.strip()
    if not normalized:
        return None
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        return None
    try:
        encoded = normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return None
    return normalized if len(encoded) <= MAX_COMMIT_MESSAGE_BYTES else None


def git_commit(
    message: object,
    verification_evidence: object,
    approved: object = False,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    """Commit the already-staged safe diff after successful verification."""

    if not isinstance(approved, bool):
        return failure_result(TOOL_ID, "invalid_approval", "Approval must be a boolean")
    if not approved:
        return failure_result(TOOL_ID, "approval_required", "Explicit approval is required")
    validated_message = _validated_message(message)
    if validated_message is None:
        return failure_result(TOOL_ID, "invalid_message", "Commit message is invalid")
    if not is_successful_verification(verification_evidence):
        return failure_result(
            TOOL_ID,
            "verification_required",
            "Successful Developer Agent verification evidence is required",
        )

    active_workspace = workspace or Workspace()
    repository_error = validate_repository(active_workspace)
    if repository_error is not None:
        return failure_result(TOOL_ID, repository_error, "Workspace is not an approved Git repository")
    branch, branch_error = current_branch(active_workspace)
    if branch_error is not None or branch is None:
        return failure_result(TOOL_ID, branch_error or "invalid_branch", "A branch is required")

    staged = inspect_staged(active_workspace)
    if not staged.valid:
        return failure_result(TOOL_ID, staged.status, "Staged changes failed safety inspection")
    if staged.file_count == 0:
        return failure_result(TOOL_ID, "no_staged_changes", "No staged changes are available")

    commit_error = create_commit(active_workspace, validated_message)
    if commit_error is not None:
        return failure_result(TOOL_ID, commit_error, "Local Git commit failed safely")
    commit_sha, sha_error = current_commit_sha(active_workspace)
    if sha_error is not None or commit_sha is None:
        return failure_result(TOOL_ID, sha_error or "commit_sha_unavailable", "Commit identity is unavailable")
    return success_result(
        TOOL_ID,
        "Created one local Git commit",
        metadata={
            "branch": branch,
            "commit_created": True,
            "commit_sha": commit_sha,
            "staged_file_count": staged.file_count,
        },
    )
