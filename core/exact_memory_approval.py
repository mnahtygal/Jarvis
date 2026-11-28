"""Standalone review and single-use approval for exact-memory changes."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from threading import Lock
from time import monotonic
from unicodedata import category
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.memory_approval import (
    DEFAULT_MAX_PENDING,
    MAX_INTERACTION_ID_CHARS,
    PROPOSAL_TTL_SECONDS,
    InteractionSource,
    MemoryApprovalError,
    ProposalStatus,
    _CREDENTIAL_PATTERN,
    _RETENTION_OPT_OUT,
)


MAX_KEY_CHARS = 256
MAX_VALUE_CHARS = 1000
_UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_CONFIRMATION = re.compile(r"(approve|cancel) exact memory ([0-9a-f]{32})")


class ExactMemoryOperation(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True, repr=False)
class ExactMemoryRecordSnapshot:
    """A read-only copy of an existing row, validated by the engine."""

    record_id: int
    memory_key: str
    memory_value: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExactMemoryProposal:
    """Review data. Even an approved copy grants no independent write authority."""

    proposal_id: str
    interaction_id: str = field(repr=False)
    operation: ExactMemoryOperation
    memory_key: str = field(repr=False)
    existing_record: ExactMemoryRecordSnapshot | None = field(repr=False)
    proposed_value: str | None = field(repr=False)
    created_at: float
    expires_at: float
    status: ProposalStatus = ProposalStatus.PENDING


class _LookupReservation:
    __slots__ = ()


def _has_unsafe_text(text: str) -> bool:
    return any(category(char) in _UNSAFE_CATEGORIES for char in text)


def _screen_review(key: str, value: str | None) -> str | None:
    # Also screen joined fields so a credential label and its value are
    # checked together even when neither field triggers the pattern alone.
    fields = (key,) if value is None else (key, value, f"{key}: {value}", f"{key} {value}")
    if any(_CREDENTIAL_PATTERN.search(text) for text in fields):
        return "credential_pattern"
    if any(_RETENTION_OPT_OUT.search(text) for text in fields):
        return "retention_opt_out"
    return None


def _normalize_key(key: str) -> str:
    if type(key) is not str:
        raise MemoryApprovalError("invalid_key")
    if len(key) > MAX_KEY_CHARS:
        raise MemoryApprovalError("oversized_key")
    if _has_unsafe_text(key):
        raise MemoryApprovalError("unsafe_key")
    normalized = key.strip().lower()
    if not normalized:
        raise MemoryApprovalError("invalid_key")
    if len(normalized) > MAX_KEY_CHARS:
        raise MemoryApprovalError("oversized_key")
    if _has_unsafe_text(normalized):
        raise MemoryApprovalError("unsafe_key")
    return normalized


def _validate_timestamp(value: datetime | None) -> bool:
    # Accept datetime values with immutable timezone implementations.
    return value is None or (
        type(value) is datetime
        and type(value.tzinfo) in (type(None), timezone, ZoneInfo)
    )


def _validate_snapshot(record: object, key: str) -> ExactMemoryRecordSnapshot | None:
    if record is None:
        return None
    if type(record) is ExactMemoryRecordSnapshot:
        try:
            record_id = record.record_id
            memory_key = record.memory_key
            value = record.memory_value
            created_at = record.created_at
            updated_at = record.updated_at
        except AttributeError:
            pass
        else:
            if (
                type(record_id) is int and record_id > 0
                and type(memory_key) is str and memory_key == key
                and type(value) is str and len(value) <= MAX_VALUE_CHARS
                and _validate_timestamp(created_at) and _validate_timestamp(updated_at)
            ):
                if _has_unsafe_text(value) or _screen_review(key, value):
                    raise MemoryApprovalError("unsafe_snapshot")
                return record
    raise MemoryApprovalError("invalid_snapshot")


class ExactMemoryApprovalEngine:
    """Manage bounded, process-local approvals for a trusted composition layer.

    The caller supplies a read-only lookup and derives trusted interaction
    identity itself. The engine performs no persistence.
    """

    def __init__(
        self,
        lookup: Callable[[str], ExactMemoryRecordSnapshot | None],
        *,
        clock: Callable[[], float] = monotonic,
        max_pending: int = DEFAULT_MAX_PENDING,
    ) -> None:
        if not callable(lookup):
            raise TypeError("lookup must be callable")
        if not callable(clock):
            raise TypeError("clock must be callable")
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("max_pending must be a positive integer")
        self._lookup = lookup
        self._clock = clock
        self._max_pending = max_pending
        self._pending: dict[str, ExactMemoryProposal | _LookupReservation] = {}
        self._lock = Lock()

    @staticmethod
    def _validate_interaction(interaction_id: str, source: InteractionSource) -> None:
        if source is not InteractionSource.TRUSTED_LOCAL_USER:
            raise MemoryApprovalError("untrusted_source")
        if (
            type(interaction_id) is not str
            or len(interaction_id) > MAX_INTERACTION_ID_CHARS
            or not interaction_id.strip()
            or _has_unsafe_text(interaction_id)
        ):
            raise MemoryApprovalError("invalid_interaction")

    def _now(self) -> float:
        try:
            value = self._clock()
            if type(value) in (int, float):
                now = float(value)
                deadline = now + PROPOSAL_TTL_SECONDS
                if isfinite(now) and isfinite(deadline) and deadline > now:
                    return now
        except Exception:
            pass
        raise MemoryApprovalError("invalid_clock")

    def propose(
        self,
        *,
        interaction_id: str,
        source: InteractionSource,
        operation: ExactMemoryOperation,
        memory_key: str,
        proposed_value: str | None = None,
    ) -> ExactMemoryProposal:
        self._validate_interaction(interaction_id, source)
        if type(operation) is not ExactMemoryOperation:
            raise MemoryApprovalError("invalid_operation")
        key = _normalize_key(memory_key)
        if operation is ExactMemoryOperation.DELETE:
            if proposed_value is not None:
                raise MemoryApprovalError("unexpected_value")
        else:
            if type(proposed_value) is not str:
                raise MemoryApprovalError("invalid_value")
            if len(proposed_value) > MAX_VALUE_CHARS:
                raise MemoryApprovalError("oversized_value")
            if _has_unsafe_text(proposed_value):
                raise MemoryApprovalError("unsafe_value")
            if not proposed_value.strip():
                raise MemoryApprovalError("invalid_value")
        rejection = _screen_review(key, proposed_value)
        if rejection is not None:
            raise MemoryApprovalError(rejection)

        reservation = _LookupReservation()
        with self._lock:
            self._cleanup_expired(self._now())
            if interaction_id in self._pending:
                raise MemoryApprovalError("already_pending")
            if len(self._pending) >= self._max_pending:
                raise MemoryApprovalError("capacity_reached")
            self._pending[interaction_id] = reservation

        try:
            existing = self._review_existing(key, operation, proposed_value)
            with self._lock:
                now = self._now()
                proposal = ExactMemoryProposal(
                    proposal_id=uuid4().hex,
                    interaction_id=interaction_id,
                    operation=operation,
                    memory_key=key,
                    existing_record=existing,
                    proposed_value=proposed_value,
                    created_at=now,
                    expires_at=now + PROPOSAL_TTL_SECONDS,
                )
                self._pending[interaction_id] = proposal
                return proposal
        finally:
            with self._lock:
                # A published proposal may already have been consumed and
                # replaced by another reservation. Only remove our own.
                if self._pending.get(interaction_id) is reservation:
                    del self._pending[interaction_id]

    def _review_existing(
        self, key: str, operation: ExactMemoryOperation, proposed_value: str | None,
    ) -> ExactMemoryRecordSnapshot | None:
        try:
            result = self._lookup(key)
        except Exception:
            pass
        else:
            record = _validate_snapshot(result, key)
            if operation is ExactMemoryOperation.CREATE:
                if record is not None:
                    raise MemoryApprovalError("record_exists")
            elif record is None:
                raise MemoryApprovalError("record_missing")
            elif operation is ExactMemoryOperation.UPDATE and record.memory_value == proposed_value:
                raise MemoryApprovalError("no_change")
            return record
        # Raise outside the handler so the underlying exception is not chained.
        raise MemoryApprovalError("lookup_failed")

    def approve(
        self, *, interaction_id: str, source: InteractionSource, command: str,
    ) -> ExactMemoryProposal:
        return self._consume(interaction_id, source, command, "approve", ProposalStatus.APPROVED)

    def cancel(
        self, *, interaction_id: str, source: InteractionSource, command: str,
    ) -> ExactMemoryProposal:
        return self._consume(interaction_id, source, command, "cancel", ProposalStatus.CANCELLED)

    def _consume(
        self,
        interaction_id: str,
        source: InteractionSource,
        command: str,
        verb: str,
        status: ProposalStatus,
    ) -> ExactMemoryProposal:
        self._validate_interaction(interaction_id, source)
        match = _CONFIRMATION.fullmatch(command) if type(command) is str else None
        if match is None or match[1] != verb:
            raise MemoryApprovalError("invalid_confirmation")
        with self._lock:
            proposal = self._pending.get(interaction_id)
            if type(proposal) is not ExactMemoryProposal or proposal.proposal_id != match[2]:
                raise MemoryApprovalError("no_matching_proposal")
            expired = self._now() >= proposal.expires_at
            del self._pending[interaction_id]
            if expired:
                raise MemoryApprovalError("expired")
            return replace(proposal, status=status)

    def cleanup_expired(self) -> int:
        """Drop expired published proposals. In-flight lookups keep their slots."""
        with self._lock:
            return self._cleanup_expired(self._now())

    def _cleanup_expired(self, now: float) -> int:
        expired = [
            interaction_id for interaction_id, proposal in self._pending.items()
            if type(proposal) is ExactMemoryProposal and now >= proposal.expires_at
        ]
        for interaction_id in expired:
            del self._pending[interaction_id]
        return len(expired)
