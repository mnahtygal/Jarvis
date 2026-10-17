"""Deterministic Phase 1 Brain-to-Developer Agent bridge.

Only the three read-only Developer Agent tools in ``PHASE1_EXECUTION_ALLOWLIST``
may execute. All other recognized developer operations stop before dispatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath
from types import MappingProxyType
from typing import Mapping

from core.capability_registry import (
    PHASE1_DEVELOPER_EXECUTION_ALLOWLIST,
    get_capability,
)
from core.developer_agent.executor import execute_tool
from core.developer_agent.registry import get_tool
from core.developer_agent.tool_models import ToolResult


PHASE1_EXECUTION_ALLOWLIST = PHASE1_DEVELOPER_EXECUTION_ALLOWLIST

DEVELOPER_EXECUTABLE = "executable"
DEVELOPER_CONFIRMATION_REQUIRED = "confirmation_required"
DEVELOPER_UNSUPPORTED = "unsupported"

MAX_DEVELOPER_REQUEST_LENGTH = 500
MAX_PATH_LENGTH = 4096
_UNSAFE_PATH_CHARACTERS = frozenset("$%;&|><`\\*?[]{}()!,:=#^\"'")


@dataclass(frozen=True)
class DeveloperRequest:
    """A bounded deterministic developer request without generated arguments."""

    mode: str
    capability_id: str | None = None
    arguments: Mapping[str, object] = field(default_factory=dict)
    safe_argument_summary: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class DeveloperBridgeResult:
    """Safe internal result adapted for the Brain response lifecycle."""

    status: str
    capability_id: str | None
    response: str
    safe_argument_summary: tuple[str, ...] = ()
    tool_invoked: bool = False
    tool_success: bool | None = None
    error_code: str | None = None


_GIT_STATUS_PATTERN = re.compile(
    r"^(?:show(?:\s+me)?|get|check)?\s*(?:the\s+)?git\s+status[?.!]*$",
    re.IGNORECASE,
)
_LIST_FILES_PATTERN = re.compile(
    r"^list\s+(?:the\s+)?files(?:\s+(?:in|under|from)\s+(.+?))?[?.!]*$",
    re.IGNORECASE,
)
_READ_FILE_PATTERN = re.compile(
    r"^(?:read|show|open)(?:\s+me)?\s+(?:the\s+)?(?:file\s+)?(.+?)[?!]*$",
    re.IGNORECASE,
)
_DEVELOPER_PREFIX_PATTERN = re.compile(
    r"^(?:read|show|open|list|write|create|patch|edit|modify|run|repair|fix|"
    r"stage|commit|developer)\b",
    re.IGNORECASE,
)
_STAGE_PATTERN = re.compile(
    r"^(?:git\s+)?(?:stage|add)(?:\s+the)?\s+(?:change|changes|file|files)[?.!]*$",
    re.IGNORECASE,
)
_COMMIT_PATTERN = re.compile(
    r"^(?:git\s+)?commit(?:\s+the)?(?:\s+verified)?\s+(?:change|changes)[?.!]*$",
    re.IGNORECASE,
)


def _safe_path(value: str, *, require_file_signal: bool) -> str | None:
    candidate = value.strip()
    if candidate.startswith(("\"", "'")):
        quote = candidate[0]
        if len(candidate) < 2 or not candidate.endswith(quote):
            return None
        candidate = candidate[1:-1]
    elif candidate.endswith(("\"", "'")):
        return None

    try:
        encoded_length = len(candidate.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        return None
    if (
        not candidate
        or encoded_length > MAX_PATH_LENGTH
        or "\x00" in candidate
        or any(character.isspace() for character in candidate)
        or any(character in _UNSAFE_PATH_CHARACTERS for character in candidate)
        or candidate.startswith("~")
    ):
        return None

    path = PurePath(candidate)
    if path.is_absolute() or ".." in path.parts:
        return None
    if candidate.casefold() in {"file", "a-file", "the-file"}:
        return None
    if require_file_signal and "/" not in candidate and "." not in path.name:
        return None
    return candidate


def _confirmation_request(
    capability_id: str,
    *,
    summary: tuple[str, ...] = (),
) -> DeveloperRequest:
    return DeveloperRequest(
        DEVELOPER_CONFIRMATION_REQUIRED,
        capability_id,
        safe_argument_summary=summary,
    )


def classify_developer_request(command: str) -> DeveloperRequest | None:
    """Recognize fixed developer request families without models or side effects."""

    if not isinstance(command, str):
        return None
    cleaned = command.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_DEVELOPER_REQUEST_LENGTH or "\n" in cleaned:
        if _DEVELOPER_PREFIX_PATTERN.match(cleaned):
            return DeveloperRequest(DEVELOPER_UNSUPPORTED)
        return None
    text = " ".join(cleaned.casefold().split())
    words = set(re.findall(r"[a-z0-9_]+", text))

    if _GIT_STATUS_PATTERN.fullmatch(cleaned):
        return DeveloperRequest(DEVELOPER_EXECUTABLE, "developer.git_status")

    match = _LIST_FILES_PATTERN.fullmatch(cleaned)
    if match:
        raw_path = match.group(1) or "."
        path = _safe_path(raw_path, require_file_signal=False)
        if path is None:
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.list_files")
        return DeveloperRequest(
            DEVELOPER_EXECUTABLE,
            "developer.list_files",
            {"path": path},
            (f"path={path}",),
        )

    match = _READ_FILE_PATTERN.fullmatch(cleaned)
    if match:
        raw_path = match.group(1)
        has_file_signal = (
            re.search(r"\bfile\b", text) is not None
            or "/" in raw_path
            or "." in PurePath(raw_path).name
        )
        if not has_file_signal:
            return None
        path = _safe_path(raw_path, require_file_signal=True)
        if path is None:
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.read_file")
        return DeveloperRequest(
            DEVELOPER_EXECUTABLE,
            "developer.read_file",
            {"path": path},
            (f"path={path}",),
        )

    if "gradle" in words and words.intersection({"test", "tests", "run", "build"}):
        return _confirmation_request("developer.gradle_test")
    if any(phrase in text for phrase in ("bounded session", "autonomous developer session")):
        return _confirmation_request("developer.bounded_session")
    if "propose" in words and "repair" in words:
        return _confirmation_request("developer.propose_repair")
    if re.search(r"\b(?:repair|fix)\b", text) and any(
        word in words for word in ("test", "tests", "failure", "failing")
    ):
        return _confirmation_request("developer.repair_loop")
    if _STAGE_PATTERN.fullmatch(cleaned):
        return _confirmation_request("developer.git_stage")
    if _COMMIT_PATTERN.fullmatch(cleaned):
        return _confirmation_request("developer.git_commit")
    if re.search(r"\b(?:patch|edit|modify)\b", text) and any(
        word in words for word in ("file", "function", "code", "source", "this")
    ):
        return _confirmation_request("developer.patch_file")
    if re.search(r"\b(?:write|create)\b", text) and any(
        word in words for word in ("file", "script", "module")
    ):
        return _confirmation_request("developer.write_file")
    exact_test_runs = {"run test", "run tests", "run the test", "run the tests"}
    has_explicit_run_target = words.intersection({
        "command", "pytest", "compileall", "py_compile",
    })
    has_scoped_tests = words.intersection({"test", "tests"}) and words.intersection({
        "brain", "unit", "python",
    })
    if text in exact_test_runs or (
        text.startswith("run ") and (has_explicit_run_target or has_scoped_tests)
    ):
        return _confirmation_request("developer.run_command")

    if any(phrase in text for phrase in ("developer request", "developer task", "developer work")):
        return DeveloperRequest(DEVELOPER_UNSUPPORTED)
    return None


def _validate_executable_capability(capability_id: str) -> str | None:
    if capability_id not in PHASE1_EXECUTION_ALLOWLIST:
        return "capability_not_allowed"

    brain_capability = get_capability(capability_id)
    developer_tool = get_tool(capability_id)
    if brain_capability is None or developer_tool is None:
        return "capability_not_registered"
    if (
        brain_capability.capability_id != capability_id
        or developer_tool.tool_id != capability_id
    ):
        return "capability_metadata_mismatch"
    if not brain_capability.enabled or not developer_tool.enabled:
        return "capability_disabled"
    if not brain_capability.executable or not developer_tool.executable:
        return "capability_not_executable"
    if not brain_capability.read_only or not developer_tool.read_only:
        return "capability_not_read_only"
    if brain_capability.mutating or developer_tool.mutating:
        return "capability_mutating"
    if brain_capability.requires_confirmation or developer_tool.requires_confirmation:
        return "confirmation_required"
    return None


def _adapt_tool_result(result: ToolResult) -> str:
    if result.success:
        if result.tool_name == "developer.read_file":
            return result.output or "The file is empty."
        if result.tool_name == "developer.list_files":
            return result.output or "No files were found in that directory."
        if result.tool_name == "developer.git_status":
            return result.output or "Git status is clean."
        return result.output or "Developer tool completed successfully."

    error_code = result.error_code or "tool_failed"
    return f"Developer tool request was refused safely ({error_code}): {result.output}"


def execute_developer_request(request: DeveloperRequest) -> DeveloperBridgeResult:
    """Execute an approved read-only request or return a safe stop result."""

    if request.mode == DEVELOPER_CONFIRMATION_REQUIRED:
        capability_id = request.capability_id or "developer.unknown"
        return DeveloperBridgeResult(
            status=DEVELOPER_CONFIRMATION_REQUIRED,
            capability_id=request.capability_id,
            response=(
                f"Developer request recognized for {capability_id}. "
                "Confirmation is required, so nothing was executed."
            ),
            safe_argument_summary=request.safe_argument_summary,
        )

    if request.mode != DEVELOPER_EXECUTABLE or not request.capability_id:
        return DeveloperBridgeResult(
            status=DEVELOPER_UNSUPPORTED,
            capability_id=request.capability_id,
            response=(
                "That developer request is ambiguous or unsupported in Phase 1. "
                "Nothing was executed."
            ),
            safe_argument_summary=request.safe_argument_summary,
            error_code="unsupported_developer_request",
        )

    validation_error = _validate_executable_capability(request.capability_id)
    if validation_error is not None:
        return DeveloperBridgeResult(
            status="rejected",
            capability_id=request.capability_id,
            response=(
                "Developer tool execution was refused safely "
                f"({validation_error})."
            ),
            safe_argument_summary=request.safe_argument_summary,
            error_code=validation_error,
        )

    result = execute_tool(request.capability_id, request.arguments)
    return DeveloperBridgeResult(
        status="executed" if result.success else "rejected",
        capability_id=request.capability_id,
        response=_adapt_tool_result(result),
        safe_argument_summary=request.safe_argument_summary,
        tool_invoked=True,
        tool_success=result.success,
        error_code=result.error_code,
    )
