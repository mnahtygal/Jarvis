"""Deterministic Brain-to-Developer Agent bridge with single-use approvals."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import time
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePath
from threading import Lock
from types import MappingProxyType
from typing import Mapping

from core.capability_registry import (
    PHASE1_DEVELOPER_EXECUTION_ALLOWLIST,
    PHASE2_DEVELOPER_APPROVAL_ALLOWLIST,
    PHASE3_DEVELOPER_SESSION_ALLOWLIST,
    PHASE5_DEVELOPER_GREENFIELD_ALLOWLIST,
    get_capability,
)
from core.developer_agent.command_policy import CommandPolicyError, validate_command
from core.developer_agent.developer_session import (
    MAX_SESSION_PROPOSAL_REQUESTS,
    MAX_SESSION_REPAIRS,
    MAX_SESSION_VERIFICATION_RUNS,
    DeveloperSessionRequest,
    DeveloperSessionResult,
    VerificationSpec,
    run_developer_session_request,
    validate_developer_session_request,
)
from core.developer_agent.executor import execute_tool, is_tool_dispatchable
from core.developer_agent.git_safety import (
    inspect_staged,
    repository_state_fingerprint,
    validate_no_external_clean_filters,
    validate_repository,
)
from core.developer_agent.greenfield_project import (
    GreenfieldProjectError,
    GreenfieldProjectManifest,
    GreenfieldProjectResult,
    classify_greenfield_request,
    prepare_greenfield_manifest,
    run_greenfield_project,
    validate_greenfield_manifest,
)
from core.developer_agent.mutation import (
    MAX_FILE_BYTES, MAX_PATCH_PAYLOAD_BYTES, MutationError, encode_text,
    prepare_mutation_target, read_existing_text,
)
from core.developer_agent.registry import get_tool
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.tools.git_commit import validate_commit_message
from core.developer_agent.tools.git_stage import validate_stage_paths
from core.developer_agent.tools.gradle_test import validate_gradle_project
from core.developer_agent.verification import VerificationEvidence, is_successful_verification
from core.developer_agent.workspace import Workspace


PHASE1_EXECUTION_ALLOWLIST = PHASE1_DEVELOPER_EXECUTION_ALLOWLIST
PHASE2_APPROVAL_ALLOWLIST = PHASE2_DEVELOPER_APPROVAL_ALLOWLIST
PHASE3_SESSION_ALLOWLIST = PHASE3_DEVELOPER_SESSION_ALLOWLIST
PHASE5_GREENFIELD_ALLOWLIST = PHASE5_DEVELOPER_GREENFIELD_ALLOWLIST
DEVELOPER_EXECUTABLE = "executable"
DEVELOPER_CONFIRMATION_REQUIRED = "confirmation_required"
DEVELOPER_APPROVAL = "approval"
DEVELOPER_CANCELLATION = "cancellation"
DEVELOPER_UNSUPPORTED = "unsupported"
MAX_DEVELOPER_REQUEST_LENGTH = 500
MAX_PATH_LENGTH = 4096
MAX_PENDING_PAYLOAD_BYTES = 32 * 1024
PENDING_ACTION_TTL_SECONDS = 300.0
_UNSAFE_PATH_CHARACTERS = frozenset("$%;&|><`\\*?[]{}()!,:=#^\"'")


@dataclass(frozen=True)
class DeveloperRequest:
    mode: str
    capability_id: str | None = None
    arguments: Mapping[str, object] = field(default_factory=dict)
    safe_argument_summary: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class DeveloperBridgeResult:
    status: str
    capability_id: str | None
    response: str
    safe_argument_summary: tuple[str, ...] = ()
    tool_invoked: bool = False
    tool_success: bool | None = None
    error_code: str | None = None
    verification_kind: str | None = None
    repair_count: int | None = None
    verification_count: int | None = None
    final_state: str | None = None


@dataclass(frozen=True)
class PendingDeveloperAction:
    capability_id: str
    arguments: Mapping[str, object]
    safe_argument_summary: tuple[str, ...]
    created_at: float
    workspace_root: Path
    registry_signature: tuple[object, ...]
    validation_seal: tuple[object, ...]
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class _VerificationRecord:
    evidence: VerificationEvidence
    workspace_root: Path
    workspace_fingerprint: str


_state_lock = Lock()
_pending_action: PendingDeveloperAction | None = None
_verification_record: _VerificationRecord | None = None
_state_generation = 0

_GIT_STATUS_PATTERN = re.compile(r"^(?:show(?:\s+me)?|get|check)?\s*(?:the\s+)?git\s+status[?.!]*$", re.I)
_LIST_FILES_PATTERN = re.compile(r"^list\s+(?:the\s+)?files(?:\s+(?:in|under|from)\s+(.+?))?[?.!]*$", re.I)
_READ_FILE_PATTERN = re.compile(r"^(?:read|show|open)(?:\s+me)?\s+(?:the\s+)?(?:file\s+)?(.+?)[?!]*$", re.I)
_WRITE_PATTERN = re.compile(r"^(?:write|create)(?:\s+(?:the\s+)?file)?\s+([^\s:]+)(?:\s+with(?:\s+content)?|\s*:)\s+(.+)$", re.I)
_PATCH_PATTERN = re.compile(r"^(?:patch|edit|modify)(?:\s+(?:the\s+)?file)?\s+([^\s:]+)\s+(?:replace|replacing)\s+(\"(?:[^\"\\]|\\.)*\")\s+with\s+(\"(?:[^\"\\]|\\.)*\")$", re.I)
_RUN_COMMAND_PATTERN = re.compile(r"^run\s+command\s*:\s*(.+)$", re.I)
_GRADLE_PATTERN = re.compile(r"^run\s+(?:the\s+)?gradle\s+tests?\s+(?:in|for)\s+([^\s]+)$", re.I)
_STAGE_FILES_PATTERN = re.compile(r"^(?:git\s+)?(?:stage|add)\s+(?:files?\s+)?(.+)$", re.I)
_COMMIT_MESSAGE_PATTERN = re.compile(r"^(?:git\s+)?commit\s+(?:with\s+message\s+|message\s+)(.+)$", re.I)
_PYTHON_SESSION_UNTIL_PATTERN = re.compile(
    r"^(?:fix|repair)\s+([A-Za-z0-9_./-]+\.py)\s+until\s+"
    r"([A-Za-z0-9_./-]+\.py)\s+passes[?.!]*$",
    re.I,
)
_PYTHON_SESSION_ONLY_PATTERN = re.compile(
    r"^fix\s+this\s+bug\s+using\s+only\s+([A-Za-z0-9_./-]+\.py)\s+"
    r"and\s+([A-Za-z0-9_./-]+\.py)[?.!]*$",
    re.I,
)
_GRADLE_SESSION_PATTERN = re.compile(
    r"^fix\s+([A-Za-z0-9_./-]+)\s+using\s+([A-Za-z0-9_./-]+)\s+until\s+"
    r"gradle\s+tests?\s+pass(?:es)?\s+in\s+([A-Za-z0-9_./-]+)[?.!]*$",
    re.I,
)
_DEVELOPER_PREFIX_PATTERN = re.compile(r"^(?:read|show|open|list|write|create|patch|edit|modify|run|repair|fix|stage|add|commit|developer)\b", re.I)
_STAGE_PATTERN = re.compile(r"^(?:git\s+)?(?:stage|add)(?:\s+the)?\s+(?:change|changes|file|files)[?.!]*$", re.I)
_COMMIT_PATTERN = re.compile(r"^(?:git\s+)?commit(?:\s+the)?(?:\s+verified)?\s+(?:change|changes)[?.!]*$", re.I)
_APPROVAL_PATTERN = re.compile(
    r"^(?:approve|yes, approve|proceed|execute it|run it)$",
    re.I,
)
_CANCELLATION_PATTERN = re.compile(
    r"^(?:cancel|never mind|don't run it|stop)$",
    re.I,
)

_CANONICAL_BOUNDED_SESSION_HANDLER = run_developer_session_request
_CANONICAL_GREENFIELD_HANDLER = run_greenfield_project


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
        size = len(candidate.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        return None
    if (not candidate or size > MAX_PATH_LENGTH or "\x00" in candidate
            or any(c.isspace() or c in _UNSAFE_PATH_CHARACTERS for c in candidate)
            or candidate.startswith("~")):
        return None
    path = PurePath(candidate)
    if path.is_absolute() or ".." in path.parts or candidate.casefold() in {"file", "a-file", "the-file"}:
        return None
    if require_file_signal and "/" not in candidate and "." not in path.name:
        return None
    return candidate


def _confirmation_request(capability_id: str, *, arguments: Mapping[str, object] | None = None, summary: tuple[str, ...] = ()) -> DeveloperRequest:
    return DeveloperRequest(DEVELOPER_CONFIRMATION_REQUIRED, capability_id, arguments or {}, summary)


def _shell_words(value: str) -> tuple[str, ...] | None:
    try:
        words = tuple(shlex.split(value, posix=True))
    except ValueError:
        return None
    return words or None


def _json_string(value: str) -> str | None:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, str) else None


def _is_test_path(path: str) -> bool:
    candidate = PurePath(path)
    name = candidate.name.casefold()
    return (
        "tests" in {part.casefold() for part in candidate.parts[:-1]}
        or "test" in {part.casefold() for part in candidate.parts[:-1]}
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(("test.kt", "tests.kt", "test.java", "tests.java"))
    )


def _python_session_request(first: str, second: str) -> DeveloperRequest:
    paths = tuple(
        _safe_path(value, require_file_signal=True)
        for value in (first, second)
    )
    if any(path is None or PurePath(path).suffix.casefold() != ".py" for path in paths):
        return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.bounded_session")
    source, test = paths
    if _is_test_path(source) or not _is_test_path(test):
        return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.bounded_session")
    request = DeveloperSessionRequest(
        verification_argv=None,
        candidate_files=(source, test),
        allowed_mutation_paths=(source,),
        approved=False,
        max_repairs=MAX_SESSION_REPAIRS,
        max_verification_runs=MAX_SESSION_VERIFICATION_RUNS,
        max_proposal_requests=MAX_SESSION_PROPOSAL_REQUESTS,
        verification_spec=VerificationSpec(
            "run_command",
            argv=("pytest", "-q", test),
        ),
    )
    return _confirmation_request(
        "developer.bounded_session",
        arguments={"request": request},
        summary=(
            "verification_kind=pytest",
            "candidate_count=2",
            "writable_count=1",
            f"max_repairs={MAX_SESSION_REPAIRS}",
            f"max_verification_runs={MAX_SESSION_VERIFICATION_RUNS}",
            f"max_proposal_requests={MAX_SESSION_PROPOSAL_REQUESTS}",
        ),
    )


def _gradle_session_request(
    source_value: str,
    test_value: str,
    project_value: str,
) -> DeveloperRequest:
    source = _safe_path(source_value, require_file_signal=True)
    test = _safe_path(test_value, require_file_signal=True)
    project = _safe_path(project_value, require_file_signal=False)
    if (
        source is None
        or test is None
        or project is None
        or PurePath(source).suffix.casefold() not in {".java", ".kt"}
        or PurePath(test).suffix.casefold() not in {".java", ".kt"}
        or _is_test_path(source)
        or not _is_test_path(test)
    ):
        return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.bounded_session")
    request = DeveloperSessionRequest(
        verification_argv=None,
        candidate_files=(source, test),
        allowed_mutation_paths=(source,),
        approved=False,
        max_repairs=MAX_SESSION_REPAIRS,
        max_verification_runs=MAX_SESSION_VERIFICATION_RUNS,
        max_proposal_requests=MAX_SESSION_PROPOSAL_REQUESTS,
        verification_spec=VerificationSpec(
            "gradle_test",
            project_path=project,
        ),
    )
    return _confirmation_request(
        "developer.bounded_session",
        arguments={"request": request},
        summary=(
            "verification_kind=gradle_test",
            "candidate_count=2",
            "writable_count=1",
            f"max_repairs={MAX_SESSION_REPAIRS}",
            f"max_verification_runs={MAX_SESSION_VERIFICATION_RUNS}",
            f"max_proposal_requests={MAX_SESSION_PROPOSAL_REQUESTS}",
        ),
    )


def classify_developer_request(command: str) -> DeveloperRequest | None:
    """Recognize fixed developer request families without a model."""
    if not isinstance(command, str) or not command.strip():
        return None
    cleaned = command.strip()
    if _APPROVAL_PATTERN.fullmatch(cleaned):
        return DeveloperRequest(DEVELOPER_APPROVAL)
    if _CANCELLATION_PATTERN.fullmatch(cleaned):
        return DeveloperRequest(DEVELOPER_CANCELLATION)
    greenfield, greenfield_intent = classify_greenfield_request(cleaned)
    if greenfield_intent:
        if greenfield is None:
            return DeveloperRequest(
                DEVELOPER_UNSUPPORTED,
                "developer.greenfield_project",
            )
        files = tuple(item.path for item in greenfield.files)
        return _confirmation_request(
            "developer.greenfield_project",
            arguments={"request": greenfield},
            summary=(
                f"workspace={greenfield.workspace}",
                f"files={','.join(files)}",
                f"file_count={len(files)}",
                "verification=pytest",
                f"writable_after_creation={sum(item.role == 'source' for item in greenfield.files)}",
            ),
        )
    if len(cleaned) > MAX_DEVELOPER_REQUEST_LENGTH or "\x00" in cleaned or "\n" in cleaned:
        return DeveloperRequest(DEVELOPER_UNSUPPORTED) if _DEVELOPER_PREFIX_PATTERN.match(cleaned) else None
    text = " ".join(cleaned.casefold().split())
    words = set(re.findall(r"[a-z0-9_]+", text))
    match = _PYTHON_SESSION_UNTIL_PATTERN.fullmatch(cleaned)
    if match:
        return _python_session_request(match.group(1), match.group(2))
    match = _PYTHON_SESSION_ONLY_PATTERN.fullmatch(cleaned)
    if match:
        first, second = match.group(1), match.group(2)
        if _is_test_path(first) == _is_test_path(second):
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.bounded_session")
        source, test = (second, first) if _is_test_path(first) else (first, second)
        return _python_session_request(source, test)
    match = _GRADLE_SESSION_PATTERN.fullmatch(cleaned)
    if match:
        return _gradle_session_request(
            match.group(1),
            match.group(2),
            match.group(3),
        )
    if _GIT_STATUS_PATTERN.fullmatch(cleaned):
        return DeveloperRequest(DEVELOPER_EXECUTABLE, "developer.git_status")
    match = _LIST_FILES_PATTERN.fullmatch(cleaned)
    if match:
        path = _safe_path(match.group(1) or ".", require_file_signal=False)
        return (DeveloperRequest(DEVELOPER_EXECUTABLE, "developer.list_files", {"path": path}, (f"path={path}",))
                if path is not None else DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.list_files"))
    match = _READ_FILE_PATTERN.fullmatch(cleaned)
    if match:
        raw_path = match.group(1)
        if not (re.search(r"\bfile\b", text) or "/" in raw_path or "." in PurePath(raw_path).name):
            return None
        path = _safe_path(raw_path, require_file_signal=True)
        return (DeveloperRequest(DEVELOPER_EXECUTABLE, "developer.read_file", {"path": path}, (f"path={path}",))
                if path is not None else DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.read_file"))
    match = _WRITE_PATTERN.fullmatch(cleaned)
    if match:
        path, content = _safe_path(match.group(1), require_file_signal=True), match.group(2)
        if path is None:
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.write_file")
        return _confirmation_request("developer.write_file", arguments={"path": path, "content": content}, summary=(f"path={path}", f"content_bytes={len(content.encode('utf-8'))}"))
    match = _PATCH_PATTERN.fullmatch(cleaned)
    if match:
        path = _safe_path(match.group(1), require_file_signal=True)
        old_text, new_text = _json_string(match.group(2)), _json_string(match.group(3))
        if path is None or old_text is None or new_text is None:
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.patch_file")
        return _confirmation_request("developer.patch_file", arguments={"path": path, "old_text": old_text, "new_text": new_text}, summary=(f"path={path}", f"old_bytes={len(old_text.encode())}", f"new_bytes={len(new_text.encode())}"))
    match = _RUN_COMMAND_PATTERN.fullmatch(cleaned)
    if match:
        argv = _shell_words(match.group(1))
        return (_confirmation_request("developer.run_command", arguments={"argv": argv}, summary=(f"argv_count={len(argv)}",))
                if argv else DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.run_command"))
    match = _GRADLE_PATTERN.fullmatch(cleaned)
    if match:
        path = _safe_path(match.group(1), require_file_signal=False)
        return (_confirmation_request("developer.gradle_test", arguments={"project_path": path}, summary=(f"project_path={path}", "task=testDebugUnitTest", "offline=true"))
                if path else DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.gradle_test"))
    match = _COMMIT_MESSAGE_PATTERN.fullmatch(cleaned)
    if match:
        message_words = _shell_words(match.group(1))
        if not message_words:
            return DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.git_commit")
        message = " ".join(message_words)
        return _confirmation_request("developer.git_commit", arguments={"message": message}, summary=(f"message_bytes={len(message.encode())}",))
    match = _STAGE_FILES_PATTERN.fullmatch(cleaned)
    if match and not _STAGE_PATTERN.fullmatch(cleaned):
        paths = _shell_words(match.group(1))
        return (_confirmation_request("developer.git_stage", arguments={"paths": paths}, summary=tuple(f"path={p}" for p in paths))
                if paths else DeveloperRequest(DEVELOPER_UNSUPPORTED, "developer.git_stage"))
    if "gradle" in words and words.intersection({"test", "tests", "run", "build"}):
        return _confirmation_request("developer.gradle_test")
    if any(p in text for p in (
        "bounded session",
        "bounded repair session",
        "autonomous developer session",
    )):
        return _confirmation_request("developer.bounded_session")
    if "propose" in words and "repair" in words:
        return _confirmation_request("developer.propose_repair")
    if re.search(r"\b(?:repair|fix)\b", text) and words.intersection({"test", "tests", "failure", "failing"}):
        return _confirmation_request("developer.repair_loop")
    if _STAGE_PATTERN.fullmatch(cleaned):
        return _confirmation_request("developer.git_stage")
    if _COMMIT_PATTERN.fullmatch(cleaned):
        return _confirmation_request("developer.git_commit")
    if re.search(r"\b(?:patch|edit|modify)\b", text) and words.intersection({"file", "function", "code", "source", "this"}):
        return _confirmation_request("developer.patch_file")
    if re.search(r"\b(?:write|create)\b", text) and words.intersection({"file", "script", "module"}):
        return _confirmation_request("developer.write_file")
    if text in {"run test", "run tests", "run the test", "run the tests"} or (text.startswith("run ") and (words.intersection({"command", "pytest", "compileall", "py_compile"}) or (words.intersection({"test", "tests"}) and words.intersection({"brain", "unit", "python"})))):
        return _confirmation_request("developer.run_command")
    if any(p in text for p in ("developer request", "developer task", "developer work")):
        return DeveloperRequest(DEVELOPER_UNSUPPORTED)
    return None


def _registry_signature(capability_id: str) -> tuple[object, ...] | None:
    brain, tool = get_capability(capability_id), get_tool(capability_id)
    if brain is None or tool is None:
        return None
    return (brain.capability_id, brain.enabled, brain.executable, brain.read_only, brain.mutating, brain.requires_confirmation,
            tool.tool_id, tool.enabled, tool.executable, tool.read_only, tool.mutating, tool.requires_confirmation)


def _validate_executable_capability(capability_id: str) -> str | None:
    if capability_id not in PHASE1_EXECUTION_ALLOWLIST:
        return "capability_not_allowed"
    brain, tool = get_capability(capability_id), get_tool(capability_id)
    if brain is None or tool is None:
        return "capability_not_registered"
    if brain.capability_id != capability_id or tool.tool_id != capability_id:
        return "capability_metadata_mismatch"
    if not brain.enabled or not tool.enabled:
        return "capability_disabled"
    if not is_tool_dispatchable(capability_id):
        return "capability_not_dispatchable"
    if not brain.executable or not tool.executable:
        return "capability_not_executable"
    if not brain.read_only or not tool.read_only:
        return "capability_not_read_only"
    if brain.mutating or tool.mutating:
        return "capability_mutating"
    if brain.requires_confirmation or tool.requires_confirmation:
        return "confirmation_required"
    return None


def _validate_approval_capability(capability_id: str) -> str | None:
    if capability_id not in PHASE2_APPROVAL_ALLOWLIST:
        return "capability_not_allowed"
    brain, tool = get_capability(capability_id), get_tool(capability_id)
    if brain is None or tool is None:
        return "capability_not_registered"
    if brain.capability_id != capability_id or tool.tool_id != capability_id:
        return "capability_metadata_mismatch"
    if not brain.enabled or not tool.enabled:
        return "capability_disabled"
    if not is_tool_dispatchable(capability_id):
        return "capability_not_dispatchable"
    # Confirmation-gated tools deliberately remain non-autonomous.
    if brain.executable or tool.executable:
        return "capability_metadata_mismatch"
    if not brain.requires_confirmation or not tool.requires_confirmation:
        return "confirmation_metadata_mismatch"
    if brain.read_only != tool.read_only or brain.mutating != tool.mutating:
        return "capability_metadata_mismatch"
    if capability_id == "developer.gradle_test":
        if not brain.read_only or brain.mutating:
            return "capability_metadata_mismatch"
    elif brain.read_only or not brain.mutating:
        return "capability_metadata_mismatch"
    return None


def _validate_session_capability(capability_id: str) -> str | None:
    if capability_id not in PHASE3_SESSION_ALLOWLIST:
        return "capability_not_allowed"
    brain, tool = get_capability(capability_id), get_tool(capability_id)
    if brain is None or tool is None:
        return "capability_not_registered"
    if brain.capability_id != capability_id or tool.tool_id != capability_id:
        return "capability_metadata_mismatch"
    if not brain.enabled or not tool.enabled:
        return "capability_disabled"
    if brain.executable or tool.executable:
        return "capability_metadata_mismatch"
    if not brain.requires_confirmation or not tool.requires_confirmation:
        return "confirmation_metadata_mismatch"
    if brain.read_only or tool.read_only or not brain.mutating or not tool.mutating:
        return "capability_metadata_mismatch"
    if run_developer_session_request is not _CANONICAL_BOUNDED_SESSION_HANDLER:
        return "capability_not_dispatchable"
    return None


def _validate_greenfield_capability(capability_id: str) -> str | None:
    if capability_id not in PHASE5_GREENFIELD_ALLOWLIST:
        return "capability_not_allowed"
    brain, tool = get_capability(capability_id), get_tool(capability_id)
    if brain is None or tool is None:
        return "capability_not_registered"
    if brain.capability_id != capability_id or tool.tool_id != capability_id:
        return "capability_metadata_mismatch"
    if not brain.enabled or not tool.enabled:
        return "capability_disabled"
    if brain.executable or tool.executable or is_tool_dispatchable(capability_id):
        return "capability_metadata_mismatch"
    if not brain.requires_confirmation or not tool.requires_confirmation:
        return "confirmation_metadata_mismatch"
    if brain.read_only or tool.read_only or not brain.mutating or not tool.mutating:
        return "capability_metadata_mismatch"
    if run_greenfield_project is not _CANONICAL_GREENFIELD_HANDLER:
        return "capability_not_dispatchable"
    return None


def _workspace_fingerprint(workspace: Workspace) -> str:
    fingerprint, error = repository_state_fingerprint(workspace)
    if error or fingerprint is None:
        raise ValueError(error or "git_state_unavailable")
    return fingerprint


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(128 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_session_arguments(
    arguments: Mapping[str, object],
    workspace: Workspace,
) -> tuple[tuple[object, ...] | None, str | None]:
    if set(arguments) != {"request"}:
        return None, "invalid_arguments"
    request = arguments["request"]
    if type(request) is not DeveloperSessionRequest or request.approved is not False:
        return None, "invalid_request"
    if (
        request.max_repairs != MAX_SESSION_REPAIRS
        or request.max_verification_runs != MAX_SESSION_VERIFICATION_RUNS
        or request.max_proposal_requests != MAX_SESSION_PROPOSAL_REQUESTS
    ):
        return None, "invalid_session_limits"
    validation_error = validate_developer_session_request(
        request,
        workspace=workspace,
    )
    if validation_error:
        return None, validation_error
    spec = request.verification_spec
    if (
        request.verification_argv is not None
        or type(spec) is not VerificationSpec
    ):
        return None, "unsupported_verification"
    test_paths = tuple(
        path for path in request.candidate_files if _is_test_path(path)
    )
    if (
        len(request.candidate_files) != 2
        or len(request.allowed_mutation_paths) != 1
        or len(test_paths) != 1
        or request.allowed_mutation_paths != tuple(
            path for path in request.candidate_files if path not in test_paths
        )
    ):
        return None, "invalid_mutation_scope"
    if any(_is_test_path(path) for path in request.allowed_mutation_paths):
        return None, "test_mutation_not_allowed"
    source_path = request.allowed_mutation_paths[0]
    test_path = test_paths[0]
    if request.candidate_files != (source_path, test_path):
        return None, "invalid_mutation_scope"
    if spec.kind == "run_command":
        expected_argv = ("pytest", "-q", test_path)
        if (
            PurePath(source_path).suffix.casefold() != ".py"
            or PurePath(test_path).suffix.casefold() != ".py"
            or spec.project_path is not None
            or spec.argv != expected_argv
        ):
            return None, "unsupported_verification"
        approved_command = validate_command(spec.argv, workspace)
        if approved_command.family != "pytest":
            return None, "unsupported_verification"
    elif spec.kind == "gradle_test":
        if (
            PurePath(source_path).suffix.casefold() not in {".java", ".kt"}
            or PurePath(test_path).suffix.casefold() not in {".java", ".kt"}
            or spec.argv
            or spec.project_path is None
        ):
            return None, "unsupported_verification"
        validate_gradle_project(spec.project_path, workspace=workspace)
    else:
        return None, "unsupported_verification"

    files: list[tuple[object, ...]] = []
    for path in request.candidate_files:
        target = prepare_mutation_target(workspace, path, require_exists=True)
        _, data, snapshot = read_existing_text(workspace, target)
        files.append((target.relative_path, snapshot, _digest_bytes(data)))
    return (
        (
            "bounded_session",
            spec,
            request.candidate_files,
            request.allowed_mutation_paths,
            request.max_repairs,
            request.max_verification_runs,
            request.max_proposal_requests,
            tuple(files),
        ),
        None,
    )


def _validate_pending_arguments(capability_id: str, arguments: Mapping[str, object], workspace: Workspace) -> tuple[tuple[object, ...] | None, str | None]:
    try:
        if capability_id == "developer.greenfield_project":
            if set(arguments) != {"manifest"}:
                return None, "invalid_arguments"
            return validate_greenfield_manifest(arguments["manifest"]), None
        if capability_id == "developer.bounded_session":
            return _validate_session_arguments(arguments, workspace)
        if capability_id == "developer.write_file":
            if set(arguments) != {"path", "content"}:
                return None, "invalid_arguments"
            encoded = encode_text(arguments["content"], max_bytes=MAX_FILE_BYTES)
            target = prepare_mutation_target(workspace, arguments["path"])
            return (("write", target.relative_path, len(encoded)), None) if not target.existed else (None, "target_exists")
        if capability_id == "developer.patch_file":
            if set(arguments) != {"path", "old_text", "new_text"}:
                return None, "invalid_arguments"
            old_text, new_text = arguments["old_text"], arguments["new_text"]
            encode_text(old_text, max_bytes=MAX_PATCH_PAYLOAD_BYTES, allow_empty=False)
            encode_text(new_text, max_bytes=MAX_PATCH_PAYLOAD_BYTES)
            target = prepare_mutation_target(workspace, arguments["path"], require_exists=True)
            text, data, snapshot = read_existing_text(workspace, target)
            if text.count(old_text) != 1:
                return None, "match_mismatch"
            return ("patch", target.relative_path, snapshot, _digest_bytes(data)), None
        if capability_id == "developer.run_command":
            if set(arguments) != {"argv"}:
                return None, "invalid_arguments"
            approved = validate_command(arguments["argv"], workspace)
            return ("command", approved.requested_argv, approved.execution_argv), None
        if capability_id == "developer.gradle_test":
            if set(arguments) != {"project_path"}:
                return None, "invalid_arguments"
            project, policy, _ = validate_gradle_project(arguments["project_path"], workspace=workspace)
            return ("gradle", project, repr(policy)), None
        if capability_id == "developer.git_stage":
            if set(arguments) != {"paths"}:
                return None, "invalid_arguments"
            validated = validate_stage_paths(arguments["paths"], workspace)
            if isinstance(validated, ToolResult):
                return None, validated.error_code or "invalid_paths"
            error = validate_repository(workspace) or validate_no_external_clean_filters(workspace)
            if error:
                return None, error
            staged = inspect_staged(workspace)
            if not staged.valid:
                return None, staged.status
            if not set(staged.paths).issubset(set(validated)):
                return None, "staged_scope_mismatch"
            files = tuple((path, _file_digest(workspace.resolve_path(path))) for path in validated)
            return ("stage", validated, files, _workspace_fingerprint(workspace)), None
        if capability_id == "developer.git_commit":
            if set(arguments) != {"message", "verification_evidence"}:
                return None, "invalid_arguments"
            message = validate_commit_message(arguments["message"])
            if message is None:
                return None, "invalid_message"
            if not is_successful_verification(arguments["verification_evidence"]):
                return None, "verification_required"
            error = (
                validate_repository(workspace)
                or validate_no_external_clean_filters(workspace)
            )
            if error:
                return None, error
            staged = inspect_staged(workspace)
            if not staged.valid:
                return None, staged.status
            if staged.file_count == 0:
                return None, "no_staged_changes"
            return (
                "commit",
                message,
                tuple(staged.paths),
                _workspace_fingerprint(workspace),
            ), None
    except (CommandPolicyError, MutationError) as exc:
        return None, exc.code
    except Exception:
        return None, "validation_failed"
    return None, "capability_not_allowed"


def _adapt_tool_result(result: ToolResult) -> str:
    if result.success:
        if result.tool_name == "developer.read_file":
            return result.output or "The file is empty."
        if result.tool_name == "developer.list_files":
            return result.output or "No files were found in that directory."
        if result.tool_name == "developer.git_status":
            return result.output or "Git status is clean."
        return result.output or "Developer tool completed successfully."
    code = result.error_code or "tool_failed"
    return f"Developer tool request was refused safely ({code}): {result.output}"


def _adapt_session_result(
    result: DeveloperSessionResult,
    summary: tuple[str, ...],
    verification_kind: str,
) -> DeveloperBridgeResult:
    if type(result) is not DeveloperSessionResult:
        return _failure(
            "executed_failed",
            "developer.bounded_session",
            "invalid_session_result",
            summary,
            "Approved developer session",
        )
    paths = ", ".join(result.changed_paths) if result.changed_paths else "none"
    outcome = "passed" if result.success else "did not pass"
    response = (
        f"Bounded developer session {outcome}. Verification runs: "
        f"{result.verification_runs}. Repairs applied: {result.repairs_applied}. "
        f"Modified paths: {paths}. Final stop reason: {result.stopped_reason}. "
        "Git stage, commit, and push performed: no."
    )
    if result.success:
        status = "executed_success"
    elif result.status in {"repair_limit", "verification_limit"}:
        status = result.status
    elif result.status in {
        "model_failure",
        "invalid_model_output",
        "invalid_proposal",
        "invalid_proposal_result",
        "proposal_request_limit",
        "proposal_conversion_failed",
        "stale_or_invalid_proposal",
        "low_confidence",
        "below_confidence_threshold",
        "no_fix",
        "path_not_a_candidate",
        "protected_candidate_path",
        "unsafe_candidate_symlink",
        "invalid_patch_payload",
        "invalid_write_payload",
        "patch_match_not_unique",
    }:
        status = "proposal_failed"
    else:
        status = "executed_failed"
    return DeveloperBridgeResult(
        status,
        "developer.bounded_session",
        response,
        summary,
        True,
        result.success,
        None if result.success else result.stopped_reason,
        "pytest" if verification_kind == "run_command" else verification_kind,
        result.repairs_applied,
        result.verification_runs,
        result.status,
    )


def _adapt_greenfield_result(
    result: GreenfieldProjectResult,
    summary: tuple[str, ...],
) -> DeveloperBridgeResult:
    if type(result) is not GreenfieldProjectResult:
        return _failure(
            "executed_failed",
            "developer.greenfield_project",
            "invalid_greenfield_result",
            summary,
            "Approved greenfield project",
        )
    created = ", ".join(result.created_files) if result.created_files else "none"
    changed = ", ".join(result.changed_paths) if result.changed_paths else "none"
    outcome = "passed" if result.success else "did not pass"
    response = (
        f"Greenfield project {outcome}. Project: {result.workspace}. "
        f"Files created: {created}. Verification runs: {result.verification_runs}. "
        f"Repairs applied: {result.repairs_applied}. Repair-modified paths: {changed}. "
        f"Final stop reason: {result.stopped_reason}. Git initialized, staged, committed, "
        "or pushed: no."
    )
    if not result.success and result.directory_created:
        response += " The created directory and any project files were retained for inspection; no rollback was attempted."
    return DeveloperBridgeResult(
        "executed_success" if result.success else result.status,
        "developer.greenfield_project",
        response,
        summary,
        True,
        result.success,
        result.error_code,
        "pytest",
        result.repairs_applied,
        result.verification_runs,
        result.status,
    )


def _clear_pending() -> int:
    global _pending_action, _state_generation
    with _state_lock:
        _pending_action = None
        _state_generation += 1
        return _state_generation


def reset_developer_approval_state() -> None:
    """Clear process-local continuation state (used by lifecycle tests)."""
    global _pending_action, _verification_record, _state_generation
    with _state_lock:
        _pending_action = None
        _verification_record = None
        _state_generation += 1


def _payload_size(arguments: Mapping[str, object]) -> int:
    return sum(len(str(key).encode()) + len(str(value).encode()) for key, value in arguments.items())


def _failure(status: str, capability_id: str | None, code: str, summary: tuple[str, ...], prefix: str = "Developer request") -> DeveloperBridgeResult:
    return DeveloperBridgeResult(status, capability_id, f"{prefix} was refused safely ({code}); nothing was executed.", summary, error_code=code)


def _propose_action(request: DeveloperRequest) -> DeveloperBridgeResult:
    global _pending_action
    generation = _clear_pending()
    capability_id = request.capability_id or "developer.unknown"
    if (
        capability_id not in PHASE2_APPROVAL_ALLOWLIST
        and capability_id not in PHASE3_SESSION_ALLOWLIST
        and capability_id not in PHASE5_GREENFIELD_ALLOWLIST
    ) or not request.arguments:
        return DeveloperBridgeResult(DEVELOPER_CONFIRMATION_REQUIRED, request.capability_id,
            f"Developer request recognized for {capability_id}. The action is not fully specified or is not approval-executable, so nothing was executed and no approval is pending.", request.safe_argument_summary)
    if _payload_size(request.arguments) > MAX_PENDING_PAYLOAD_BYTES:
        return _failure("validation_failed", capability_id, "pending_payload_too_large", request.safe_argument_summary)
    error = (
        _validate_greenfield_capability(capability_id)
        if capability_id in PHASE5_GREENFIELD_ALLOWLIST
        else (
            _validate_session_capability(capability_id)
            if capability_id in PHASE3_SESSION_ALLOWLIST
            else _validate_approval_capability(capability_id)
        )
    )
    signature = _registry_signature(capability_id)
    if error or signature is None:
        return _failure("policy_blocked", capability_id, error or "capability_not_registered", request.safe_argument_summary)
    if capability_id in PHASE5_GREENFIELD_ALLOWLIST:
        if set(request.arguments) != {"request"}:
            return _failure(
                "validation_failed",
                capability_id,
                "invalid_arguments",
                request.safe_argument_summary,
            )
        try:
            manifest = prepare_greenfield_manifest(request.arguments["request"])
            arguments = {"manifest": manifest}
            if _payload_size(arguments) > MAX_PENDING_PAYLOAD_BYTES:
                raise GreenfieldProjectError("pending_payload_too_large")
            seal = validate_greenfield_manifest(manifest)
        except GreenfieldProjectError as exc:
            return _failure(
                "validation_failed",
                capability_id,
                exc.code,
                request.safe_argument_summary,
            )
        except Exception:
            return _failure(
                "validation_failed",
                capability_id,
                "greenfield_preparation_failed",
                request.safe_argument_summary,
            )
        pending = PendingDeveloperAction(
            capability_id,
            arguments,
            request.safe_argument_summary,
            time.monotonic(),
            Path(manifest.workspace).parent,
            signature,
            seal,
        )
        with _state_lock:
            if _state_generation != generation:
                return _failure(
                    "rejected",
                    capability_id,
                    "request_superseded",
                    request.safe_argument_summary,
                )
            _pending_action = pending
        summary = ", ".join(request.safe_argument_summary)
        return DeveloperBridgeResult(
            DEVELOPER_CONFIRMATION_REQUIRED,
            capability_id,
            f"Confirmation required for {capability_id} ({summary}). Reply exactly "
            "'approve' to create and verify this one exact project, or 'cancel'. "
            "Nothing was created or executed.",
            request.safe_argument_summary,
        )
    try:
        workspace = Workspace()
    except Exception:
        return _failure(
            "validation_failed",
            capability_id,
            "workspace_unavailable",
            request.safe_argument_summary,
        )
    arguments = dict(request.arguments)
    if capability_id == "developer.git_commit":
        with _state_lock:
            verification = _verification_record
        try:
            current_fingerprint = _workspace_fingerprint(workspace)
        except ValueError:
            current_fingerprint = ""
        if verification is None or verification.workspace_root != workspace.root or verification.workspace_fingerprint != current_fingerprint:
            return _failure("validation_failed", capability_id, "verification_required", request.safe_argument_summary)
        arguments["verification_evidence"] = verification.evidence
    seal, error = _validate_pending_arguments(capability_id, arguments, workspace)
    if error or seal is None:
        return _failure("validation_failed", capability_id, error or "validation_failed", request.safe_argument_summary)
    pending = PendingDeveloperAction(capability_id, arguments, request.safe_argument_summary, time.monotonic(), workspace.root, signature, seal)
    with _state_lock:
        if _state_generation != generation:
            return _failure("rejected", capability_id, "request_superseded", request.safe_argument_summary)
        _pending_action = pending
    if capability_id == "developer.bounded_session":
        session_request = request.arguments["request"]
        source = session_request.allowed_mutation_paths[0]
        test = tuple(
            path
            for path in session_request.candidate_files
            if path not in session_request.allowed_mutation_paths
        )[0]
        verification_kind = session_request.verification_spec.kind
        verification_label = (
            "pytest" if verification_kind == "run_command" else verification_kind
        )
        summary = (
            f"source={source}, test={test}, verification={verification_label}, "
            f"repairs<={MAX_SESSION_REPAIRS}, verifications<="
            f"{MAX_SESSION_VERIFICATION_RUNS}"
        )
    else:
        summary = ", ".join(request.safe_argument_summary) or "validated arguments"
    return DeveloperBridgeResult(DEVELOPER_CONFIRMATION_REQUIRED, capability_id,
        f"Confirmation required for {capability_id} ({summary}). Reply exactly 'approve' to attempt this one action, or 'cancel'. Nothing was executed.", request.safe_argument_summary)


def _cancel_action() -> DeveloperBridgeResult:
    global _pending_action, _state_generation
    with _state_lock:
        pending, _pending_action = _pending_action, None
        _state_generation += 1
    return DeveloperBridgeResult("cancelled", pending.capability_id if pending else None,
        "Pending developer action cancelled; nothing was executed." if pending else "There is no pending developer action to cancel; nothing was executed.",
        pending.safe_argument_summary if pending else ())


def _approve_action() -> DeveloperBridgeResult:
    global _pending_action, _verification_record, _state_generation
    with _state_lock:
        pending, _pending_action = _pending_action, None
        _state_generation += 1
        approval_generation = _state_generation
    if pending is None:
        return _failure("rejected", None, "no_pending_action", ())
    if time.monotonic() - pending.created_at > PENDING_ACTION_TTL_SECONDS:
        return _failure("expired", pending.capability_id, "pending_action_expired", pending.safe_argument_summary, "Pending developer action")
    error = (
        _validate_greenfield_capability(pending.capability_id)
        if pending.capability_id in PHASE5_GREENFIELD_ALLOWLIST
        else (
            _validate_session_capability(pending.capability_id)
            if pending.capability_id in PHASE3_SESSION_ALLOWLIST
            else _validate_approval_capability(pending.capability_id)
        )
    )
    signature = _registry_signature(pending.capability_id)
    if error or signature != pending.registry_signature:
        return _failure("policy_blocked", pending.capability_id, error or "capability_metadata_changed", pending.safe_argument_summary, "Approved developer action")
    if pending.capability_id in PHASE5_GREENFIELD_ALLOWLIST:
        if set(pending.arguments) != {"manifest"}:
            return _failure(
                "validation_failed",
                pending.capability_id,
                "invalid_arguments",
                pending.safe_argument_summary,
                "Approved greenfield project",
            )
        manifest = pending.arguments["manifest"]
        try:
            seal = validate_greenfield_manifest(manifest)
        except GreenfieldProjectError as exc:
            return _failure(
                "validation_failed",
                pending.capability_id,
                exc.code,
                pending.safe_argument_summary,
                "Approved greenfield project",
            )
        except Exception:
            return _failure(
                "validation_failed",
                pending.capability_id,
                "greenfield_revalidation_failed",
                pending.safe_argument_summary,
                "Approved greenfield project",
            )
        if (
            seal != pending.validation_seal
            or Path(manifest.workspace).parent != pending.workspace_root
        ):
            return _failure(
                "validation_failed",
                pending.capability_id,
                "validation_state_changed",
                pending.safe_argument_summary,
                "Approved greenfield project",
            )
        try:
            result = run_greenfield_project(manifest)
        except GreenfieldProjectError as exc:
            return _failure(
                "validation_failed",
                pending.capability_id,
                exc.code,
                pending.safe_argument_summary,
                "Approved greenfield project",
            )
        except Exception:
            result = GreenfieldProjectResult(
                False,
                "unexpected_greenfield_failure",
                manifest.workspace,
                False,
                (),
                0,
                0,
                (),
                "unexpected_greenfield_failure",
                "unexpected_greenfield_failure",
            )
        with _state_lock:
            if _state_generation == approval_generation:
                _verification_record = None
        return _adapt_greenfield_result(result, pending.safe_argument_summary)
    try:
        workspace = Workspace()
    except Exception:
        return _failure(
            "validation_failed",
            pending.capability_id,
            "workspace_unavailable",
            pending.safe_argument_summary,
            "Approved developer action",
        )
    if workspace.root != pending.workspace_root:
        return _failure("validation_failed", pending.capability_id, "workspace_changed", pending.safe_argument_summary, "Approved developer action")
    seal, error = _validate_pending_arguments(pending.capability_id, pending.arguments, workspace)
    if error or seal != pending.validation_seal:
        return _failure("validation_failed", pending.capability_id, error or "validation_state_changed", pending.safe_argument_summary, "Approved developer action")
    arguments = dict(pending.arguments)
    if pending.capability_id == "developer.bounded_session":
        request = arguments["request"]
        try:
            result = run_developer_session_request(
                replace(request, approved=True),
                workspace=workspace,
            )
        except Exception:
            result = DeveloperSessionResult(
                False,
                "unexpected_session_failure",
                0,
                0,
                0,
                (),
                (),
                "unexpected_session_failure",
            )
        with _state_lock:
            if _state_generation == approval_generation:
                _verification_record = None
        return _adapt_session_result(
            result,
            pending.safe_argument_summary,
            request.verification_spec.kind,
        )
    if pending.capability_id in {"developer.gradle_test", "developer.git_stage", "developer.git_commit"}:
        arguments["approved"] = True
    result = execute_tool(pending.capability_id, arguments, workspace=workspace)
    if pending.capability_id in {"developer.run_command", "developer.gradle_test"}:
        evidence = VerificationEvidence.from_tool_result(result)
        try:
            fingerprint = _workspace_fingerprint(workspace) if is_successful_verification(evidence) else ""
        except ValueError:
            fingerprint = ""
        with _state_lock:
            if _state_generation == approval_generation:
                _verification_record = (
                    _VerificationRecord(evidence, workspace.root, fingerprint)
                    if fingerprint
                    else None
                )
    elif pending.capability_id != "developer.git_commit":
        with _state_lock:
            if _state_generation == approval_generation:
                _verification_record = None
    return DeveloperBridgeResult("executed" if result.success else "rejected", pending.capability_id,
        _adapt_tool_result(result), pending.safe_argument_summary, True, result.success, result.error_code)


def execute_developer_request(request: DeveloperRequest) -> DeveloperBridgeResult:
    """Execute one direct read or manage one explicit approval continuation."""
    if request.mode == DEVELOPER_APPROVAL:
        return _approve_action()
    if request.mode == DEVELOPER_CANCELLATION:
        return _cancel_action()
    if request.mode == DEVELOPER_CONFIRMATION_REQUIRED:
        return _propose_action(request)
    _clear_pending()
    if request.mode != DEVELOPER_EXECUTABLE or not request.capability_id:
        return DeveloperBridgeResult(DEVELOPER_UNSUPPORTED, request.capability_id,
            "That developer request is ambiguous or unsupported. Nothing was executed.", request.safe_argument_summary,
            error_code="unsupported_developer_request")
    error = _validate_executable_capability(request.capability_id)
    if error:
        return _failure("rejected", request.capability_id, error, request.safe_argument_summary)
    result = execute_tool(request.capability_id, request.arguments)
    return DeveloperBridgeResult("executed" if result.success else "rejected", request.capability_id,
        _adapt_tool_result(result), request.safe_argument_summary, True, result.success, result.error_code)


def invalidate_pending_developer_action() -> None:
    """Cancel latent mutation authority after unrelated conversation."""
    _clear_pending()
