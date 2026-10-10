"""Safe verification evidence for controlled Developer Agent checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.developer_agent.tool_models import ToolResult


VERIFICATION_COMMAND_FAMILIES = frozenset({
    "compileall",
    "py_compile",
    "pytest",
})
_EVIDENCE_SEAL = object()


@dataclass(frozen=True, init=False)
class VerificationEvidence:
    """Output-free proof derived from one Developer Agent verification result."""

    successful: bool
    command_family: str
    exit_code: int
    source: str
    _seal: object = field(repr=False, compare=False)

    @classmethod
    def from_tool_result(cls, result: ToolResult) -> VerificationEvidence:
        """Reduce a run-command result to safe, bounded evidence metadata."""

        if type(result) is not ToolResult:
            raise ValueError("verification result type is invalid")
        command_family = result.metadata.get("command_family")
        exit_code = result.metadata.get("exit_code")
        timed_out = result.metadata.get("timed_out", False)
        evidence = object.__new__(cls)
        object.__setattr__(
            evidence,
            "successful",
            (
                result.tool_name == "developer.run_command"
                and result.success is True
                and timed_out is False
                and isinstance(exit_code, int)
                and not isinstance(exit_code, bool)
                and exit_code == 0
                and command_family in VERIFICATION_COMMAND_FAMILIES
            ),
        )
        object.__setattr__(
            evidence,
            "command_family",
            command_family if isinstance(command_family, str) else "",
        )
        object.__setattr__(
            evidence,
            "exit_code",
            (
                exit_code
                if isinstance(exit_code, int) and not isinstance(exit_code, bool)
                else -1
            ),
        )
        object.__setattr__(
            evidence,
            "source",
            result.tool_name if isinstance(result.tool_name, str) else "",
        )
        object.__setattr__(evidence, "_seal", _EVIDENCE_SEAL)
        return evidence


def is_successful_verification(evidence: object) -> bool:
    """Validate exact evidence fields without accepting a bare boolean."""

    return (
        type(evidence) is VerificationEvidence
        and evidence.successful is True
        and evidence.command_family in VERIFICATION_COMMAND_FAMILIES
        and type(evidence.exit_code) is int
        and evidence.exit_code == 0
        and evidence.source == "developer.run_command"
        and evidence._seal is _EVIDENCE_SEAL
    )
