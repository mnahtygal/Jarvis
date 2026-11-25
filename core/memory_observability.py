"""Privacy-safe, request-scoped semantic memory retrieval diagnostics."""

from __future__ import annotations

import math
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


SEMANTIC_MEMORY_SIMILARITY_THRESHOLD = 0.50

_SAFE_CATEGORY_LABELS = frozenset(
    {
        "cruise",
        "hardware",
        "personal",
        "preference",
        "project",
        "runtime",
        "test",
        "unknown",
        "work",
    }
)


@dataclass(frozen=True)
class MemoryRetrievalDiagnostics:
    status: str
    results_examined: int = 0
    results_selected: int = 0
    selected_memory_ids: tuple[int | None, ...] = ()
    selected_weighted_similarity_scores: tuple[float | None, ...] = ()
    similarity_threshold: float = SEMANTIC_MEMORY_SIMILARITY_THRESHOLD
    category_labels: tuple[str, ...] = ()

    def to_safe_dict(self) -> dict[str, Any]:
        """Return the allow-listed diagnostics representation."""

        return {
            "status": self.status,
            "results_examined": self.results_examined,
            "results_selected": self.results_selected,
            "selected_memory_ids": list(self.selected_memory_ids),
            "selected_weighted_similarity_scores": list(
                self.selected_weighted_similarity_scores
            ),
            "similarity_threshold": self.similarity_threshold,
            "category_labels": list(self.category_labels),
        }


_ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS: ContextVar[
    MemoryRetrievalDiagnostics | None
] = ContextVar(
    "jarvis_memory_retrieval_diagnostics",
    default=None,
)


def begin_memory_retrieval_diagnostics(
    *,
    semantic_memory_permitted: bool,
) -> Token:
    """Start one request-local diagnostic lifecycle."""

    status = "not_run" if semantic_memory_permitted else "disabled"
    return _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.set(
        MemoryRetrievalDiagnostics(status=status)
    )


def reset_memory_retrieval_diagnostics(token: Token) -> None:
    _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.reset(token)


def get_memory_retrieval_diagnostics() -> MemoryRetrievalDiagnostics | None:
    return _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.get()


def _safe_memory_id(value: Any) -> int | None:
    return value if type(value) is int else None


def _safe_category(value: Any) -> str:
    if type(value) is str and value in _SAFE_CATEGORY_LABELS:
        return value
    return "unknown"


def record_memory_retrieval_result(
    *,
    results_examined: int,
    selected_results: list[tuple[dict[str, Any], float]],
    similarity_threshold: float = SEMANTIC_MEMORY_SIMILARITY_THRESHOLD,
) -> None:
    """Replace the latest snapshot, keeping one slot per selected result."""

    current = _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.get()
    if current is None or current.status == "disabled":
        return

    _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.set(
        MemoryRetrievalDiagnostics(
            status="matched" if selected_results else "no_matches",
            results_examined=results_examined,
            results_selected=len(selected_results),
            selected_memory_ids=tuple(
                _safe_memory_id(item.get("id")) for item, _ in selected_results
            ),
            selected_weighted_similarity_scores=tuple(
                score if math.isfinite(score) else None for _, score in selected_results
            ),
            similarity_threshold=float(similarity_threshold),
            category_labels=tuple(
                _safe_category(item.get("category")) for item, _ in selected_results
            ),
        )
    )


def record_memory_retrieval_error(
    *,
    similarity_threshold: float,
    results_examined: int = 0,
) -> None:
    """Record a payload-free retrieval or result-processing failure."""

    current = _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.get()
    if current is None or current.status == "disabled":
        return
    _ACTIVE_MEMORY_RETRIEVAL_DIAGNOSTICS.set(
        MemoryRetrievalDiagnostics(
            status="error",
            results_examined=results_examined,
            similarity_threshold=float(similarity_threshold),
        )
    )
