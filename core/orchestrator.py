"""Brain v2 request orchestration.

Phase 3 keeps the existing router as the execution boundary while applying
request-scoped context policy during LLM context assembly.
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
from core.request_classifier import ContextPolicy, RequestIntent, classify_request
from core.router import route


logger = logging.getLogger(__name__)

BRAIN_VERSION = "2.0-phase3"


@dataclass
class BrainResult:
    """Structured result returned by the Brain v2 orchestration layer."""

    response: str
    route_type: str = "legacy_router"
    intent: RequestIntent | None = None
    context_policy: ContextPolicy | None = None
    used_llm: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def process_request(command: str) -> BrainResult:
    """Process a command through the existing router.

    Phase 3 deliberately does not own session persistence, memory writes, or
    LLM calls. Those responsibilities remain in the existing brain, router,
    and skill layers.
    """

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    normalized_command = command.strip()
    started_at = time.perf_counter()
    classification = classify_request(normalized_command)
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
        "processing_ms": processing_ms,
    }
    logger.debug(
        "Brain v2 request completed route_type=%s command_length=%d processing_ms=%.2f",
        metadata["route_type"],
        metadata["command_length"],
        processing_ms,
    )

    return BrainResult(
        response=response,
        intent=classification.intent,
        context_policy=classification.context_policy,
        metadata=metadata,
    )
