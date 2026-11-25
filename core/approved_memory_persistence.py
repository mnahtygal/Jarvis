"""Persist project notes only as part of consuming a genuine memory approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.memory_approval import InteractionSource, MemoryApprovalEngine, MemoryApprovalError
from core.memory_persistence import _is_duplicate
from core.semantic_memory import add_semantic_memory, search_semantic_memories


PersistenceStatus = Literal[
    "persisted", "duplicate", "unauthorized", "lookup_failed", "persistence_failed"
]


@dataclass(frozen=True, slots=True)
class ApprovedMemoryPersistenceResult:
    status: PersistenceStatus
    commit_uncertain: bool = False


class ApprovedMemoryPersistence:
    """Bind to an engine supplied by the trusted local composition layer."""

    def __init__(self, engine: MemoryApprovalEngine) -> None:
        if type(engine) is not MemoryApprovalEngine:
            raise TypeError("a MemoryApprovalEngine instance is required")
        self._engine = engine

    def approve_and_persist(
        self, *, interaction_id: str, source: InteractionSource, command: str
    ) -> ApprovedMemoryPersistenceResult:
        """Consume approval before storage and make at most one write attempt."""
        try:
            proposal = self._engine.approve(
                interaction_id=interaction_id, source=source, command=command
            )
        except MemoryApprovalError:
            return ApprovedMemoryPersistenceResult("unauthorized")

        try:
            matches = search_semantic_memories(proposal.text, limit=3)
            if not isinstance(matches, list):
                return ApprovedMemoryPersistenceResult("lookup_failed")
            duplicate = _is_duplicate(proposal.text, matches)
        except Exception:
            return ApprovedMemoryPersistenceResult("lookup_failed")
        if duplicate:
            return ApprovedMemoryPersistenceResult("duplicate")

        try:
            memory_id = add_semantic_memory(
                content=proposal.text,
                source_type=proposal.memory_type,
                metadata={
                    "category": proposal.category,
                    "source": "brain_v2",
                    "capture_method": "approved_project_note",
                },
                preserve_whitespace=True,
            )
        except Exception:
            # The existing writer does not report which phase failed.
            return ApprovedMemoryPersistenceResult("persistence_failed", commit_uncertain=True)

        if type(memory_id) is not int or memory_id <= 0:
            return ApprovedMemoryPersistenceResult("persistence_failed", commit_uncertain=True)
        return ApprovedMemoryPersistenceResult("persisted")
