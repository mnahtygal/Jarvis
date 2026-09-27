"""Brain v2 request orchestration.

Phase 10 validates observe-only plans before the unchanged router.
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
from core.brain_status_v2 import (
    BRAIN_VERSION,
    publish_brain_v2_failure,
    publish_brain_v2_status,
)
from core.execution_strategy import (
    ExecutionStrategy,
    determine_execution_strategy,
)
from core.memory_decision import MemoryDecision, decide_memory
from core.memory_persistence import (
    MemoryPersistenceResult,
    persist_project_note,
)
from core.planner import PlanResult, analyze_plan
from core.plan_validator import PlanValidationResult, validate_plan
from core.request_classifier import ContextPolicy, RequestIntent, classify_request
from core.result_evaluator import EvaluationResult, evaluate_response
from core.router import route
from core.route_trace import begin_route_trace, get_actual_route, reset_route_trace


logger = logging.getLogger(__name__)

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
    memory_persisted: bool = False
    memory_persistence_target: str = "none"
    memory_persistence_status: str = "not_applicable"
    plan: PlanResult | None = None
    requires_plan: bool = False
    plan_step_count: int = 0
    plan_categories: tuple[str, ...] = ()
    planner_confidence: float = 0.0
    plan_validation: PlanValidationResult | None = None
    plan_valid: bool = True
    plan_validation_status: str = "not_required"
    unsupported_plan_categories: tuple[str, ...] = ()
    actual_route: str | None = None
    used_llm: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def process_request(command: str) -> BrainResult:
    """Process a command through the existing router.

    Phase 10 validates diagnostic plans without executing them. The existing
    router still executes the request exactly once.
    """

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    normalized_command = command.strip()
    started_at = time.perf_counter()
    classification = classify_request(normalized_command)
    execution_strategy = determine_execution_strategy(classification)
    memory_decision = decide_memory(normalized_command, classification)
    plan = analyze_plan(normalized_command)
    plan_validation = validate_plan(plan)
    plan_categories = tuple(step.category for step in plan.steps)
    request_context = BrainRequestContext(
        context_policy=classification.context_policy,
    )
    context_token = set_active_request_context(request_context)
    trace_token = begin_route_trace()

    try:
        response = route(normalized_command)
        actual_route = get_actual_route()
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        policy = classification.context_policy
        publish_brain_v2_failure(
            actual_route=get_actual_route(),
            intent=classification.intent.value,
            execution_strategy=execution_strategy.value,
            context_sources=(
                source
                for enabled, source in (
                    (policy.use_exact_memory, "exact_memory"),
                    (policy.use_semantic_memory, "semantic_memory"),
                    (policy.use_recent_history, "recent_history"),
                    (policy.use_last_topic, "last_topic"),
                )
                if enabled
            ),
            memory_should_store=memory_decision.should_store,
            memory_type=memory_decision.memory_type.value,
            memory_confidence=memory_decision.confidence,
            requires_plan=plan.requires_plan,
            plan_step_count=len(plan.steps),
            plan_categories=plan_categories,
            planner_confidence=plan.confidence,
            plan_valid=plan_validation.valid,
            plan_validation_status=plan_validation.status,
            unsupported_plan_categories=plan_validation.unsupported_categories,
            processing_ms=elapsed_ms,
        )
        logger.exception("Brain v2 request failed in legacy router")
        raise
    finally:
        reset_route_trace(trace_token)
        reset_active_request_context(context_token)

    processing_ms = (time.perf_counter() - started_at) * 1000
    evaluation = evaluate_response(response)
    if evaluation.success and evaluation.quality == "good":
        persistence_result = persist_project_note(normalized_command, memory_decision)
    else:
        persistence_result = MemoryPersistenceResult(
            False,
            "none",
            "skipped",
            "request evaluation was not successful",
        )
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
        "memory_persistence": {
            "persisted": persistence_result.persisted,
            "target": persistence_result.target,
            "status": persistence_result.status,
            "reason": persistence_result.reason,
        },
        "memory_persisted": persistence_result.persisted,
        "memory_persistence_target": persistence_result.target,
        "memory_persistence_status": persistence_result.status,
        "requires_plan": plan.requires_plan,
        "plan_step_count": len(plan.steps),
        "plan_categories": list(plan_categories),
        "planner_confidence": plan.confidence,
        "plan_valid": plan_validation.valid,
        "plan_validation_status": plan_validation.status,
        "unsupported_plan_categories": list(
            plan_validation.unsupported_categories
        ),
        "actual_route": actual_route,
        "processing_ms": processing_ms,
    }
    logger.debug(
        "Brain v2 request completed intent=%s strategy=%s quality=%s processing_ms=%.2f",
        metadata["intent"],
        metadata["execution_strategy"],
        metadata["evaluation"]["quality"],
        processing_ms,
    )

    result = BrainResult(
        response=response,
        intent=classification.intent,
        context_policy=classification.context_policy,
        execution_strategy=execution_strategy,
        evaluation=evaluation,
        memory_decision=memory_decision,
        memory_persisted=persistence_result.persisted,
        memory_persistence_target=persistence_result.target,
        memory_persistence_status=persistence_result.status,
        plan=plan,
        requires_plan=plan.requires_plan,
        plan_step_count=len(plan.steps),
        plan_categories=plan_categories,
        planner_confidence=plan.confidence,
        plan_validation=plan_validation,
        plan_valid=plan_validation.valid,
        plan_validation_status=plan_validation.status,
        unsupported_plan_categories=plan_validation.unsupported_categories,
        actual_route=actual_route,
        metadata=metadata,
    )
    publish_brain_v2_status(result)
    return result
