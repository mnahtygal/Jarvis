"""Brain v2 request orchestration.

Phase 5 keeps the existing router as the execution boundary while recording
observe-only memory decisions alongside execution metadata.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core.brain_request_context import (
    BrainRequestContext,
    reset_active_request_context,
    set_active_request_context,
)
from core.execution_strategy import (
    ExecutionStrategy,
    determine_execution_strategy,
)
from core.memory_decision import MemoryDecision, decide_memory
from core.request_classifier import ContextPolicy, RequestIntent, classify_request
from core.result_evaluator import EvaluationResult, evaluate_response
from core.router import route


logger = logging.getLogger(__name__)

BRAIN_VERSION = "2.0-phase5"


@dataclass
class BrainResult:
    """Structured result returned by the Brain v2 orchestration layer."""

    response: str
    route_type: str = "legacy_router"
    intent: RequestIntent | None = None
    context_policy: ContextPolicy | None = None
    execution_strategy: ExecutionStrategy | None = None
    evaluation: EvaluationResult | None = None
    memory_decision: MemoryDecision | None = None
    actual_route: str | None = None
    used_llm: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def process_request(command: str) -> BrainResult:
    """Process a command through the existing router.

    Phase 5 deliberately does not own session persistence, memory writes, or
    LLM calls. Those responsibilities remain in the existing brain, router,
    and skill layers.
    """

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    normalized_command = command.strip()
    started_at = time.perf_counter()
    classification = classify_request(normalized_command)
    execution_strategy = determine_execution_strategy(classification)
    memory_decision = decide_memory(normalized_command, classification)
    request_context = BrainRequestContext(
        context_policy=classification.context_policy,
    )
    context_token = set_active_request_context(request_context)

    try:
        response = route(normalized_command)
    except Exception:
        logger.exception("Brain v2 request failed in legacy router")
        raise
    finally:
        reset_active_request_context(context_token)

    processing_ms = (time.perf_counter() - started_at) * 1000
    evaluation = evaluate_response(response)
    policy = classification.context_policy
    context_sources = [
        source
        for enabled, source in (
            (policy.use_exact_memory, "exact_memory"),
            (policy.use_semantic_memory, "semantic_memory"),
            (policy.use_recent_history, "recent_history"),
            (policy.use_last_topic, "last_topic"),
        )
        if enabled
    ]
    metadata = {
        "command_length": len(normalized_command),
        "route_type": "legacy_router",
        "intent": classification.intent.value,
        "context_policy": asdict(classification.context_policy),
        "context_sources": context_sources,
        "execution_strategy": execution_strategy.value,
        "evaluation": asdict(evaluation),
        "memory_decision": {
            "should_store": memory_decision.should_store,
            "memory_type": memory_decision.memory_type.value,
            "confidence": memory_decision.confidence,
            "reason": memory_decision.reason,
        },
        "should_store_memory": memory_decision.should_store,
        "memory_type": memory_decision.memory_type.value,
        "memory_confidence": memory_decision.confidence,
        "actual_route": "unknown",
        "processing_ms": processing_ms,
    }
    logger.debug(
        "Brain v2 request completed intent=%s strategy=%s quality=%s processing_ms=%.2f",
        metadata["intent"],
        metadata["execution_strategy"],
        metadata["evaluation"]["quality"],
        processing_ms,
    )

    return BrainResult(
        response=response,
        intent=classification.intent,
        context_policy=classification.context_policy,
        execution_strategy=execution_strategy,
        evaluation=evaluation,
        memory_decision=memory_decision,
        actual_route="unknown",
        metadata=metadata,
    )
