"""In-memory approval for one exact project note at a time per interaction."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from threading import Lock
from time import monotonic
from uuid import uuid4


PROPOSAL_TTL_SECONDS = 120.0
MAX_CANDIDATE_CHARS = 1000
DEFAULT_MAX_PENDING = 64
MAX_INTERACTION_ID_CHARS = 128

_CREDENTIAL_PATTERN = re.compile(
    r"\b(?:password|passwd|pwd|(?:api|access|secret|private)[ _-]?key|"
    r"(?:access|auth|api|refresh)[ _-]?token|client[ _-]?secret)"
    r"\s*(?:[:=]|\bis\b)\s*\S"
    r"|\bbearer\s+\S"
    r"|-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"
    r"|\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[A-Z0-9]{16})\b"
    r"|\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@",
    re.IGNORECASE,
)
_RETENTION_OPT_OUT = re.compile(
    r"\b(?:do\s+not|don['’]t|never|please\s+avoid)\s+"
    r"(?:remember(?:ing)?|retain(?:ing)?|stor(?:e|ing)|sav(?:e|ing)|record(?:ing)?|log(?:ging)?)\b"
    r"|\b(?:off[-\s]+the[-\s]+record|no\s+memory|forget\s+(?:this|that|it))\b",
    re.IGNORECASE,
)
_CONFIRMATION = re.compile(r"(approve|cancel) memory ([0-9a-f]{32})")


class InteractionSource(StrEnum):
    TRUSTED_LOCAL_USER = "trusted_local_user"
    REMOTE_USER = "remote_user"
    MODEL = "model"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class MemoryApprovalError(ValueError):
    """A rejection with a fixed, payload-free code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    proposal_id: str
    interaction_id: str
    text: str = field(repr=False)
    created_at: float
    expires_at: float
    status: ProposalStatus = ProposalStatus.PENDING
    memory_type: str = field(init=False, default="project_note")
    category: str = field(init=False, default="project")


class MemoryApprovalEngine:
    """Keep bounded, process-local pending state for trusted user turns."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        max_pending: int = DEFAULT_MAX_PENDING,
    ) -> None:
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("max_pending must be a positive integer")
        self._clock = clock
        self._max_pending = max_pending
        self._pending: dict[str, MemoryProposal] = {}
        self._lock = Lock()

    @staticmethod
    def _validate_interaction(interaction_id: str, source: InteractionSource) -> None:
        if source is not InteractionSource.TRUSTED_LOCAL_USER:
            raise MemoryApprovalError("untrusted_source")
        if (
            type(interaction_id) is not str
            or len(interaction_id) > MAX_INTERACTION_ID_CHARS
            or not interaction_id.strip()
        ):
            raise MemoryApprovalError("invalid_interaction")

    def propose(
        self, *, interaction_id: str, source: InteractionSource, text: str
    ) -> MemoryProposal:
        self._validate_interaction(interaction_id, source)
        if type(text) is not str:
            raise MemoryApprovalError("invalid_candidate")
        if len(text) > MAX_CANDIDATE_CHARS:
            raise MemoryApprovalError("oversized_candidate")
        if not text.strip():
            raise MemoryApprovalError("empty_candidate")
        if _CREDENTIAL_PATTERN.search(text):
            raise MemoryApprovalError("credential_pattern")
        if _RETENTION_OPT_OUT.search(text):
            raise MemoryApprovalError("retention_opt_out")

        with self._lock:
            now = self._clock()
            self._cleanup_expired(now)
            if interaction_id in self._pending:
                raise MemoryApprovalError("already_pending")
            if len(self._pending) >= self._max_pending:
                raise MemoryApprovalError("capacity_reached")
            proposal = MemoryProposal(
                proposal_id=uuid4().hex,
                interaction_id=interaction_id,
                text=text,
                created_at=now,
                expires_at=now + PROPOSAL_TTL_SECONDS,
            )
            self._pending[interaction_id] = proposal
            return proposal

    def approve(
        self, *, interaction_id: str, source: InteractionSource, command: str
    ) -> MemoryProposal:
        return self._consume(interaction_id, source, command, "approve", ProposalStatus.APPROVED)

    def cancel(
        self, *, interaction_id: str, source: InteractionSource, command: str
    ) -> MemoryProposal:
        return self._consume(interaction_id, source, command, "cancel", ProposalStatus.CANCELLED)

    def _consume(
        self,
        interaction_id: str,
        source: InteractionSource,
        command: str,
        verb: str,
        status: ProposalStatus,
    ) -> MemoryProposal:
        self._validate_interaction(interaction_id, source)
        match = _CONFIRMATION.fullmatch(command) if type(command) is str else None
        if match is None or match[1] != verb:
            raise MemoryApprovalError("invalid_confirmation")
        with self._lock:
            proposal = self._pending.get(interaction_id)
            if proposal is None or proposal.proposal_id != match[2]:
                raise MemoryApprovalError("no_matching_proposal")
            expired = self._clock() >= proposal.expires_at
            del self._pending[interaction_id]
            if expired:
                raise MemoryApprovalError(ProposalStatus.EXPIRED.value)
            return replace(proposal, status=status)

    def cleanup_expired(self) -> int:
        """Remove expired proposals and return the number removed."""
        with self._lock:
            return self._cleanup_expired(self._clock())

    def _cleanup_expired(self, now: float) -> int:
        expired = [
            interaction_id for interaction_id, proposal in self._pending.items()
            if now >= proposal.expires_at
        ]
        for interaction_id in expired:
            del self._pending[interaction_id]
        return len(expired)
