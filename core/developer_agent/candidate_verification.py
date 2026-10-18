"""Disposable, namespace-isolated verification for bounded Python repairs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile

from core.developer_agent.command_policy import CommandPolicyError, validate_command
from core.developer_agent.executor import execute_tool
from core.developer_agent.mutation import (
    FileSnapshot,
    MutationError,
    atomic_write_text,
    prepare_mutation_target,
    read_existing_text,
)
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.tools.run_command import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    _execute_fixed_argv,
)
from core.developer_agent.workspace import Workspace, WorkspacePathError


BWRAP_PATH = Path("/usr/bin/bwrap")
SANDBOX_HOME = "/tmp/home"
SANDBOX_PYCACHE = "/tmp/pycache"
SANDBOX_SITE_PACKAGES = Path("/opt/jarvis-site-packages")
READELF_PATH = Path("/usr/bin/readelf")
_NEEDED_LIBRARY_PATTERN = re.compile(r"Shared library: \[([^\]]+)\]")
_MAX_READELF_OUTPUT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class WorkspaceIdentity:
    root: Path
    device: int
    inode: int


@dataclass(frozen=True)
class FileBaseline:
    path: str
    exists: bool
    device: int | None
    inode: int | None
    size: int | None
    modified_ns: int | None
    mode: int | None
    sha256: str | None
    content: bytes | None = field(repr=False)


@dataclass(frozen=True)
class SessionBaseline:
    workspace: WorkspaceIdentity
    files: tuple[FileBaseline, ...]

    def file(self, path: str) -> FileBaseline | None:
        return next((item for item in self.files if item.path == path), None)


@dataclass(frozen=True)
class SealedCandidate:
    path: str
    content: bytes = field(repr=False)
    sha256: str
    size: int


@dataclass(frozen=True)
class CandidateVerification:
    status: str
    verification: ToolResult | None
    sealed_candidate: SealedCandidate | None
    mutation_status: str | None
    cleanup_succeeded: bool


class CandidateIsolationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_snapshot_tuple(snapshot: FileSnapshot) -> tuple[int, int, int, int, int]:
    return (
        snapshot.device,
        snapshot.inode,
        snapshot.size,
        snapshot.modified_ns,
        snapshot.mode,
    )


def _baseline_snapshot_tuple(
    baseline: FileBaseline,
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    return (
        baseline.device,
        baseline.inode,
        baseline.size,
        baseline.modified_ns,
        baseline.mode,
    )


def capture_session_baseline(
    workspace: Workspace,
    paths: tuple[str, ...],
) -> SessionBaseline:
    """Capture exact approved-file identities without following unsafe targets."""

    root_stat = workspace.root.stat()
    files: list[FileBaseline] = []
    for path in paths:
        try:
            target = prepare_mutation_target(workspace, path)
            if target.existed:
                _, content, snapshot = read_existing_text(workspace, target)
                files.append(FileBaseline(
                    path,
                    True,
                    snapshot.device,
                    snapshot.inode,
                    snapshot.size,
                    snapshot.modified_ns,
                    snapshot.mode,
                    _sha256(content),
                    content,
                ))
            else:
                files.append(FileBaseline(
                    path,
                    False,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ))
        except (MutationError, OSError) as exc:
            code = exc.code if isinstance(exc, MutationError) else "baseline_unavailable"
            raise CandidateIsolationError(code) from None
    return SessionBaseline(
        WorkspaceIdentity(workspace.root, root_stat.st_dev, root_stat.st_ino),
        tuple(files),
    )


def validate_session_baseline(
    workspace: Workspace,
    baseline: SessionBaseline,
) -> str | None:
    """Return a safe reason if any approved original identity has changed."""

    try:
        root_stat = workspace.root.stat()
        if (
            workspace.root != baseline.workspace.root
            or root_stat.st_dev != baseline.workspace.device
            or root_stat.st_ino != baseline.workspace.inode
        ):
            return "workspace_identity_changed"
        for expected in baseline.files:
            target = prepare_mutation_target(workspace, expected.path)
            if target.existed != expected.exists:
                return "approved_file_changed"
            if not target.existed:
                continue
            _, content, snapshot = read_existing_text(workspace, target)
            if (
                _file_snapshot_tuple(snapshot) != _baseline_snapshot_tuple(expected)
                or _sha256(content) != expected.sha256
            ):
                return "approved_file_changed"
    except (MutationError, OSError, ValueError):
        return "approved_file_changed"
    return None


def _copy_baseline(candidate_root: Path, baseline: SessionBaseline) -> None:
    for item in baseline.files:
        destination = candidate_root / item.path
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not item.exists:
            continue
        if item.content is None or item.mode is None:
            raise CandidateIsolationError("baseline_unavailable")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(destination, flags, item.mode)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(item.content)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def _runtime_venv() -> Path:
    prefix = Path(sys.prefix).resolve(strict=True)
    executable = Path(sys.executable).resolve(strict=True)
    if (
        prefix == Path(sys.base_prefix).resolve(strict=True)
        or not prefix.is_dir()
        or not executable.is_file()
        or not (prefix / "bin/python").exists()
    ):
        raise CandidateIsolationError("candidate_runtime_unavailable")
    return prefix


def _runtime_site_packages(runtime: Path) -> Path:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    try:
        site_packages = (runtime / "lib" / version / "site-packages").resolve(
            strict=True
        )
    except OSError:
        raise CandidateIsolationError("candidate_runtime_unavailable") from None
    if not site_packages.is_dir() or not site_packages.is_relative_to(runtime):
        raise CandidateIsolationError("candidate_runtime_unavailable")
    return site_packages


def _system_runtime_roots() -> tuple[Path, Path, str]:
    multiarch = sysconfig.get_config_var("MULTIARCH")
    stdlib_value = sysconfig.get_path("stdlib")
    if not isinstance(multiarch, str) or not multiarch:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    if not isinstance(stdlib_value, str) or not stdlib_value:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    try:
        shared_libraries = (Path("/usr/lib") / multiarch).resolve(strict=True)
        standard_library = Path(stdlib_value).resolve(strict=True)
    except OSError:
        raise CandidateIsolationError("candidate_runtime_unavailable") from None
    if (
        not shared_libraries.is_dir()
        or shared_libraries.parent != Path("/usr/lib")
        or not standard_library.is_dir()
        or standard_library.parent != Path("/usr/lib")
    ):
        raise CandidateIsolationError("candidate_runtime_unavailable")
    loader_links = tuple(Path("/usr/lib").glob("ld-linux-*.so.*"))
    if len(loader_links) != 1:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    loader_link = loader_links[0]
    try:
        loader_target = loader_link.resolve(strict=True)
    except OSError:
        raise CandidateIsolationError("candidate_runtime_unavailable") from None
    if not loader_target.is_file() or loader_target.parent != shared_libraries:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    return shared_libraries, standard_library, loader_link.name


def _trusted_executable(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
        file_stat = resolved.stat()
    except OSError:
        raise CandidateIsolationError("candidate_runtime_unavailable") from None
    if (
        not resolved.is_file()
        or not os.access(resolved, os.X_OK)
        or file_stat.st_uid != 0
        or bool(file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    ):
        raise CandidateIsolationError("candidate_runtime_unavailable")
    return resolved


def _needed_library_names(paths: tuple[Path, ...]) -> set[str]:
    if not paths:
        return set()
    readelf = _trusted_executable(READELF_PATH)
    try:
        completed = subprocess.run(
            (str(readelf), "-dW", *(str(path) for path in paths)),
            cwd="/",
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise CandidateIsolationError("candidate_runtime_unavailable") from None
    if len(completed.stdout) > _MAX_READELF_OUTPUT_BYTES:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    output = completed.stdout.decode("utf-8", errors="replace")
    return set(_NEEDED_LIBRARY_PATTERN.findall(output))


@lru_cache(maxsize=1)
def _system_library_bindings(
    runtime: Path,
    shared_libraries: Path,
    standard_library: Path,
    base_python: Path,
) -> tuple[tuple[Path, Path], ...]:
    extension_roots = tuple(sorted(
        {
            path.resolve(strict=True)
            for root in (standard_library, runtime)
            for pattern in ("*.so", "*.so.*")
            for path in root.rglob(pattern)
            if path.is_file()
        },
        key=str,
    ))
    pending = _needed_library_names((base_python, *extension_roots))
    bindings: dict[Path, Path] = {}
    inspected: set[Path] = set()
    while pending:
        name = pending.pop()
        if Path(name).name != name:
            raise CandidateIsolationError("candidate_runtime_unavailable")
        destination = shared_libraries / name
        try:
            source = destination.resolve(strict=True)
        except OSError:
            # Private wheel libraries remain reachable inside the mounted venv.
            continue
        if not source.is_file() or not source.is_relative_to(shared_libraries):
            raise CandidateIsolationError("candidate_runtime_unavailable")
        bindings[destination] = source
        if source not in inspected:
            inspected.add(source)
            pending.update(_needed_library_names((source,)))
    if not bindings:
        raise CandidateIsolationError("candidate_runtime_unavailable")
    return tuple(sorted(
        ((source, destination) for destination, source in bindings.items()),
        key=lambda item: str(item[1]),
    ))


def _validate_bwrap() -> Path:
    try:
        resolved = BWRAP_PATH.resolve(strict=True)
        file_stat = resolved.stat()
    except OSError:
        raise CandidateIsolationError("candidate_isolation_unavailable") from None
    if (
        not resolved.is_file()
        or not os.access(resolved, os.X_OK)
        or file_stat.st_uid != 0
        or bool(file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH))
    ):
        raise CandidateIsolationError("candidate_isolation_unavailable")
    return resolved


def _sandbox_argv(
    candidate_root: Path,
    verification_argv: tuple[str, ...],
    workspace: Workspace,
) -> tuple[str, ...]:
    try:
        approved = validate_command(verification_argv, workspace)
    except CommandPolicyError as exc:
        raise CandidateIsolationError(exc.code) from None
    if approved.family != "pytest":
        raise CandidateIsolationError("candidate_verification_not_supported")

    bwrap = _validate_bwrap()
    runtime = _runtime_venv()
    site_packages = _runtime_site_packages(runtime)
    shared_libraries, standard_library, loader_name = _system_runtime_roots()
    base_python = Path(sys.executable).resolve(strict=True)
    if base_python.parent != Path("/usr/bin"):
        raise CandidateIsolationError("candidate_runtime_unavailable")
    library_bindings = _system_library_bindings(
        runtime,
        shared_libraries,
        standard_library,
        base_python,
    )
    requested = approved.requested_argv
    if requested[0] == "pytest":
        pytest_arguments = requested[1:]
    elif (
        len(requested) >= 3
        and requested[0] in {"python", "python3"}
        and requested[1:3] == ("-m", "pytest")
    ):
        pytest_arguments = requested[3:]
    else:
        raise CandidateIsolationError("candidate_verification_not_supported")

    return (
        str(bwrap),
        "--unshare-user",
        "--unshare-ipc",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-uts",
        "--unshare-cgroup-try",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
        "--dir",
        "/usr",
        "--dir",
        "/usr/lib",
        "--dir",
        str(shared_libraries),
        "--dir",
        str(standard_library),
        "--symlink",
        f"{shared_libraries.name}/{loader_name}",
        f"/usr/lib/{loader_name}",
        *(
            value
            for source, destination in library_bindings
            for value in ("--ro-bind", str(source), str(destination))
        ),
        "--ro-bind",
        str(standard_library),
        str(standard_library),
        "--dir",
        "/usr/bin",
        "--ro-bind",
        str(base_python),
        str(base_python),
        "--symlink",
        base_python.name,
        "/usr/bin/python3",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        SANDBOX_HOME,
        "--dir",
        SANDBOX_PYCACHE,
        "--dir",
        "/opt",
        "--ro-bind",
        str(site_packages),
        str(SANDBOX_SITE_PACKAGES),
        "--dir",
        "/workspace",
        "--ro-bind",
        str(candidate_root),
        "/workspace",
        "--chdir",
        "/workspace",
        "--setenv",
        "HOME",
        SANDBOX_HOME,
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "LC_ALL",
        "C.UTF-8",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "1",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--setenv",
        "PYTHONNOUSERSITE",
        "1",
        "--setenv",
        "PYTHONPATH",
        str(SANDBOX_SITE_PACKAGES),
        "--setenv",
        "PYTHONSAFEPATH",
        "1",
        "--setenv",
        "PYTHONPYCACHEPREFIX",
        SANDBOX_PYCACHE,
        "--",
        str(base_python),
        "-m",
        "pytest",
        "-c",
        "/dev/null",
        "--rootdir=/workspace",
        "--confcutdir=/workspace",
        "-p",
        "no:cacheprovider",
        *pytest_arguments,
    )


def _run_isolated_pytest(
    candidate_root: Path,
    verification_argv: tuple[str, ...],
    workspace: Workspace,
) -> ToolResult:
    argv = _sandbox_argv(candidate_root, verification_argv, workspace)
    result = _execute_fixed_argv(
        argv,
        cwd=Path("/"),
        environment={"PATH": "/usr/bin:/bin"},
        timeout=DEFAULT_TIMEOUT_SECONDS,
        output_limit=DEFAULT_MAX_OUTPUT_BYTES,
        tool_id="developer.run_command",
        command_family="pytest",
    )
    if not result.success and result.output.lstrip().startswith("bwrap:"):
        return ToolResult(
            False,
            result.tool_name,
            "Candidate isolation could not be established",
            error_code="candidate_isolation_unavailable",
            metadata=result.metadata,
        )
    return result


def _cleanup_candidate(candidate_root: Path) -> bool:
    try:
        shutil.rmtree(candidate_root)
    except OSError:
        return False
    return not candidate_root.exists()


def verify_disposable_candidate(
    *,
    workspace: Workspace,
    baseline: SessionBaseline,
    verification_argv: tuple[str, ...],
    repair: Mapping[str, object] | None = None,
    seal_path: str | None = None,
) -> CandidateVerification:
    """Verify one exact baseline or repaired candidate, then destroy its tree."""

    candidate_root: Path | None = None
    result: ToolResult | None = None
    sealed: SealedCandidate | None = None
    mutation_status: str | None = None
    status = "candidate_preparation_failed"
    try:
        candidate_root = Path(tempfile.mkdtemp(prefix="jarvis-candidate-"))
        _copy_baseline(candidate_root, baseline)
        candidate_workspace = Workspace(candidate_root)
        if repair is not None:
            if set(repair) != {"tool", "arguments"}:
                raise CandidateIsolationError("invalid_candidate_repair")
            tool_id = repair["tool"]
            arguments = repair["arguments"]
            if tool_id not in {"developer.patch_file", "developer.write_file"}:
                raise CandidateIsolationError("invalid_candidate_repair")
            if not isinstance(arguments, Mapping):
                raise CandidateIsolationError("invalid_candidate_repair")
            mutation = execute_tool(tool_id, arguments, workspace=candidate_workspace)
            if not mutation.success:
                mutation_status = mutation.error_code or "candidate_mutation_failed"
                status = "candidate_mutation_failed"
                cleanup_succeeded = _cleanup_candidate(candidate_root)
                return CandidateVerification(
                    status if cleanup_succeeded else "candidate_cleanup_failed",
                    None,
                    None,
                    mutation_status,
                    cleanup_succeeded,
                )
            mutation_status = "candidate_applied"

        result = _run_isolated_pytest(
            candidate_root,
            verification_argv,
            workspace,
        )
        if result.success:
            status = "candidate_verification_passed"
        elif result.error_code == "timeout":
            status = "candidate_verification_timeout"
        elif result.error_code == "candidate_isolation_unavailable":
            status = "candidate_isolation_unavailable"
        else:
            status = "candidate_verification_failed"
        if result.success and seal_path is not None:
            sealed_path = candidate_workspace.resolve_path(seal_path)
            if not sealed_path.is_file() or sealed_path.is_symlink():
                raise CandidateIsolationError("candidate_seal_failed")
            content = sealed_path.read_bytes()
            sealed = SealedCandidate(
                seal_path,
                content,
                _sha256(content),
                len(content),
            )
    except CandidateIsolationError as exc:
        status = exc.code
    except (MutationError, WorkspacePathError, OSError, ValueError, TypeError):
        status = "candidate_preparation_failed"

    cleanup_succeeded = bool(
        candidate_root is not None and _cleanup_candidate(candidate_root)
    )
    if not cleanup_succeeded:
        return CandidateVerification(
            "candidate_cleanup_failed",
            result,
            None,
            mutation_status,
            False,
        )
    return CandidateVerification(
        status,
        result,
        sealed,
        mutation_status,
        True,
    )


def promote_sealed_candidate(
    *,
    workspace: Workspace,
    baseline: SessionBaseline,
    proposal_repair: Mapping[str, object],
    sealed: SealedCandidate,
) -> str | None:
    """Atomically promote the exact bytes that passed candidate verification."""

    if _sha256(sealed.content) != sealed.sha256 or len(sealed.content) != sealed.size:
        return "candidate_seal_mismatch"
    baseline_error = validate_session_baseline(workspace, baseline)
    if baseline_error:
        return baseline_error
    if set(proposal_repair) != {"tool", "arguments"}:
        return "proposal_precondition_failed"
    tool_id = proposal_repair["tool"]
    arguments = proposal_repair["arguments"]
    if not isinstance(arguments, Mapping) or arguments.get("path") != sealed.path:
        return "proposal_precondition_failed"
    original = baseline.file(sealed.path)
    if original is None:
        return "proposal_precondition_failed"

    try:
        if tool_id == "developer.patch_file":
            if not original.exists or original.content is None:
                return "proposal_precondition_failed"
            old_text = arguments.get("old_text")
            if not isinstance(old_text, str):
                return "proposal_precondition_failed"
            current_text = original.content.decode("utf-8", errors="strict")
            if current_text.count(old_text) != 1:
                return "proposal_precondition_failed"
            target = prepare_mutation_target(
                workspace,
                sealed.path,
                require_exists=True,
            )
            _, current_content, snapshot = read_existing_text(workspace, target)
            if (
                _file_snapshot_tuple(snapshot) != _baseline_snapshot_tuple(original)
                or _sha256(current_content) != original.sha256
            ):
                return "approved_file_changed"
            atomic_write_text(
                workspace,
                target,
                sealed.content,
                replace_existing=True,
                expected_snapshot=snapshot,
            )
        elif tool_id == "developer.write_file":
            if original.exists:
                return "proposal_precondition_failed"
            target = prepare_mutation_target(workspace, sealed.path)
            if target.existed:
                return "approved_file_changed"
            atomic_write_text(
                workspace,
                target,
                sealed.content,
                replace_existing=False,
            )
        else:
            return "proposal_precondition_failed"
    except (MutationError, UnicodeDecodeError, OSError, ValueError, TypeError):
        return "promotion_failed"
    return None
