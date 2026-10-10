"""Bounded execution of pre-approved Developer Agent repair sequences."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from core.developer_agent.executor import execute_tool
from core.developer_agent.mutation import MAX_FILE_BYTES, MAX_PATCH_PAYLOAD_BYTES
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.tools.patch_file import MAX_EXPECTED_MATCHES
from core.developer_agent.workspace import Workspace


VERIFICATION_TOOL_ID = "developer.run_command"
ALLOWED_REPAIR_TOOL_IDS = frozenset({
    "developer.patch_file",
    "developer.write_file",
})
MAX_REPAIR_ATTEMPTS = 3
MAX_VERIFICATION_RUNS = 4

_REPAIR_ARGUMENTS = {
    "developer.patch_file": (
        frozenset({"path", "old_text", "new_text"}),
        frozenset({"path", "old_text", "new_text", "expected_matches"}),
    ),
    "developer.write_file": (
        frozenset({"path", "content"}),
        frozenset({"path", "content", "overwrite", "create_parent_dirs"}),
    ),
}
_VERIFICATION_POLICY_ERRORS = frozenset({
    "argument_file",
    "argument_too_long",
    "arguments_too_large",
    "disallowed_option",
    "executable_not_allowed",
    "git_operation_not_allowed",
    "invalid_argument",
    "invalid_arguments",
    "invalid_argv",
    "invalid_pytest_option",
    "invalid_pytest_target",
    "path_not_allowed",
    "path_required",
    "python_form_not_allowed",
    "python_module_not_allowed",
    "shell_syntax",
    "too_many_arguments",
})
_REPAIR_OPERATION_ERRORS = frozenset({
    "concurrent_modification",
    "create_parent_failed",
    "internal_error",
    "mode_preservation_failed",
    "read_failed",
    "temp_file_failed",
    "write_failed",
})


@dataclass(frozen=True)
class RepairAttempt:
    attempt_number: int
    verification_tool: str
    verification_success: bool
    exit_code: int | None
    patch_applied: bool
    status: str


@dataclass(frozen=True)
class RepairResult:
    success: bool
    status: str
    attempts: tuple[RepairAttempt, ...]
    verification_runs: int
    repairs_attempted: int
    patches_applied: int
    final_exit_code: int | None
    stopped_reason: str


@dataclass(frozen=True)
class _RepairAction:
    tool_id: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


class _RequestError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _encoded_length(value: str) -> int:
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        raise _RequestError("invalid_repair_arguments") from None


def _validate_text(
    value: object,
    *,
    allow_empty: bool,
    maximum_bytes: int,
) -> None:
    if not isinstance(value, str) or (not allow_empty and not value) or "\x00" in value:
        raise _RequestError("invalid_repair_arguments")
    if _encoded_length(value) > maximum_bytes:
        raise _RequestError("invalid_repair_arguments")


def _validate_repair_arguments(tool_id: str, arguments: object) -> dict[str, object]:
    if not isinstance(arguments, Mapping) or any(
        not isinstance(key, str) for key in arguments
    ):
        raise _RequestError("invalid_repair_arguments")
    copied = dict(arguments)
    required, allowed = _REPAIR_ARGUMENTS[tool_id]
    if not required.issubset(copied) or set(copied) - allowed:
        raise _RequestError("invalid_repair_arguments")

    _validate_text(copied["path"], allow_empty=False, maximum_bytes=4096)
    if tool_id == "developer.patch_file":
        _validate_text(
            copied["old_text"],
            allow_empty=False,
            maximum_bytes=MAX_PATCH_PAYLOAD_BYTES,
        )
        _validate_text(
            copied["new_text"],
            allow_empty=True,
            maximum_bytes=MAX_PATCH_PAYLOAD_BYTES,
        )
        expected_matches = copied.get("expected_matches", 1)
        if (
            not isinstance(expected_matches, int)
            or isinstance(expected_matches, bool)
            or not 1 <= expected_matches <= MAX_EXPECTED_MATCHES
        ):
            raise _RequestError("invalid_repair_arguments")
    else:
        _validate_text(
            copied["content"],
            allow_empty=True,
            maximum_bytes=MAX_FILE_BYTES,
        )
        if not isinstance(copied.get("overwrite", False), bool) or not isinstance(
            copied.get("create_parent_dirs", False),
            bool,
        ):
            raise _RequestError("invalid_repair_arguments")
    return copied


def _validate_request(
    verification_argv: object,
    repairs: object,
    approved: object,
    max_attempts: object,
    workspace: object,
) -> tuple[tuple[str, ...], tuple[_RepairAction, ...], bool, int]:
    if not isinstance(approved, bool):
        raise _RequestError("invalid_request")
    if (
        not isinstance(max_attempts, int)
        or isinstance(max_attempts, bool)
        or not 1 <= max_attempts <= MAX_REPAIR_ATTEMPTS
    ):
        raise _RequestError("invalid_attempt_limit")
    if workspace is not None and not isinstance(workspace, Workspace):
        raise _RequestError("invalid_request")
    if (
        not isinstance(verification_argv, (list, tuple))
        or not verification_argv
        or any(not isinstance(item, str) for item in verification_argv)
    ):
        raise _RequestError("invalid_verification")
    if not isinstance(repairs, (list, tuple)):
        raise _RequestError("invalid_repairs")
    if len(repairs) > MAX_REPAIR_ATTEMPTS:
        raise _RequestError("too_many_repairs")

    validated_repairs: list[_RepairAction] = []
    for repair in repairs:
        if not isinstance(repair, Mapping) or set(repair) != {"tool", "arguments"}:
            raise _RequestError("invalid_repair")
        tool_id = repair["tool"]
        if not isinstance(tool_id, str) or tool_id not in ALLOWED_REPAIR_TOOL_IDS:
            raise _RequestError("unknown_repair_tool")
        arguments = _validate_repair_arguments(tool_id, repair["arguments"])
        validated_repairs.append(_RepairAction(tool_id, arguments))

    return (
        tuple(verification_argv),
        tuple(validated_repairs),
        approved,
        max_attempts,
    )


def _repair_fingerprint(repair: _RepairAction) -> str:
    serialized = json.dumps(
        {"arguments": dict(repair.arguments), "tool": repair.tool_id},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _exit_code(result: ToolResult) -> int | None:
    value = result.metadata.get("exit_code")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _verification_status(result: ToolResult) -> str:
    if result.success:
        return "verification_passed"
    if result.error_code == "timeout":
        return "verification_timeout"
    if result.error_code in _VERIFICATION_POLICY_ERRORS:
        return "verification_policy_rejected"
    if result.error_code == "command_failed":
        return "verification_failed"
    return "internal_safe_failure"


def _repair_failure_status(result: ToolResult) -> str:
    if result.error_code in _REPAIR_OPERATION_ERRORS or result.error_code is None:
        return "repair_failed"
    return "repair_rejected"


def _finish(
    status: str,
    attempts: list[RepairAttempt],
    *,
    verification_runs: int,
    repairs_attempted: int,
    patches_applied: int,
    final_exit_code: int | None,
) -> RepairResult:
    return RepairResult(
        success=status == "verification_passed",
        status=status,
        attempts=tuple(attempts),
        verification_runs=verification_runs,
        repairs_attempted=repairs_attempted,
        patches_applied=patches_applied,
        final_exit_code=final_exit_code,
        stopped_reason=status,
    )


def _empty_result(status: str) -> RepairResult:
    return _finish(
        status,
        [],
        verification_runs=0,
        repairs_attempted=0,
        patches_applied=0,
        final_exit_code=None,
    )


def _execute_safely(
    tool_id: str,
    arguments: Mapping[str, object],
    workspace: Workspace,
) -> ToolResult | None:
    try:
        result = execute_tool(tool_id, arguments, workspace=workspace)
    except Exception:
        return None
    return result if isinstance(result, ToolResult) else None


def run_repair_loop(
    verification_argv: Sequence[str],
    repairs: Sequence[Mapping[str, object]],
    *,
    approved: bool = False,
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
    workspace: Workspace | None = None,
) -> RepairResult:
    """Verify, apply predefined repairs, and reverify within hard limits."""

    try:
        argv, actions, is_approved, repair_limit = _validate_request(
            verification_argv,
            repairs,
            approved,
            max_attempts,
            workspace,
        )
    except _RequestError as exc:
        return _empty_result(exc.code)

    if not is_approved:
        return _empty_result("approval_required")

    try:
        active_workspace = workspace or Workspace()
    except Exception:
        return _empty_result("internal_safe_failure")

    attempts: list[RepairAttempt] = []
    attempted_fingerprints: set[str] = set()
    verification_runs = 0
    repairs_attempted = 0
    patches_applied = 0
    repair_index = 0

    def stop(
        status: str,
        exit_code: int | None,
        *,
        verification_success: bool = False,
        patch_applied: bool = False,
    ) -> RepairResult:
        attempts.append(RepairAttempt(
            verification_runs,
            VERIFICATION_TOOL_ID,
            verification_success,
            exit_code,
            patch_applied,
            status,
        ))
        return _finish(
            status,
            attempts,
            verification_runs=verification_runs,
            repairs_attempted=repairs_attempted,
            patches_applied=patches_applied,
            final_exit_code=exit_code,
        )

    maximum_verifications = min(MAX_VERIFICATION_RUNS, repair_limit + 1)
    for verification_runs in range(1, maximum_verifications + 1):
        verification = _execute_safely(
            VERIFICATION_TOOL_ID,
            {"argv": argv},
            active_workspace,
        )
        if verification is None:
            return stop("internal_safe_failure", None)

        exit_code = _exit_code(verification)
        verification_status = _verification_status(verification)
        if verification_status == "verification_passed":
            return stop(
                verification_status,
                exit_code,
                verification_success=True,
            )
        if verification_status != "verification_failed":
            return stop(verification_status, exit_code)
        if repairs_attempted >= repair_limit:
            return stop("attempt_limit", exit_code)
        if repair_index >= len(actions):
            return stop("no_repair_available", exit_code)

        repair = actions[repair_index]
        repair_index += 1
        fingerprint = _repair_fingerprint(repair)
        if fingerprint in attempted_fingerprints:
            return stop("duplicate_repair", exit_code)
        attempted_fingerprints.add(fingerprint)
        repairs_attempted += 1

        repair_result = _execute_safely(
            repair.tool_id,
            repair.arguments,
            active_workspace,
        )
        if repair_result is None:
            return stop("internal_safe_failure", exit_code)
        repair_status = (
            "repair_applied"
            if repair_result.success
            else _repair_failure_status(repair_result)
        )
        if repair_status != "repair_applied":
            return stop(repair_status, exit_code)

        patches_applied += 1
        attempts.append(RepairAttempt(
            verification_runs,
            VERIFICATION_TOOL_ID,
            False,
            exit_code,
            True,
            repair_status,
        ))

    return _finish(
        "internal_safe_failure",
        attempts,
        verification_runs=verification_runs,
        repairs_attempted=repairs_attempted,
        patches_applied=patches_applied,
        final_exit_code=attempts[-1].exit_code if attempts else None,
    )
