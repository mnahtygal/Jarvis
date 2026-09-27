"""Safe response-level evaluation for Brain v2 results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    success: bool
    quality: str
    reason: str


_DEGRADED_RESPONSE_PREFIXES = (
    "My local brain returned nothing useful from llama.cpp or Ollama.",
    "Sorry Marty, I had trouble reaching both local brains.",
    "Sorry Marty, both local brain paths failed.",
)


def evaluate_response(response: object) -> EvaluationResult:
    """Evaluate only response shape and known safe failure messages."""

    if not isinstance(response, str) or not response.strip():
        return EvaluationResult(False, "failed", "empty response")

    if response.startswith(_DEGRADED_RESPONSE_PREFIXES):
        return EvaluationResult(False, "degraded", "local model fallback failure")

    return EvaluationResult(True, "good", "non-empty response")
