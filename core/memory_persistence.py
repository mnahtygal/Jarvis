"""Controlled automatic persistence for eligible Brain v2 memory decisions."""

from __future__ import annotations

import logging
import string
from dataclasses import dataclass
from typing import Any, Dict, List

from core.memory_decision import MemoryDecision, MemoryType
from core.semantic_memory import add_semantic_memory, search_semantic_memories


logger = logging.getLogger(__name__)

PROJECT_NOTE_AUTO_SAVE_THRESHOLD = 0.70
PERSISTENCE_TARGET_NONE = "none"
PERSISTENCE_TARGET_SEMANTIC = "semantic_memory"


@dataclass(frozen=True)
class MemoryPersistenceDecision:
    persist: bool
    target: str
    reason: str


@dataclass(frozen=True)
class MemoryPersistenceResult:
    persisted: bool
    target: str
    status: str
    reason: str


def determine_persistence(decision: MemoryDecision) -> MemoryPersistenceDecision:
    """Choose whether the observe-only decision is eligible for auto-save."""

    if decision.memory_type is not MemoryType.PROJECT_NOTE:
        return MemoryPersistenceDecision(False, PERSISTENCE_TARGET_NONE, "not a project note")

    if not decision.should_store:
        return MemoryPersistenceDecision(False, PERSISTENCE_TARGET_NONE, "memory decision declined")

    if decision.confidence < PROJECT_NOTE_AUTO_SAVE_THRESHOLD:
        return MemoryPersistenceDecision(False, PERSISTENCE_TARGET_NONE, "below project note threshold")

    return MemoryPersistenceDecision(True, PERSISTENCE_TARGET_SEMANTIC, "eligible project note")


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


def persist_project_note(
    content: str,
    decision: MemoryDecision,
) -> MemoryPersistenceResult:
    """Persist one eligible project note with duplicate protection.

    Persistence failures are logged and converted to safe status metadata so
    the original user response can remain unchanged.
    """

    persistence = determine_persistence(decision)
    if not persistence.persist:
        status = (
            "skipped"
            if decision.memory_type is MemoryType.PROJECT_NOTE
            else "not_applicable"
        )
        return MemoryPersistenceResult(
            False,
            persistence.target,
            status,
            persistence.reason,
        )

    try:
        results = search_semantic_memories(content, limit=3)
        duplicate = _is_duplicate(content, results)
    except Exception:
        logger.exception("Automatic project-note duplicate check failed")
        return MemoryPersistenceResult(
            False,
            PERSISTENCE_TARGET_SEMANTIC,
            "failed",
            "duplicate check failed",
        )

    if duplicate:
        return MemoryPersistenceResult(
            False,
            PERSISTENCE_TARGET_SEMANTIC,
            "duplicate",
            "duplicate project note",
        )

    try:
        add_semantic_memory(
            content=content,
            source_type="project_note",
            metadata={
                "source": "brain_v2",
                "capture_method": "automatic_project_note",
            },
        )
    except Exception:
        logger.exception("Automatic project-note persistence failed")
        return MemoryPersistenceResult(
            False,
            PERSISTENCE_TARGET_SEMANTIC,
            "failed",
            "semantic persistence failed",
        )

    return MemoryPersistenceResult(
        True,
        PERSISTENCE_TARGET_SEMANTIC,
        "persisted",
        "project note persisted",
    )
