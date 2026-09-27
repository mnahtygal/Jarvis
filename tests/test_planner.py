from unittest.mock import Mock

import pytest

from core import orchestrator
from core.brain_request_context import get_active_request_context
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.planner import PLAN_CATEGORIES, analyze_plan
from core.route_trace import get_actual_route


@pytest.mark.parametrize(
    "command,categories",
    [
        (
            "check Jarvis health and then tell me what model is running",
            ("runtime", "system", "summary"),
        ),
        (
            "capture an image and analyze what is on the workbench",
            ("camera", "vision", "summary"),
        ),
        (
            "show me what Jarvis remembers about Thor and compare it with the current runtime",
            ("memory", "runtime", "comparison", "summary"),
        ),
    ],
)
def test_multistep_examples_produce_bounded_fixed_plans(command, categories):
    first = analyze_plan(command)
    second = analyze_plan(command)

    assert first == second
    assert first.requires_plan is True
    assert 2 <= len(first.steps) <= 5
    assert tuple(step.order for step in first.steps) == tuple(range(1, len(first.steps) + 1))
    assert tuple(step.category for step in first.steps) == categories
    assert all(step.category in PLAN_CATEGORIES for step in first.steps)
    assert all(step.action and len(step.action) <= 32 for step in first.steps)
    assert 0.0 <= first.confidence <= 1.0


@pytest.mark.parametrize(
    "command",
    [
        "what is PostgreSQL",
        "brain status",
        "hello",
        "what is my favorite ship",
        "PostgreSQL and Python are useful",
    ],
)
def test_single_step_examples_do_not_produce_plan(command):
    plan = analyze_plan(command)

    assert plan.requires_plan is False
    assert plan.steps == ()
    assert plan.reason == "single-step request"


def test_planner_is_side_effect_free_and_router_runs_once(monkeypatch):
    unexpected = Mock(side_effect=AssertionError("planner invoked an external dependency"))
    monkeypatch.setattr("core.db.get_connection", unexpected)
    monkeypatch.setattr("skills.llm_skill.ask_local_llm", unexpected)
    monkeypatch.setattr("skills.camera_skill.capture_snapshot", unexpected)
    monkeypatch.setattr("core.semantic_memory.add_semantic_memory", unexpected)
    routed = Mock(return_value="  unchanged response text  ")
    monkeypatch.setattr(orchestrator, "route", routed)

    command = "capture an image and analyze what is on the workbench"
    result = orchestrator.process_request(command)

    routed.assert_called_once_with(command)
    assert result.response == "  unchanged response text  "
    assert result.requires_plan is True
    assert result.plan_step_count == 3
    assert result.plan_categories == ("camera", "vision", "summary")
    assert result.metadata["plan_categories"] == ["camera", "vision", "summary"]
    assert unexpected.call_count == 0
    assert get_actual_route() == "unknown"
    assert get_active_request_context() is None


def test_planner_metadata_is_safe_in_status(monkeypatch):
    command = "check Jarvis health and then tell me what model is running"
    response = "private assistant response"
    monkeypatch.setattr(orchestrator, "route", lambda value: response)

    orchestrator.process_request(command)
    status = get_brain_v2_status()
    rendered = get_brain_v2_status_response()

    assert status.requires_plan is True
    assert status.plan_step_count == 3
    assert status.plan_categories == ("runtime", "system", "summary")
    assert "Planner: required" in rendered
    assert "Plan steps: 3" in rendered
    assert "Plan categories: runtime, system, summary" in rendered
    assert command not in repr(status)
    assert response not in repr(status)
    assert command not in rendered
    assert response not in rendered


def test_route_exception_keeps_plan_diagnostics_and_resets_context(monkeypatch):
    error = RuntimeError("private route failure")
    monkeypatch.setattr(
        orchestrator,
        "route",
        lambda command: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError) as caught:
        orchestrator.process_request(
            "capture an image and analyze what is on the workbench"
        )

    assert caught.value is error
    status = get_brain_v2_status()
    assert status.state == "failed"
    assert status.requires_plan is True
    assert status.plan_categories == ("camera", "vision", "summary")
    assert str(error) not in repr(status)
    assert get_actual_route() == "unknown"
    assert get_active_request_context() is None
