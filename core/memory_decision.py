"""Observe-only memory decisions for Brain v2 requests."""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum

from core.request_classifier import RequestClassification, RequestIntent


class MemoryType(str, Enum):
    NONE = "none"
    EXACT_FACT = "exact_fact"
    SEMANTIC_NOTE = "semantic_note"
    EXPLICIT_MEMORY_COMMAND = "explicit_memory_command"
    PROJECT_NOTE = "project_note"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class MemoryDecision:
    should_store: bool
    memory_type: MemoryType
    confidence: float
    reason: str


def _normalize(command: str) -> str:
    translator = str.maketrans({character: " " for character in string.punctuation})
    normalized = command.lower().strip().translate(translator)
    return " ".join(normalized.split())


def _none(reason: str, confidence: float = 0.93) -> MemoryDecision:
    return MemoryDecision(False, MemoryType.NONE, confidence, reason)


def decide_memory(
    command: str,
    classification: RequestClassification,
) -> MemoryDecision:
    """Decide whether a user command resembles durable memory.

    This function is intentionally heuristic and observe-only. It performs no
    persistence, database access, model calls, or external actions.
    """

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    text = _normalize(command)

    if classification.intent in {
        RequestIntent.FACTUAL_QUESTION,
        RequestIntent.MEMORY_RECALL,
        RequestIntent.RUNTIME_STATUS,
        RequestIntent.SYSTEM_COMMAND,
        RequestIntent.CAMERA_OR_VISION,
        RequestIntent.HELP_OR_DOCS,
    }:
        return _none("question or command", 0.96)

    if text.startswith("forget that ") or text.startswith("forget "):
        return _none("memory deletion command", 0.99)

    if text.startswith(("remember ", "note ", "save ")):
        return MemoryDecision(
            True,
            MemoryType.EXPLICIT_MEMORY_COMMAND,
            0.98,
            "explicit memory command",
        )

    if text.startswith("update my "):
        return MemoryDecision(
            True,
            MemoryType.EXPLICIT_MEMORY_COMMAND,
            0.96,
            "explicit memory update",
        )

    if text.startswith((
        "what ",
        "why ",
        "how ",
        "which ",
        "where ",
        "who ",
        "can ",
        "could ",
        "would ",
        "should ",
    )):
        return _none("question or instruction", 0.96)

    if text.startswith(("i prefer ", "i like ")) or (
        text.startswith("my ") and ("favorite" in text or "preference" in text)
    ):
        return MemoryDecision(True, MemoryType.PREFERENCE, 0.90, "durable preference")

    if (
        text.startswith(("we should ", "i want to ", "we need to ", "someday "))
        or " should use " in text
        or text.endswith(" someday")
    ):
        return MemoryDecision(True, MemoryType.PROJECT_NOTE, 0.72, "project idea")

    if text.startswith(("i work at ", "i work for ", "i moved ")):
        return MemoryDecision(True, MemoryType.EXACT_FACT, 0.84, "durable personal fact")

    if text.startswith("my ") and " is " in text:
        return MemoryDecision(True, MemoryType.EXACT_FACT, 0.82, "durable stated fact")

    if " is working on " in text or " is building " in text:
        return MemoryDecision(True, MemoryType.PROJECT_NOTE, 0.70, "project activity")

    if text.startswith(("i am watching ", "i m watching ", "i am drinking ", "i m drinking ")):
        return _none("transient activity", 0.90)

    if text in {"it is raining right now", "i am tired", "i m tired"}:
        return _none("transient state", 0.90)

    return _none("no durable memory signal")
