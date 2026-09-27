"""Deterministic observe-only validation for Brain v2 plans."""

from __future__ import annotations

from dataclasses import dataclass

from core.planner import PlanResult, PlanStep


SUPPORTED_PLAN_CATEGORIES = frozenset({
    "memory",
    "runtime",
    "system",
    "camera",
    "vision",
    "llm",
    "comparison",
    "summary",
})


@dataclass(frozen=True)
class PlanValidationResult:
    valid: bool
    status: str
    unsupported_categories: tuple[str, ...]
    step_count: int
    reason: str


def _result(
    valid: bool,
    status: str,
    step_count: int,
    reason: str,
    unsupported_categories: tuple[str, ...] = (),
) -> PlanValidationResult:
    return PlanValidationResult(
        valid=valid,
        status=status,
        unsupported_categories=unsupported_categories,
        step_count=step_count,
        reason=reason,
    )


def validate_plan(plan: PlanResult) -> PlanValidationResult:
    """Validate plan structure without executing or mutating the plan."""

    if not isinstance(plan, PlanResult):
        return _result(False, "malformed", 0, "plan result is malformed")

    if plan.requires_plan is False:
        step_count = len(plan.steps) if isinstance(plan.steps, tuple) else 0
        return _result(True, "not_required", step_count, "plan not required")

    if plan.requires_plan is not True or not isinstance(plan.steps, tuple):
        return _result(False, "malformed", 0, "plan structure is malformed")

    step_count = len(plan.steps)
    if step_count < 2:
        return _result(False, "too_few_steps", step_count, "plan has too few steps")
    if step_count > 5:
        return _result(False, "too_many_steps", step_count, "plan has too many steps")

    for step in plan.steps:
        if not isinstance(step, PlanStep):
            return _result(False, "malformed", step_count, "plan step is malformed")
        if not isinstance(step.order, int) or isinstance(step.order, bool):
            return _result(False, "malformed", step_count, "plan step is malformed")
        if not isinstance(step.action, str) or not step.action.strip():
            return _result(False, "malformed", step_count, "plan step is malformed")
        if not isinstance(step.category, str):
            return _result(False, "malformed", step_count, "plan step is malformed")

    expected_order = tuple(range(1, step_count + 1))
    actual_order = tuple(step.order for step in plan.steps)
    if actual_order != expected_order:
        return _result(False, "invalid_order", step_count, "plan order is invalid")

    unsupported = tuple(
        dict.fromkeys(
            step.category
            for step in plan.steps
            if step.category not in SUPPORTED_PLAN_CATEGORIES
        )
    )
    if unsupported:
        return _result(
            False,
            "unsupported_category",
            step_count,
            "plan contains unsupported categories",
            unsupported,
        )

    identities = tuple((step.action, step.category) for step in plan.steps)
    if len(set(identities)) != len(identities):
        return _result(
            False,
            "duplicate_step",
            step_count,
            "plan contains duplicate steps",
        )

    if (
        not isinstance(plan.confidence, (int, float))
        or isinstance(plan.confidence, bool)
        or not 0.0 <= plan.confidence <= 1.0
        or not isinstance(plan.reason, str)
        or not plan.reason.strip()
    ):
        return _result(False, "malformed", step_count, "plan metadata is malformed")

    return _result(True, "valid", step_count, "plan structure is valid")
