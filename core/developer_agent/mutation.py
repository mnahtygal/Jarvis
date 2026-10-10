"""Shared validation and atomic UTF-8 writes for mutation tools."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import secrets
import stat

from core.developer_agent.policy import mutation_protection_code
from core.developer_agent.workspace import Workspace, WorkspacePathError


MAX_FILE_BYTES = 1024 * 1024
MAX_PATCH_PAYLOAD_BYTES = 256 * 1024
TEMP_FILE_ATTEMPTS = 10


class MutationError(RuntimeError):
    """Safe, stable mutation failure without raw OS details."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FileSnapshot:
    device: int
    inode: int
    size: int
    modified_ns: int
    mode: int


@dataclass(frozen=True)
class MutationTarget:
    requested: Path
    resolved: Path
    relative_path: str
    existed: bool


def encode_text(value: object, *, max_bytes: int, allow_empty: bool = True) -> bytes:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise MutationError("invalid_text", "Text content is invalid")
    if "\x00" in value:
        raise MutationError("binary_content", "Binary content is not allowed")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise MutationError("invalid_text", "Text must be valid UTF-8") from None
    if len(encoded) > max_bytes:
        raise MutationError("content_too_large", "Text exceeds the safe size limit")
    return encoded


def _policy_error(
    workspace: Workspace,
    requested: Path,
    resolved: Path,
) -> MutationError | None:
    if requested.is_absolute():
        try:
            requested = requested.relative_to(workspace.root)
        except ValueError:
            requested = Path(requested.name)
    resolved_relative = resolved.relative_to(workspace.root)
    code = mutation_protection_code(requested, resolved_relative)
    messages = {
        "repository_metadata": "Repository metadata cannot be modified",
        "protected_file": "Protected personal files cannot be modified",
        "sensitive_file": "Sensitive files cannot be modified",
    }
    return MutationError(code, messages[code]) if code else None


def prepare_mutation_target(
    workspace: Workspace,
    path: object,
    *,
    create_parent_dirs: bool = False,
    require_exists: bool = False,
) -> MutationTarget:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise MutationError("invalid_path", "Target path is invalid")
    if not isinstance(create_parent_dirs, bool):
        raise MutationError("invalid_arguments", "create_parent_dirs must be a boolean")

    requested = Path(path)
    try:
        resolved = workspace.resolve_path(path, require_exists=require_exists)
    except WorkspacePathError as exc:
        raise MutationError(exc.code, "Target is not available in the workspace") from None

    policy_error = _policy_error(workspace, requested, resolved)
    if policy_error:
        raise policy_error
    if resolved == workspace.root or (resolved.exists() and resolved.is_dir()):
        raise MutationError("not_a_file", "Target path is a directory")

    parent = resolved.parent
    if not parent.exists():
        if require_exists or not create_parent_dirs:
            raise MutationError("parent_missing", "Target parent directory does not exist")
        try:
            unresolved_parent = workspace.resolve_path(str(parent), require_exists=False)
            if unresolved_parent != parent:
                raise MutationError("path_changed", "Target path changed during validation")
            parent.mkdir(parents=True, exist_ok=True)
        except MutationError:
            raise
        except OSError:
            raise MutationError("create_parent_failed", "Parent directories could not be created") from None

    try:
        canonical_parent = workspace.resolve_path(str(parent))
        revalidated = workspace.resolve_path(str(resolved), require_exists=False)
    except WorkspacePathError:
        raise MutationError("path_changed", "Target path changed during validation") from None
    if canonical_parent != parent or revalidated != resolved:
        raise MutationError("path_changed", "Target path changed during validation")
    if not canonical_parent.is_dir():
        raise MutationError("parent_not_directory", "Target parent is not a directory")

    policy_error = _policy_error(workspace, requested, revalidated)
    if policy_error:
        raise policy_error
    existed = revalidated.exists()
    if require_exists and not existed:
        raise MutationError("path_not_found", "Target file does not exist")
    if existed and not revalidated.is_file():
        raise MutationError("not_a_file", "Target is not a regular file")

    return MutationTarget(
        requested=requested,
        resolved=revalidated,
        relative_path=(
            workspace.relative_path(revalidated)
            if existed
            else revalidated.relative_to(workspace.root).as_posix()
        ),
        existed=existed,
    )


def _snapshot(file_stat: os.stat_result) -> FileSnapshot:
    return FileSnapshot(
        device=file_stat.st_dev,
        inode=file_stat.st_ino,
        size=file_stat.st_size,
        modified_ns=file_stat.st_mtime_ns,
        mode=stat.S_IMODE(file_stat.st_mode),
    )


def _create_temp_file(parent: Path, mode: int) -> tuple[int, Path]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    for _ in range(TEMP_FILE_ATTEMPTS):
        temp_path = parent / f".jarvis-developer-{secrets.token_hex(8)}.tmp"
        try:
            descriptor = os.open(temp_path, flags, mode)
        except FileExistsError:
            continue
        try:
            actual_mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
            if actual_mode != mode:
                raise MutationError(
                    "mode_preservation_failed",
                    "Existing file mode could not be preserved safely",
                )
            return descriptor, temp_path
        except Exception:
            os.close(descriptor)
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    raise MutationError("temp_file_failed", "A private temporary file could not be created")


def read_existing_text(
    workspace: Workspace,
    target: MutationTarget,
    *,
    max_bytes: int = MAX_FILE_BYTES,
) -> tuple[str, bytes, FileSnapshot]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target.resolved, flags)
        with os.fdopen(descriptor, "rb") as file_handle:
            file_stat = os.fstat(file_handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise MutationError("not_a_file", "Target is not a regular file")
            data = file_handle.read(max_bytes + 1)
    except MutationError:
        raise
    except OSError:
        raise MutationError("read_failed", "Target file could not be read") from None

    if len(data) > max_bytes:
        raise MutationError("file_too_large", "Target file exceeds the safe size limit")
    if b"\x00" in data:
        raise MutationError("binary_file", "Binary files cannot be modified")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise MutationError("binary_file", "Target is not valid UTF-8 text") from None

    try:
        revalidated = workspace.resolve_path(str(target.resolved))
        current_stat = revalidated.stat()
    except (WorkspacePathError, OSError):
        raise MutationError("path_changed", "Target path changed during validation") from None
    snapshot = _snapshot(file_stat)
    if revalidated != target.resolved or _snapshot(current_stat) != snapshot:
        raise MutationError("concurrent_modification", "Target changed during validation")
    return text, data, snapshot


def atomic_write_text(
    workspace: Workspace,
    target: MutationTarget,
    data: bytes,
    *,
    replace_existing: bool,
    expected_snapshot: FileSnapshot | None = None,
) -> None:
    temp_path: Path | None = None
    descriptor: int | None = None
    try:
        parent = workspace.resolve_path(str(target.resolved.parent))
        revalidated = workspace.resolve_path(str(target.resolved), require_exists=False)
        if parent != target.resolved.parent or revalidated != target.resolved:
            raise MutationError("path_changed", "Target path changed before mutation")
        policy_error = _policy_error(workspace, target.requested, revalidated)
        if policy_error:
            raise policy_error

        existing_mode: int | None = None
        if revalidated.exists():
            current_snapshot = _snapshot(revalidated.stat())
            if expected_snapshot is not None and current_snapshot != expected_snapshot:
                raise MutationError("concurrent_modification", "Target changed before mutation")
            existing_mode = current_snapshot.mode
        elif expected_snapshot is not None:
            raise MutationError("concurrent_modification", "Target changed before mutation")

        descriptor, temp_path = _create_temp_file(
            parent,
            existing_mode if existing_mode is not None else 0o600,
        )
        with os.fdopen(descriptor, "wb") as file_handle:
            descriptor = None
            file_handle.write(data)
            file_handle.flush()
            os.fsync(file_handle.fileno())

        final_parent = workspace.resolve_path(str(parent))
        final_target = workspace.resolve_path(str(revalidated), require_exists=False)
        if final_parent != parent or final_target != revalidated:
            raise MutationError("path_changed", "Target path changed before mutation")
        policy_error = _policy_error(workspace, target.requested, final_target)
        if policy_error:
            raise policy_error
        if expected_snapshot is not None:
            try:
                if _snapshot(final_target.stat()) != expected_snapshot:
                    raise MutationError("concurrent_modification", "Target changed before mutation")
            except FileNotFoundError:
                raise MutationError("concurrent_modification", "Target changed before mutation") from None

        if replace_existing:
            os.replace(temp_path, final_target)
            temp_path = None
        else:
            os.link(temp_path, final_target, follow_symlinks=False)
            try:
                temp_path.unlink()
                temp_path = None
            except OSError:
                pass

        try:
            directory_descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            pass
    except MutationError:
        raise
    except FileExistsError:
        raise MutationError("target_exists", "Target already exists") from None
    except OSError:
        raise MutationError("write_failed", "Target file could not be written") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
