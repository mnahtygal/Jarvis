from unittest.mock import Mock

import pytest

from core import orchestrator
from core.brain_request_context import get_active_request_context
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.plan_validator import validate_plan
from core.planner import PlanResult, PlanStep, analyze_plan
from core.route_trace import get_actual_route


def _plan(*steps: PlanStep, requires_plan: bool = True) -> PlanResult:
    return PlanResult(
        requires_plan=requires_plan,
        steps=steps,
        confidence=0.9,
        reason="test plan",
    )


@pytest.mark.parametrize(
    "command",
    [
        "check Jarvis health and then tell me what model is running",
        "capture an image and analyze what is on the workbench",
    ],
)
def test_generated_multistep_plans_are_valid(command):
    result = validate_plan(analyze_plan(command))

    assert result.valid is True
    assert result.status == "valid"
    assert 2 <= result.step_count <= 5
    assert result.unsupported_categories == ()


def test_no_plan_is_valid_and_not_required():
    result = validate_plan(analyze_plan("hello"))

    assert result.valid is True
    assert result.status == "not_required"
    assert result.step_count == 0


def test_one_step_plan_is_rejected():
    result = validate_plan(_plan(PlanStep(1, "inspect state", "system")))

    assert result.valid is False
    assert result.status == "too_few_steps"


def test_six_step_plan_is_rejected():
    steps = tuple(
        PlanStep(index, f"step {index}", "system")
        for index in range(1, 7)
    )

    result = validate_plan(_plan(*steps))

    assert result.valid is False
    assert result.status == "too_many_steps"
    assert result.step_count == 6


def test_unknown_category_is_unsupported():
    result = validate_plan(_plan(
        PlanStep(1, "inspect state", "unknown"),
        PlanStep(2, "summarize result", "summary"),
    ))

    assert result.valid is False
    assert result.status == "unsupported_category"
    assert result.unsupported_categories == ("unknown",)


def test_malformed_step_order_is_rejected():
    result = validate_plan(_plan(
        PlanStep(1, "inspect state", "system"),
        PlanStep(3, "summarize result", "summary"),
    ))

    assert result.valid is False
    assert result.status == "invalid_order"


def test_duplicate_step_is_rejected():
    result = validate_plan(_plan(
        PlanStep(1, "inspect state", "system"),
        PlanStep(2, "inspect state", "system"),
    ))

    assert result.valid is False
    assert result.status == "duplicate_step"


def test_empty_action_is_malformed():
    result = validate_plan(_plan(
        PlanStep(1, "", "system"),
        PlanStep(2, "summarize result", "summary"),
    ))

    assert result.valid is False
    assert result.status == "malformed"


def test_validator_is_side_effect_free(monkeypatch):
    unexpected = Mock(side_effect=AssertionError("validator called a dependency"))
    monkeypatch.setattr("core.db.get_connection", unexpected)
    monkeypatch.setattr("skills.llm_skill.ask_local_llm", unexpected)
    monkeypatch.setattr("skills.camera_skill.capture_snapshot", unexpected)
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", unexpected)
    monkeypatch.setattr(orchestrator, "route", unexpected)

    result = validate_plan(analyze_plan(
        "capture an image and analyze what is on the workbench"
    ))

    assert result.valid is True
    assert unexpected.call_count == 0


def test_invalid_plan_does_not_change_router_execution(monkeypatch):
    invalid = _plan(PlanStep(1, "inspect state", "system"))
    routed = Mock(return_value="  unchanged response text  ")
    monkeypatch.setattr(orchestrator, "analyze_plan", lambda command: invalid)
    monkeypatch.setattr(orchestrator, "route", routed)

    result = orchestrator.process_request("test command")

    routed.assert_called_once_with("test command")
    assert result.response == "  unchanged response text  "
    assert result.plan_valid is False
    assert result.plan_validation_status == "too_few_steps"
    assert result.metadata["plan_validation_status"] == "too_few_steps"
    assert get_actual_route() == "unknown"
    assert get_active_request_context() is None


def test_status_exposes_only_safe_validation_metadata(monkeypatch):
    command = "private command content"
    response = "private response content"
    invalid = _plan(
        PlanStep(1, "private internal action", "unknown"),
        PlanStep(2, "summarize result", "summary"),
    )
    monkeypatch.setattr(orchestrator, "analyze_plan", lambda value: invalid)
    monkeypatch.setattr(orchestrator, "route", lambda value: response)

    orchestrator.process_request(command)
    status = get_brain_v2_status()
    rendered = get_brain_v2_status_response()

    assert status.plan_valid is False
    assert status.plan_validation_status == "unsupported_category"
    assert status.unsupported_plan_categories == ("unknown",)
    assert "Plan validation: unsupported_category" in rendered
    assert command not in repr(status)
    assert response not in repr(status)
    assert "private internal action" not in repr(status)
    assert command not in rendered
    assert response not in rendered
    assert "private internal action" not in rendered
