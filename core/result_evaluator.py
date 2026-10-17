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


def evaluate_developer_result(result: object) -> EvaluationResult:
    """Evaluate the fixed Developer bridge lifecycle without inspecting output."""

    status = getattr(result, "status", None)
    if status in {"executed", "executed_success"} and getattr(result, "tool_success", None) is True:
        return EvaluationResult(True, "good", "developer tool execution succeeded")
    if status == "confirmation_required":
        return EvaluationResult(
            False,
            "confirmation_required",
            "developer request stopped for confirmation",
        )
    if status == "cancelled":
        return EvaluationResult(
            False,
            "cancelled",
            "pending developer action was cancelled",
        )
    if status == "expired":
        return EvaluationResult(
            False,
            "expired",
            "pending developer action expired",
        )
    if status in {
        "policy_blocked",
        "validation_failed",
        "rejected",
        "executed_failed",
        "repair_limit",
        "verification_limit",
        "proposal_failed",
        "truthfulness_blocked",
    }:
        return EvaluationResult(
            False,
            "failed",
            "developer tool validation or policy failure",
        )
    if status == "unsupported":
        return EvaluationResult(
            False,
            "unsupported",
            "developer request is ambiguous or unsupported",
        )
    return EvaluationResult(
        False,
        "failed",
        "developer tool validation or policy failure",
    )
