"""Fixed internal Git operations for controlled local checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import threading

from core.developer_agent.command_policy import SAFE_SYSTEM_PATH
from core.developer_agent.policy import git_protection_code
from core.developer_agent.workspace import Workspace


GIT_TIMEOUT_SECONDS = 15
GIT_COMMIT_TIMEOUT_SECONDS = 30
MAX_GIT_OUTPUT_BYTES = 256 * 1024
_SAFE_STAGED_STATUSES = frozenset({"A", "M"})
_SHA_PATTERN = re.compile(r"[0-9a-f]{40,64}")
_SAFE_INDEX_ENTRY = re.compile(rb"(100644|100755) [0-9a-f]{40,64} 0\t(.+)")
_READ_CHUNK_BYTES = 8192


@dataclass(frozen=True)
class FixedGitResult:
    status: str
    returncode: int | None
    stdout: bytes


@dataclass(frozen=True)
class StagedInspection:
    valid: bool
    status: str
    paths: tuple[str, ...]

    @property
    def file_count(self) -> int:
        return len(self.paths)


def _safe_environment(workspace: Workspace) -> dict[str, str]:
    return {
        "GIT_ASKPASS": "/bin/false",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_EDITOR": "/bin/false",
        "GIT_LITERAL_PATHSPECS": "1",
        "GIT_MERGE_AUTOEDIT": "no",
        "GIT_PAGER": "cat",
        "GIT_SEQUENCE_EDITOR": "/bin/false",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": str(workspace.root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PAGER": "cat",
        "PATH": SAFE_SYSTEM_PATH,
    }


def _git_executable() -> str | None:
    executable = shutil.which("git", path=SAFE_SYSTEM_PATH)
    if executable is None:
        return None
    try:
        resolved = Path(executable).resolve(strict=True)
    except OSError:
        return None
    return str(resolved) if resolved.is_file() else None


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        pass


def _read_bounded(
    stream,
    process: subprocess.Popen[bytes],
    captured: bytearray,
    exceeded: threading.Event,
) -> None:
    try:
        while True:
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                return
            remaining = MAX_GIT_OUTPUT_BYTES - len(captured)
            captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                exceeded.set()
                _terminate(process)
                return
    except (OSError, ValueError):
        return
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _run_fixed(
    workspace: Workspace,
    arguments: tuple[str, ...],
    *,
    timeout_seconds: int = GIT_TIMEOUT_SECONDS,
) -> FixedGitResult:
    executable = _git_executable()
    if executable is None:
        return FixedGitResult("git_unavailable", None, b"")
    command = (
        executable,
        "--no-pager",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "diff.external=",
        *arguments,
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=workspace.root,
            env=_safe_environment(workspace),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=os.name == "posix",
        )
    except (OSError, subprocess.SubprocessError):
        return FixedGitResult("git_unavailable", None, b"")
    if process.stdout is None:
        _terminate(process)
        return FixedGitResult("git_unavailable", None, b"")

    captured = bytearray()
    exceeded = threading.Event()
    reader = threading.Thread(
        target=_read_bounded,
        args=(process.stdout, process, captured, exceeded),
        daemon=True,
    )
    try:
        reader.start()
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate(process)
        process.wait()
        reader.join(timeout=1)
        return FixedGitResult("timeout", process.returncode, b"")
    except (OSError, subprocess.SubprocessError, RuntimeError):
        _terminate(process)
        try:
            process.wait(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass
        return FixedGitResult("git_unavailable", process.returncode, b"")
    reader.join(timeout=1)
    if reader.is_alive():
        _terminate(process)
        return FixedGitResult("git_unavailable", process.returncode, b"")
    if exceeded.is_set():
        return FixedGitResult("output_too_large", process.returncode, b"")
    return FixedGitResult("ok", process.returncode, bytes(captured))


def validate_repository(workspace: Workspace) -> str | None:
    result = _run_fixed(workspace, ("rev-parse", "--show-toplevel"))
    if result.status != "ok" or result.returncode != 0:
        return "invalid_repository"
    try:
        top_level = Path(result.stdout.decode("utf-8", errors="strict").strip()).resolve(
            strict=True
        )
    except (UnicodeDecodeError, OSError):
        return "invalid_repository"
    return None if top_level == workspace.root else "invalid_repository"


def validate_no_external_clean_filters(workspace: Workspace) -> str | None:
    result = _run_fixed(
        workspace,
        (
            "config",
            "--local",
            "--includes",
            "--get-regexp",
            r"^filter\..*\.(clean|process)$",
        ),
    )
    if result.status != "ok":
        return "git_policy_check_failed"
    if result.returncode == 1:
        return None
    if result.returncode == 0:
        return "external_filter_not_allowed"
    return "git_policy_check_failed"


def _parse_staged_names(output: bytes) -> StagedInspection:
    fields = output.split(b"\x00")
    if fields and fields[-1] == b"":
        fields.pop()
    paths: list[str] = []
    index = 0
    while index < len(fields):
        try:
            status = fields[index].decode("ascii", errors="strict")
        except UnicodeDecodeError:
            return StagedInspection(False, "unsupported_staged_status", ())
        index += 1
        if status not in _SAFE_STAGED_STATUSES or index >= len(fields):
            return StagedInspection(False, "unsupported_staged_status", ())
        try:
            path = fields[index].decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return StagedInspection(False, "invalid_staged_path", ())
        index += 1
        path_object = Path(path)
        if (
            not path
            or "\x00" in path
            or path_object.is_absolute()
            or ".." in path_object.parts
            or git_protection_code(path_object) is not None
        ):
            return StagedInspection(False, "protected_staged_path", ())
        paths.append(path)
    if len(paths) != len(set(paths)):
        return StagedInspection(False, "invalid_staged_path", ())
    return StagedInspection(True, "staged_diff_valid", tuple(paths))


def _validate_staged_modes(workspace: Workspace, paths: tuple[str, ...]) -> str | None:
    if not paths:
        return None
    result = _run_fixed(workspace, ("ls-files", "--stage", "-z", "--", *paths))
    if result.status != "ok" or result.returncode != 0:
        return "staged_inspection_failed"
    entries = result.stdout.split(b"\x00")
    if entries and entries[-1] == b"":
        entries.pop()
    seen: set[str] = set()
    for entry in entries:
        matched = _SAFE_INDEX_ENTRY.fullmatch(entry)
        if matched is None:
            return "unsupported_staged_mode"
        try:
            path = matched.group(2).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return "invalid_staged_path"
        if path not in paths or path in seen:
            return "invalid_staged_path"
        seen.add(path)
    return None if seen == set(paths) else "invalid_staged_path"


def inspect_staged(workspace: Workspace) -> StagedInspection:
    whitespace = _run_fixed(
        workspace,
        (
            "diff",
            "--cached",
            "--check",
            "--no-ext-diff",
            "--no-textconv",
        ),
    )
    if whitespace.status != "ok":
        return StagedInspection(False, whitespace.status, ())
    if whitespace.returncode != 0:
        return StagedInspection(False, "cached_diff_check_failed", ())

    names = _run_fixed(
        workspace,
        (
            "diff",
            "--cached",
            "--name-status",
            "-z",
            "--no-ext-diff",
            "--no-textconv",
        ),
    )
    if names.status != "ok" or names.returncode != 0:
        return StagedInspection(False, "staged_inspection_failed", ())
    inspection = _parse_staged_names(names.stdout)
    if not inspection.valid:
        return inspection
    mode_error = _validate_staged_modes(workspace, inspection.paths)
    if mode_error is not None:
        return StagedInspection(False, mode_error, ())
    return inspection


def stage_paths(workspace: Workspace, paths: tuple[str, ...]) -> str | None:
    result = _run_fixed(workspace, ("add", "--", *paths))
    if result.status != "ok":
        return result.status
    return None if result.returncode == 0 else "git_stage_failed"


def current_branch(workspace: Workspace) -> tuple[str | None, str | None]:
    result = _run_fixed(workspace, ("symbolic-ref", "--quiet", "--short", "HEAD"))
    if result.status != "ok" or result.returncode != 0:
        return None, "detached_head"
    try:
        branch = result.stdout.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        return None, "invalid_branch"
    return (branch, None) if branch else (None, "invalid_branch")


def create_commit(workspace: Workspace, message: str) -> str | None:
    result = _run_fixed(
        workspace,
        (
            "commit",
            "--no-verify",
            "--no-gpg-sign",
            "-m",
            message,
        ),
        timeout_seconds=GIT_COMMIT_TIMEOUT_SECONDS,
    )
    if result.status != "ok":
        return result.status
    return None if result.returncode == 0 else "git_commit_failed"


def current_commit_sha(workspace: Workspace) -> tuple[str | None, str | None]:
    result = _run_fixed(workspace, ("rev-parse", "HEAD"))
    if result.status != "ok" or result.returncode != 0:
        return None, "commit_sha_unavailable"
    try:
        sha = result.stdout.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError:
        return None, "commit_sha_unavailable"
    return (sha, None) if _SHA_PATTERN.fullmatch(sha) else (None, "commit_sha_unavailable")
