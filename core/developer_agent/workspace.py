"""Workspace boundary shared by every developer filesystem tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


class WorkspacePathError(ValueError):
    """A path is invalid or escapes the configured workspace."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Workspace:
    """Resolve paths only within one approved project root."""

    root: Path = DEFAULT_WORKSPACE_ROOT

    def __post_init__(self) -> None:
        root = Path(self.root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("workspace root must be a directory")
        object.__setattr__(self, "root", root)

    def resolve_path(self, path: str, *, require_exists: bool = True) -> Path:
        if not isinstance(path, str) or not path or "\x00" in path:
            raise WorkspacePathError("invalid_path")

        requested = Path(path)
        candidate = requested if requested.is_absolute() else self.root / requested
        try:
            resolved = candidate.resolve(strict=require_exists)
        except (FileNotFoundError, OSError):
            raise WorkspacePathError("path_not_found") from None

        if not resolved.is_relative_to(self.root):
            raise WorkspacePathError("outside_workspace")
        return resolved

    def relative_path(self, path: Path) -> str:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise WorkspacePathError("outside_workspace")
        relative = resolved.relative_to(self.root)
        return "." if relative == Path(".") else relative.as_posix()


def resolve_workspace_path(
    relative_path: str,
    *,
    workspace: Workspace | None = None,
) -> Path:
    """Resolve a path through the standard Jarvis workspace guard."""

    return (workspace or Workspace()).resolve_path(relative_path)
