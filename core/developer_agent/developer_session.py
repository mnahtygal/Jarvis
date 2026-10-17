"""Bounded autonomous repair sessions within a fixed, human-approved scope."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import unicodedata

from core.developer_agent.executor import execute_tool
from core.developer_agent.policy import git_protection_code
from core.developer_agent.repair_proposal import (
    MAX_CANDIDATE_FILES,
    MAX_CANDIDATE_PATH_BYTES,
    MAX_FAILURE_OUTPUT_BYTES,
    MAX_MODEL_CALLS,
    RepairProposal,
    RepairProposalRequest,
    proposal_to_predefined_repair,
    propose_repair,
)
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.workspace import Workspace, WorkspacePathError


MAX_SESSION_REPAIRS = 2
MAX_SESSION_VERIFICATION_RUNS = 3
MAX_SESSION_PROPOSAL_REQUESTS = 2
MAX_MUTATION_PATHS = 5
MAX_SESSION_MODEL_CALLS = MAX_SESSION_PROPOSAL_REQUESTS * MAX_MODEL_CALLS

_RUN_COMMAND_VERIFICATION = "run_command"
_GRADLE_TEST_VERIFICATION = "gradle_test"
_VERIFICATION_TOOL_IDS = {
    _RUN_COMMAND_VERIFICATION: "developer.run_command",
    _GRADLE_TEST_VERIFICATION: "developer.gradle_test",
}
_ALLOWED_MUTATION_TOOLS = frozenset({
    "developer.patch_file",
    "developer.write_file",
})
_VERIFICATION_POLICY_ERRORS = frozenset({
    "approval_required",
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
    "validation_failed",
    "distribution_sha256_mismatch",
    "gradlew_not_executable",
    "invalid_distribution_sha256",
    "invalid_project_path",
    "missing_gradlew",
    "missing_wrapper_jar",
    "missing_wrapper_properties",
    "project_init_script_not_allowed",
    "project_not_directory",
    "project_not_found",
    "project_path_not_allowed",
    "unsafe_gradle_properties",
    "unsafe_gradle_distribution",
    "unsafe_gradlew",
    "unsafe_project_symlink",
    "unsafe_wrapper_jar",
    "unsafe_wrapper_properties",
    "unsafe_wrapper_url",
    "unsupported_gradle_version",
    "untrusted_gradlew",
    "untrusted_wrapper_jar",
    "wrapper_properties_invalid",
    "wrapper_properties_not_allowed",
    "wrapper_properties_unreadable",
})
_VERIFICATION_INFRASTRUCTURE_ERRORS = frozenset({
    "aapt2_unavailable",
    "android_sdk_incomplete",
    "android_sdk_unavailable",
    "command_unavailable",
    "execution_failed",
    "gradle_cache_unavailable",
    "gradle_distribution_not_cached",
    "offline_cache_miss",
    "untrusted_aapt2",
})
_MUTATION_OPERATION_ERRORS = frozenset({
    "create_parent_failed",
    "internal_error",
    "mode_preservation_failed",
    "read_failed",
    "temp_file_failed",
    "write_failed",
})
_PATHSPEC_CHARACTERS = frozenset("*?[]")
_DIAGNOSTIC_MARKER = "\n...[diagnostic truncated]...\n"

ModelCall = Callable[[str, str], object]
ExecutorCall = Callable[..., ToolResult]


@dataclass(frozen=True)
class VerificationSpec:
    """One immutable verification kind and its kind-specific parameters."""

    kind: str
    argv: tuple[str, ...] = ()
    project_path: str | None = None


@dataclass(frozen=True)
class DeveloperSessionRequest:
    """One ephemeral approval and its complete static session scope."""

    verification_argv: tuple[str, ...] | None
    candidate_files: tuple[str, ...]
    allowed_mutation_paths: tuple[str, ...]
    approved: bool
    max_repairs: int = MAX_SESSION_REPAIRS
    max_verification_runs: int = MAX_SESSION_VERIFICATION_RUNS
    max_proposal_requests: int = MAX_SESSION_PROPOSAL_REQUESTS
    verification_spec: VerificationSpec | None = None


@dataclass(frozen=True)
class DeveloperSessionAttempt:
    """Safe, payload-free summary of one verification cycle."""

    attempt_number: int
    verification_status: str
    proposal_status: str | None
    proposal_type: str | None
    proposal_path: str | None
    proposal_confidence: float | None
    mutation_status: str | None


@dataclass(frozen=True)
class DeveloperSessionResult:
    """Bounded session outcome without diagnostics, source, or repair payloads."""

    success: bool
    status: str
    verification_runs: int
    proposals_generated: int
    repairs_applied: int
    attempts: tuple[DeveloperSessionAttempt, ...]
    changed_paths: tuple[str, ...]
    stopped_reason: str


@dataclass(frozen=True)
class DiagnosticExcerpt:
    """Ephemeral bounded verification output passed only to Phase 6."""

    text: str
    truncated: bool
    original_bytes: int


@dataclass(frozen=True)
class _FrozenSessionScope:
    verification: VerificationSpec
    candidate_files: tuple[str, ...]
    allowed_mutation_paths: tuple[str, ...]
    max_repairs: int
    max_verification_runs: int
    max_proposal_requests: int


class _RequestError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _result(
    success: bool,
    status: str,
    *,
    verification_runs: int = 0,
    proposals_generated: int = 0,
    repairs_applied: int = 0,
    attempts: tuple[DeveloperSessionAttempt, ...] = (),
    changed_paths: tuple[str, ...] = (),
) -> DeveloperSessionResult:
    return DeveloperSessionResult(
        success=success,
        status=status,
        verification_runs=verification_runs,
        proposals_generated=proposals_generated,
        repairs_applied=repairs_applied,
        attempts=attempts,
        changed_paths=changed_paths,
        stopped_reason=status,
    )


def _validate_limit(value: object, *, maximum: int, minimum: int, code: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not minimum <= value <= maximum
    ):
        raise _RequestError(code)
    return value


def _validate_scope_path(path: object, workspace: Workspace) -> str:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise _RequestError("invalid_scope_path")
    try:
        encoded = path.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise _RequestError("invalid_scope_path") from None
    requested = Path(path)
    if (
        len(encoded) > MAX_CANDIDATE_PATH_BYTES
        or requested.is_absolute()
        or path == "."
        or ".." in requested.parts
        or requested.as_posix() != path
        or path.startswith(("-", ":"))
        or "\\" in path
        or any(character in path for character in _PATHSPEC_CHARACTERS)
        or any(unicodedata.category(character).startswith("C") for character in path)
        or git_protection_code(requested) is not None
    ):
        raise _RequestError("protected_scope_path")
    expected = workspace.root / requested
    try:
        resolved = workspace.resolve_path(path, require_exists=False)
    except WorkspacePathError:
        if expected.is_symlink():
            raise _RequestError("unsafe_scope_symlink") from None
        raise _RequestError("invalid_scope_path") from None
    if resolved != expected:
        raise _RequestError("unsafe_scope_symlink")
    try:
        relative = resolved.relative_to(workspace.root)
    except ValueError:
        raise _RequestError("invalid_scope_path") from None
    if git_protection_code(requested, relative) is not None:
        raise _RequestError("protected_scope_path")
    if resolved.exists():
        if not resolved.is_file():
            raise _RequestError("invalid_scope_path")
    else:
        try:
            parent = workspace.resolve_path(str(resolved.parent))
        except WorkspacePathError:
            raise _RequestError("invalid_scope_parent") from None
        if parent != resolved.parent or not parent.is_dir():
            raise _RequestError("invalid_scope_parent")
    return path


def _validate_path_tuple(
    value: object,
    *,
    workspace: Workspace,
    maximum: int,
    count_code: str,
) -> tuple[str, ...]:
    if type(value) is not tuple or not value or len(value) > maximum:
        raise _RequestError(count_code)
    paths = tuple(_validate_scope_path(path, workspace) for path in value)
    if len(paths) != len(set(paths)):
        raise _RequestError("duplicate_scope_path")
    return paths


def _freeze_request(
    request: object,
    workspace: Workspace,
) -> _FrozenSessionScope:
    if type(request) is not DeveloperSessionRequest:
        raise _RequestError("invalid_request")
    verification = _freeze_verification(request, workspace)
    candidates = _validate_path_tuple(
        request.candidate_files,
        workspace=workspace,
        maximum=MAX_CANDIDATE_FILES,
        count_code="invalid_candidate_count",
    )
    mutation_paths = _validate_path_tuple(
        request.allowed_mutation_paths,
        workspace=workspace,
        maximum=MAX_MUTATION_PATHS,
        count_code="invalid_mutation_path_count",
    )
    return _FrozenSessionScope(
        verification=verification,
        candidate_files=candidates,
        allowed_mutation_paths=mutation_paths,
        max_repairs=_validate_limit(
            request.max_repairs,
            maximum=MAX_SESSION_REPAIRS,
            minimum=0,
            code="invalid_repair_limit",
        ),
        max_verification_runs=_validate_limit(
            request.max_verification_runs,
            maximum=MAX_SESSION_VERIFICATION_RUNS,
            minimum=1,
            code="invalid_verification_limit",
        ),
        max_proposal_requests=_validate_limit(
            request.max_proposal_requests,
            maximum=MAX_SESSION_PROPOSAL_REQUESTS,
            minimum=0,
            code="invalid_proposal_limit",
        ),
    )


def validate_developer_session_request(
    request: object,
    *,
    workspace: Workspace | None = None,
) -> str | None:
    """Validate one session scope without verification, model, or mutation work."""

    try:
        _freeze_request(request, workspace or Workspace())
    except _RequestError as exc:
        return exc.code
    except Exception:
        return "invalid_request"
    return None


def _valid_verification_argv(value: object) -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        raise _RequestError("invalid_verification_argv")
    if any(
        not isinstance(argument, str) or not argument or "\x00" in argument
        for argument in value
    ):
        raise _RequestError("invalid_verification_argv")
    return tuple(value)


def _freeze_gradle_project_path(value: object, workspace: Workspace) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise _RequestError("invalid_gradle_project_path")
    requested = Path(value)
    if ".." in requested.parts or "~" in requested.parts:
        raise _RequestError("invalid_gradle_project_path")
    expected = requested if requested.is_absolute() else workspace.root / requested
    try:
        resolved = expected.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise _RequestError("invalid_gradle_project_path") from None
    if (
        not resolved.is_relative_to(workspace.root)
        or not resolved.is_dir()
        or resolved != expected.absolute()
    ):
        raise _RequestError("invalid_gradle_project_path")
    return value


def _freeze_verification(
    request: DeveloperSessionRequest,
    workspace: Workspace,
) -> VerificationSpec:
    if request.verification_spec is None:
        return VerificationSpec(
            _RUN_COMMAND_VERIFICATION,
            argv=_valid_verification_argv(request.verification_argv),
        )
    if request.verification_argv is not None:
        raise _RequestError("ambiguous_verification")
    if type(request.verification_spec) is not VerificationSpec:
        raise _RequestError("invalid_verification_spec")

    spec = request.verification_spec
    if spec.kind == _RUN_COMMAND_VERIFICATION:
        if spec.project_path is not None:
            raise _RequestError("invalid_verification_spec")
        return VerificationSpec(spec.kind, argv=_valid_verification_argv(spec.argv))
    if spec.kind == _GRADLE_TEST_VERIFICATION:
        if type(spec.argv) is not tuple or spec.argv:
            raise _RequestError("invalid_verification_spec")
        return VerificationSpec(
            spec.kind,
            project_path=_freeze_gradle_project_path(spec.project_path, workspace),
        )
    raise _RequestError("invalid_verification_kind")


def _valid_utf8_prefix(value: bytes, maximum: int) -> str:
    return value[:maximum].decode("utf-8", errors="ignore")


def _valid_utf8_suffix(value: bytes, maximum: int) -> str:
    return value[-maximum:].decode("utf-8", errors="ignore") if maximum else ""


def build_diagnostic_excerpt(
    result: ToolResult,
    *,
    maximum_bytes: int = MAX_FAILURE_OUTPUT_BYTES,
) -> DiagnosticExcerpt:
    """Build a deterministic UTF-8 head/tail excerpt without persisting output."""

    if type(result) is not ToolResult:
        raise ValueError("invalid tool result")
    if (
        not isinstance(maximum_bytes, int)
        or isinstance(maximum_bytes, bool)
        or maximum_bytes <= 0
        or maximum_bytes > MAX_FAILURE_OUTPUT_BYTES
    ):
        raise ValueError("invalid diagnostic bound")
    raw = result.output.encode("utf-8", errors="replace")
    upstream_truncated = result.metadata.get("output_truncated") is True
    if len(raw) <= maximum_bytes:
        return DiagnosticExcerpt(
            raw.decode("utf-8"),
            upstream_truncated,
            len(raw),
        )

    marker = _DIAGNOSTIC_MARKER.encode("utf-8")
    content_budget = maximum_bytes - len(marker)
    if content_budget < 0:
        marker = b""
        content_budget = maximum_bytes
    head_budget = (content_budget + 1) // 2
    tail_budget = content_budget - head_budget
    text = (
        _valid_utf8_prefix(raw, head_budget)
        + marker.decode("utf-8")
        + _valid_utf8_suffix(raw, tail_budget)
    )
    while len(text.encode("utf-8")) > maximum_bytes:
        text = text[:-1]
    return DiagnosticExcerpt(text, True, len(raw))


def _verification_status(result: ToolResult, expected_tool_id: str) -> str:
    if result.tool_name != expected_tool_id:
        return "unexpected_executor_failure"
    if result.success:
        return "verification_passed"
    if result.error_code == "timeout" or result.metadata.get("timed_out") is True:
        return "verification_timeout"
    if result.error_code in _VERIFICATION_POLICY_ERRORS:
        return "verification_policy_rejected"
    if result.error_code in _VERIFICATION_INFRASTRUCTURE_ERRORS:
        return "verification_infrastructure_failure"
    return "verification_failed"


def _verification_summary(result: ToolResult, excerpt: DiagnosticExcerpt) -> str:
    exit_code = result.metadata.get("exit_code")
    safe_exit_code = (
        exit_code
        if isinstance(exit_code, int) and not isinstance(exit_code, bool)
        else None
    )
    return (
        f"{result.tool_name} failed; "
        f"error_code={result.error_code or 'command_failed'}; "
        f"exit_code={safe_exit_code}; "
        f"diagnostic_truncated={str(excerpt.truncated).lower()}"
    )


def _verification_call(spec: VerificationSpec) -> tuple[str, dict[str, object]]:
    tool_id = _VERIFICATION_TOOL_IDS[spec.kind]
    if spec.kind == _RUN_COMMAND_VERIFICATION:
        return tool_id, {"argv": spec.argv}
    return tool_id, {"project_path": spec.project_path, "approved": True}


def _attempt(
    number: int,
    verification_status: str,
    *,
    proposal_status: str | None = None,
    proposal_type: str | None = None,
    proposal_path: str | None = None,
    proposal_confidence: float | None = None,
    mutation_status: str | None = None,
) -> DeveloperSessionAttempt:
    return DeveloperSessionAttempt(
        number,
        verification_status,
        proposal_status,
        proposal_type,
        proposal_path,
        proposal_confidence,
        mutation_status,
    )


def run_developer_session_request(
    request: DeveloperSessionRequest,
    *,
    workspace: Workspace | None = None,
    model_call: ModelCall | None = None,
    _executor: ExecutorCall | None = None,
) -> DeveloperSessionResult:
    """Run one approved session; approval and all scope disappear on return."""

    if type(request) is not DeveloperSessionRequest:
        return _result(False, "invalid_request")
    if request.approved is not True:
        return _result(False, "approval_required")

    try:
        active_workspace = workspace or Workspace()
        scope = _freeze_request(request, active_workspace)
    except _RequestError as exc:
        return _result(False, exc.code)
    except Exception:
        return _result(False, "invalid_request")

    executor = _executor or execute_tool
    attempts: list[DeveloperSessionAttempt] = []
    changed_paths: list[str] = []
    verification_runs = 0
    proposal_requests = 0
    repairs_applied = 0

    def finish(success: bool, status: str) -> DeveloperSessionResult:
        return _result(
            success,
            status,
            verification_runs=verification_runs,
            proposals_generated=proposal_requests,
            repairs_applied=repairs_applied,
            attempts=tuple(attempts),
            changed_paths=tuple(changed_paths),
        )

    while verification_runs < scope.max_verification_runs:
        verification_tool_id, verification_arguments = _verification_call(
            scope.verification
        )
        try:
            verification = executor(
                verification_tool_id,
                verification_arguments,
                workspace=active_workspace,
            )
        except Exception:
            attempts.append(_attempt(
                verification_runs + 1,
                "unexpected_executor_failure",
            ))
            return finish(False, "unexpected_executor_failure")
        verification_runs += 1
        if type(verification) is not ToolResult:
            attempts.append(_attempt(
                verification_runs,
                "unexpected_executor_failure",
            ))
            return finish(False, "unexpected_executor_failure")

        verification_status = _verification_status(
            verification,
            verification_tool_id,
        )
        if verification_status == "verification_passed":
            attempts.append(_attempt(verification_runs, verification_status))
            return finish(True, verification_status)
        if verification_status != "verification_failed":
            attempts.append(_attempt(verification_runs, verification_status))
            return finish(False, verification_status)

        if repairs_applied >= scope.max_repairs:
            attempts.append(_attempt(verification_runs, verification_status))
            return finish(False, "repair_limit")
        if verification_runs >= scope.max_verification_runs:
            attempts.append(_attempt(verification_runs, verification_status))
            return finish(False, "verification_limit")
        if proposal_requests >= scope.max_proposal_requests:
            attempts.append(_attempt(verification_runs, verification_status))
            return finish(False, "proposal_request_limit")

        try:
            diagnostic = build_diagnostic_excerpt(verification)
            proposal_request = RepairProposalRequest(
                verification_summary=_verification_summary(verification, diagnostic),
                failure_output=diagnostic.text,
                candidate_files=scope.candidate_files,
            )
        except Exception:
            attempts.append(_attempt(
                verification_runs,
                "unexpected_executor_failure",
            ))
            return finish(False, "unexpected_executor_failure")
        proposal_requests += 1
        try:
            proposal = propose_repair(
                proposal_request,
                workspace=active_workspace,
                model_call=model_call,
            )
        except Exception:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                proposal_status="model_failure",
            ))
            return finish(False, "model_failure")
        if type(proposal) is not RepairProposal:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                proposal_status="invalid_proposal_result",
            ))
            return finish(False, "invalid_proposal_result")

        proposal_path = proposal.path if isinstance(proposal.path, str) else None
        proposal_confidence = (
            proposal.confidence
            if isinstance(proposal.confidence, float)
            else None
        )
        proposal_details = {
            "proposal_status": proposal.status,
            "proposal_type": proposal.proposal_type,
            "proposal_path": proposal_path,
            "proposal_confidence": proposal_confidence,
        }
        if not proposal.valid:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                **proposal_details,
            ))
            return finish(False, proposal.status)
        if proposal.proposal_type == "no_fix":
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                **proposal_details,
            ))
            return finish(False, "no_fix")
        if not proposal.eligible_for_repair:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                **proposal_details,
            ))
            return finish(False, "low_confidence")
        if proposal_path not in scope.allowed_mutation_paths:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                **proposal_details,
            ))
            return finish(False, "proposal_outside_mutation_scope")

        try:
            repair = proposal_to_predefined_repair(
                proposal,
                workspace=active_workspace,
            )
        except Exception:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status="not_applied",
                **proposal_details,
            ))
            return finish(False, "proposal_conversion_failed")
        if not isinstance(repair, Mapping):
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status="not_applied",
                **proposal_details,
            ))
            return finish(False, "stale_or_invalid_proposal")
        tool_id = repair.get("tool")
        arguments = repair.get("arguments")
        if (
            tool_id not in _ALLOWED_MUTATION_TOOLS
            or not isinstance(arguments, Mapping)
            or arguments.get("path") != proposal_path
            or arguments.get("path") not in scope.allowed_mutation_paths
        ):
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status="not_applied",
                **proposal_details,
            ))
            return finish(False, "proposal_conversion_failed")

        try:
            mutation = executor(
                tool_id,
                arguments,
                workspace=active_workspace,
            )
        except Exception:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status="unexpected_executor_failure",
                **proposal_details,
            ))
            return finish(False, "unexpected_executor_failure")
        if type(mutation) is not ToolResult or mutation.tool_name != tool_id:
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status="unexpected_executor_failure",
                **proposal_details,
            ))
            return finish(False, "unexpected_executor_failure")
        if not mutation.success:
            mutation_status = (
                "failed"
                if mutation.error_code in _MUTATION_OPERATION_ERRORS
                else "rejected"
            )
            attempts.append(_attempt(
                verification_runs,
                verification_status,
                mutation_status=mutation_status,
                **proposal_details,
            ))
            return finish(
                False,
                "mutation_failed" if mutation_status == "failed" else "mutation_rejected",
            )

        repairs_applied += 1
        if proposal_path not in changed_paths:
            changed_paths.append(proposal_path)
        attempts.append(_attempt(
            verification_runs,
            verification_status,
            mutation_status="applied",
            **proposal_details,
        ))

    return finish(False, "verification_limit")


def run_bounded_developer_session(
    verification_argv: object,
    candidate_files: object,
    allowed_mutation_paths: object,
    *,
    approved: object = False,
    max_repairs: object = MAX_SESSION_REPAIRS,
    max_verification_runs: object = MAX_SESSION_VERIFICATION_RUNS,
    max_proposal_requests: object = MAX_SESSION_PROPOSAL_REQUESTS,
    workspace: Workspace | None = None,
    model_call: ModelCall | None = None,
    _executor: ExecutorCall | None = None,
    verification_spec: VerificationSpec | None = None,
) -> DeveloperSessionResult:
    """Construct and run one strictly validated bounded session request."""

    request = DeveloperSessionRequest(
        verification_argv=verification_argv,
        candidate_files=candidate_files,
        allowed_mutation_paths=allowed_mutation_paths,
        approved=approved,
        max_repairs=max_repairs,
        max_verification_runs=max_verification_runs,
        max_proposal_requests=max_proposal_requests,
        verification_spec=verification_spec,
    )
    return run_developer_session_request(
        request,
        workspace=workspace,
        model_call=model_call,
        _executor=_executor,
    )
