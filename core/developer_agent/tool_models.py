"""Immutable models shared by the controlled developer tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ToolResult:
    """Deterministic tool output safe for a future agent loop."""

    success: bool
    tool_name: str
    output: str
    error_code: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


def success_result(
    tool_name: str,
    output: str,
    *,
    metadata: Mapping[str, object] | None = None,
) -> ToolResult:
    return ToolResult(True, tool_name, output, metadata=metadata or {})


def failure_result(tool_name: str, error_code: str, output: str) -> ToolResult:
    return ToolResult(False, tool_name, output, error_code=error_code)
