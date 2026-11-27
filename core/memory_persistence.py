"""Project-note capture policy and shared duplicate detection."""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any, Dict, List

from core.memory_decision import MemoryDecision, MemoryType


PERSISTENCE_TARGET_NONE = "none"


@dataclass(frozen=True)
class MemoryPersistenceResult:
    persisted: bool
    target: str
    status: str
    reason: str


def project_note_capture_result(decision: MemoryDecision) -> MemoryPersistenceResult:
    """Report capture policy without reading or writing candidate content.

    Ordinary Brain v2 conversation has no authorization path to persistence.
    A detected project note is observable as approval-required, but this does
    not create a proposal or grant authority to any later request.
    """

    if (
        decision.memory_type is MemoryType.PROJECT_NOTE
        and decision.should_store
    ):
        return MemoryPersistenceResult(
            False,
            PERSISTENCE_TARGET_NONE,
            "approval_required",
            "explicit approval required",
        )

    status = (
        "skipped"
        if decision.memory_type is MemoryType.PROJECT_NOTE
        else "not_applicable"
    )
    return MemoryPersistenceResult(
        False,
        PERSISTENCE_TARGET_NONE,
        status,
        "memory decision declined" if status == "skipped" else "not a project note",
    )


def _normalize_content(content: str) -> str:
    translator = str.maketrans({character: " " for character in string.punctuation})
    normalized = content.lower().strip().translate(translator)
    return " ".join(normalized.split())


def _is_duplicate(content: str, results: List[Dict[str, Any]]) -> bool:
    normalized_content = _normalize_content(content)

    for item in results:
        existing_content = _normalize_content(str(item.get("content", "")))
        if existing_content and existing_content == normalized_content:
            return True

        try:
            similarity = float(item.get("similarity", 0.0))
        except (TypeError, ValueError):
            similarity = 0.0

        if similarity >= 0.96:
            return True

    return False
