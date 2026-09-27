"""Safe process-local status for the most recent Brain v2 request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Iterable


BRAIN_VERSION = "2.0-phase7"


@dataclass(frozen=True)
class BrainV2Status:
    state: str
    brain_version: str
    timestamp: str | None
    intent: str | None
    execution_strategy: str | None
    actual_route: str | None
    context_sources: tuple[str, ...]
    evaluation_quality: str | None
    evaluation_success: bool | None
    memory_should_store: bool | None
    memory_type: str | None
    memory_confidence: float | None
    memory_persistence_status: str | None
    memory_persistence_target: str | None
    processing_ms: float | None


_status_lock = Lock()
_latest_status: BrainV2Status | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_sources(sources: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(source) for source in (sources or ()))


def _idle_status() -> BrainV2Status:
    return BrainV2Status(
        state="idle",
        brain_version=BRAIN_VERSION,
        timestamp=None,
        intent=None,
        execution_strategy=None,
        actual_route=None,
        context_sources=(),
        evaluation_quality=None,
        evaluation_success=None,
        memory_should_store=None,
        memory_type=None,
        memory_confidence=None,
        memory_persistence_status=None,
        memory_persistence_target=None,
        processing_ms=None,
    )


def get_brain_v2_status() -> BrainV2Status:
    """Return an immutable snapshot of the latest safe request summary."""

    with _status_lock:
        return _latest_status or _idle_status()


def publish_brain_v2_status(result) -> None:
    """Publish only allow-listed fields from a completed BrainResult."""

    global _latest_status

    evaluation = result.evaluation
    decision = result.memory_decision
    with _status_lock:
        _latest_status = BrainV2Status(
            state="complete",
            brain_version=BRAIN_VERSION,
            timestamp=_now(),
            intent=result.intent.value if result.intent else None,
            execution_strategy=(
                result.execution_strategy.value
                if result.execution_strategy
                else None
            ),
            actual_route=result.actual_route,
            context_sources=_safe_sources(result.metadata.get("context_sources")),
            evaluation_quality=evaluation.quality if evaluation else None,
            evaluation_success=evaluation.success if evaluation else None,
            memory_should_store=decision.should_store if decision else None,
            memory_type=decision.memory_type.value if decision else None,
            memory_confidence=decision.confidence if decision else None,
            memory_persistence_status=result.memory_persistence_status,
            memory_persistence_target=result.memory_persistence_target,
            processing_ms=result.metadata.get("processing_ms"),
        )


def publish_brain_v2_failure(
    *,
    intent: str | None,
    execution_strategy: str | None,
    context_sources: Iterable[str] = (),
    memory_should_store: bool | None = None,
    memory_type: str | None = None,
    memory_confidence: float | None = None,
    processing_ms: float | None = None,
) -> None:
    """Publish a safe failed lifecycle state without exception details."""

    global _latest_status

    with _status_lock:
        _latest_status = BrainV2Status(
            state="failed",
            brain_version=BRAIN_VERSION,
            timestamp=_now(),
            intent=intent,
            execution_strategy=execution_strategy,
            actual_route="unknown",
            context_sources=_safe_sources(context_sources),
            evaluation_quality="failed",
            evaluation_success=False,
            memory_should_store=memory_should_store,
            memory_type=memory_type,
            memory_confidence=memory_confidence,
            memory_persistence_status="skipped",
            memory_persistence_target="none",
            processing_ms=processing_ms,
        )


def format_brain_v2_status(status: BrainV2Status | None = None) -> str:
    snapshot = status or get_brain_v2_status()
    if snapshot.state == "idle":
        return f"Brain v2: {snapshot.brain_version}\nStatus: idle (no request processed yet)"

    context = ", ".join(snapshot.context_sources) if snapshot.context_sources else "none"
    evaluation = snapshot.evaluation_quality or "unknown"
    memory_type = snapshot.memory_type or "none"
    persistence = snapshot.memory_persistence_status or "not_applicable"
    processing = (
        f"{snapshot.processing_ms:.0f} ms"
        if snapshot.processing_ms is not None
        else "unknown"
    )

    return "\n".join(
        (
            f"Brain v2: {snapshot.brain_version}",
            f"Last intent: {snapshot.intent or 'unknown'}",
            f"Strategy: {snapshot.execution_strategy or 'unknown'}",
            f"Context: {context}",
            f"Evaluation: {evaluation}",
            f"Memory decision: {memory_type}",
            f"Persistence: {persistence}",
            f"Processing: {processing}",
        )
    )


def get_brain_v2_status_response() -> str:
    return format_brain_v2_status()
