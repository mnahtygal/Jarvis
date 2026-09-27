"""Expected execution strategy for a classified Brain v2 request."""

from __future__ import annotations

from enum import Enum

from core.request_classifier import RequestClassification, RequestIntent


class ExecutionStrategy(str, Enum):
    DETERMINISTIC = "deterministic"
    MEMORY = "memory"
    SEMANTIC_MEMORY = "semantic_memory"
    LLM = "llm"
    SYSTEM = "system"
    CAMERA_VISION = "camera_vision"
    UNKNOWN = "unknown"


def determine_execution_strategy(
    classification: RequestClassification,
) -> ExecutionStrategy:
    """Determine the expected route without side effects or external calls."""

    intent = classification.intent

    if intent is RequestIntent.MEMORY_WRITE:
        return ExecutionStrategy.MEMORY

    if intent is RequestIntent.MEMORY_RECALL:
        if classification.context_policy.use_semantic_memory:
            return ExecutionStrategy.SEMANTIC_MEMORY
        return ExecutionStrategy.MEMORY

    if intent is RequestIntent.CAMERA_OR_VISION:
        return ExecutionStrategy.CAMERA_VISION

    if intent in {RequestIntent.RUNTIME_STATUS, RequestIntent.SYSTEM_COMMAND}:
        return ExecutionStrategy.SYSTEM

    if intent is RequestIntent.HELP_OR_DOCS:
        return ExecutionStrategy.DETERMINISTIC

    if intent in {
        RequestIntent.CONVERSATION,
        RequestIntent.FACTUAL_QUESTION,
        RequestIntent.UNKNOWN,
    }:
        return ExecutionStrategy.LLM

    return ExecutionStrategy.UNKNOWN
