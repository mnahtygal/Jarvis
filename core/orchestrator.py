"""Brain v2 request orchestration.

Phase 1 keeps the existing router as the execution boundary while providing a
stable place for future planning, context, and diagnostics work.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from core.router import route


logger = logging.getLogger(__name__)

BRAIN_VERSION = "2.0-phase1"


@dataclass
class BrainResult:
    """Structured result returned by the Brain v2 orchestration layer."""

    response: str
    route_type: str = "legacy_router"
    intent: str | None = None
    used_llm: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def process_request(command: str) -> BrainResult:
    """Process a command through the existing router.

    Phase 1 deliberately does not own session persistence, memory writes, or
    LLM calls. Those responsibilities remain in the existing brain, router,
    and skill layers.
    """

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    normalized_command = command.strip()
    started_at = time.perf_counter()

    try:
        response = route(normalized_command)
    except Exception:
        logger.exception("Brain v2 request failed in legacy router")
        raise

    processing_ms = (time.perf_counter() - started_at) * 1000
    metadata = {
        "command_length": len(normalized_command),
        "route_type": "legacy_router",
        "processing_ms": processing_ms,
    }
    logger.debug(
        "Brain v2 request completed route_type=%s command_length=%d processing_ms=%.2f",
        metadata["route_type"],
        metadata["command_length"],
        processing_ms,
    )

    return BrainResult(response=response, metadata=metadata)
