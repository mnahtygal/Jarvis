"""Bounded observe-only planning for Brain v2 requests."""

from __future__ import annotations

import string
from dataclasses import dataclass


PLAN_CATEGORIES = frozenset({
    "memory",
    "runtime",
    "system",
    "camera",
    "vision",
    "llm",
    "comparison",
    "summary",
    "unknown",
})


@dataclass(frozen=True)
class PlanStep:
    order: int
    action: str
    category: str


@dataclass(frozen=True)
class PlanResult:
    requires_plan: bool
    steps: tuple[PlanStep, ...]
    confidence: float
    reason: str


def _normalize(command: str) -> str:
    translator = str.maketrans({character: " " for character in string.punctuation})
    normalized = command.lower().strip().translate(translator)
    return " ".join(normalized.split())


def _step(action: str, category: str) -> tuple[str, str]:
    if category not in PLAN_CATEGORIES:
        raise ValueError("Unsupported plan category")
    return action, category


def _plan(
    steps: tuple[tuple[str, str], ...],
    confidence: float,
    reason: str,
) -> PlanResult:
    bounded = steps[:5]
    if len(bounded) < 2:
        return PlanResult(False, (), 0.95, "single-step request")

    return PlanResult(
        True,
        tuple(
            PlanStep(order=index, action=action, category=category)
            for index, (action, category) in enumerate(bounded, start=1)
        ),
        confidence,
        reason,
    )


def analyze_plan(command: str) -> PlanResult:
    """Return a fixed-label diagnostic plan without executing any step."""

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    text = _normalize(command)
    has_sequence = any(
        phrase in text
        for phrase in ("and then", "after that", " then ")
    )
    has_health = "health" in text
    has_model = "model" in text
    has_capture = "capture" in text and ("image" in text or "camera" in text)
    has_analyze = "analyze" in text or "analyse" in text
    has_memory = any(term in text for term in ("remember", "memory", "memories", "told you"))
    has_runtime = "runtime" in text or "running" in text
    has_compare = "compare" in text
    has_inspect = "inspect" in text or "check" in text
    has_summary = "summarize" in text or "summarise" in text
    has_retrieve = "retrieve" in text or "show me what" in text

    if has_sequence and has_health and has_model:
        return _plan(
            (
                _step("check runtime health", "runtime"),
                _step("inspect active model", "system"),
                _step("summarize result", "summary"),
            ),
            0.94,
            "sequenced runtime checks",
        )

    if has_capture and has_analyze:
        return _plan(
            (
                _step("capture workbench image", "camera"),
                _step("analyze captured image", "vision"),
                _step("return description", "summary"),
            ),
            0.95,
            "capture and analysis request",
        )

    if has_memory and has_runtime and has_compare:
        return _plan(
            (
                _step("retrieve relevant memory", "memory"),
                _step("inspect runtime identity", "runtime"),
                _step("compare results", "comparison"),
                _step("summarize comparison", "summary"),
            ),
            0.93,
            "memory runtime comparison",
        )

    if has_retrieve and has_compare:
        return _plan(
            (
                _step("retrieve relevant information", "memory"),
                _step("compare results", "comparison"),
                _step("summarize comparison", "summary"),
            ),
            0.84,
            "retrieval comparison",
        )

    if has_inspect and has_summary:
        return _plan(
            (
                _step("inspect requested state", "system"),
                _step("summarize result", "summary"),
            ),
            0.82,
            "inspection summary",
        )

    if has_sequence:
        inferred: list[tuple[str, str]] = []
        if has_memory:
            inferred.append(_step("retrieve relevant memory", "memory"))
        if has_runtime or has_health:
            inferred.append(_step("inspect runtime state", "runtime"))
        if has_model:
            inferred.append(_step("inspect active model", "system"))
        if has_capture:
            inferred.append(_step("capture image", "camera"))
        if has_analyze:
            inferred.append(_step("analyze result", "vision"))
        if has_compare:
            inferred.append(_step("compare results", "comparison"))

        if len(inferred) >= 2:
            if len(inferred) < 5:
                inferred.append(_step("summarize result", "summary"))
            return _plan(tuple(inferred), 0.80, "explicit step sequence")

    return PlanResult(False, (), 0.95, "single-step request")
