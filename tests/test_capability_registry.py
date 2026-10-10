from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from core import orchestrator, router
from core.brain_request_context import get_active_request_context
from core.brain_status_v2 import get_brain_v2_status, get_brain_v2_status_response
from core.capability_registry import (
    capabilities_for_category,
    get_capabilities_response,
    get_capability,
    is_capability_available,
    list_capabilities,
    resolve_plan_step_capabilities,
)
from core.plan_validator import SUPPORTED_PLAN_CATEGORIES, validate_plan
from core.planner import PlanResult, PlanStep, analyze_plan
from core.route_trace import get_actual_route


EXPECTED_CAPABILITY_IDS = (
    "memory.recall_exact",
    "memory.search_semantic",
    "memory.write_explicit",
    "runtime.health",
    "runtime.identity",
    "runtime.active_model",
    "runtime.brain_status",
    "system.status",
    "system.time",
    "camera.status",
    "camera.capture",
    "vision.describe",
    "vision.measure",
    "help.docs",
    "llm.respond",
    "developer.list_files",
    "developer.read_file",
    "developer.git_status",
    "developer.write_file",
    "developer.patch_file",
    "developer.run_command",
    "developer.repair_loop",
)


def _plan(*steps: PlanStep) -> PlanResult:
    return PlanResult(True, steps, 0.9, "test plan")


def test_registry_contains_only_unique_fixed_capabilities():
    capabilities = list_capabilities()
    capability_ids = tuple(item.capability_id for item in capabilities)

    assert isinstance(capabilities, tuple)
    assert capability_ids == EXPECTED_CAPABILITY_IDS
    assert len(capability_ids) == len(set(capability_ids))
    assert all(item.category in SUPPORTED_PLAN_CATEGORIES for item in capabilities)
    with pytest.raises(FrozenInstanceError):
        capabilities[0].enabled = False


def test_registry_lookup_and_category_filter_are_safe():
    runtime = capabilities_for_category("runtime")

    assert get_capability("runtime.health") in runtime
    assert get_capability("missing.capability") is None
    assert get_capability(None) is None
    assert capabilities_for_category("missing") == ()
    assert is_capability_available("runtime.health") is True
    assert is_capability_available("missing.capability") is False
    assert get_capability("runtime.health").executable is True
    assert get_capability("memory.write_explicit").executable is False
    assert get_capability("camera.capture").executable is False
    assert get_capability("vision.measure").executable is False
    assert get_capability("developer.list_files").read_only is True
    assert get_capability("developer.read_file").read_only is True
    assert get_capability("developer.git_status").read_only is True
    write_file = get_capability("developer.write_file")
    patch_file = get_capability("developer.patch_file")
    run_command = get_capability("developer.run_command")
    repair_loop = get_capability("developer.repair_loop")
    assert (
        write_file.enabled
        is patch_file.enabled
        is run_command.enabled
        is repair_loop.enabled
        is True
    )
    assert (
        write_file.executable
        is patch_file.executable
        is run_command.executable
        is repair_loop.executable
        is False
    )
    assert (
        write_file.read_only
        is patch_file.read_only
        is run_command.read_only
        is repair_loop.read_only
        is False
    )
    assert (
        write_file.mutating
        is patch_file.mutating
        is run_command.mutating
        is repair_loop.mutating
        is True
    )
    assert (
        write_file.requires_confirmation
        is patch_file.requires_confirmation
        is run_command.requires_confirmation
        is repair_loop.requires_confirmation
        is True
    )


@pytest.mark.parametrize(
    "step,expected",
    [
        (PlanStep(1, "check runtime health", "runtime"), ("runtime.health",)),
        (PlanStep(1, "inspect active model", "system"), ("runtime.active_model",)),
        (PlanStep(1, "capture image", "camera"), ("camera.capture",)),
        (PlanStep(1, "analyze captured image", "vision"), ("vision.describe",)),
        (PlanStep(1, "retrieve relevant memory", "memory"), ("memory.search_semantic",)),
        (PlanStep(1, "write file", "developer"), ()),
        (PlanStep(1, "run tests", "developer"), ()),
        (PlanStep(1, "repair code", "developer"), ()),
        (PlanStep(1, "unsupported action", "system"), ()),
    ],
)
def test_fixed_plan_step_resolution(step, expected):
    assert resolve_plan_step_capabilities(step) == expected


def test_fully_supported_plan_is_execution_ready():
    validation = validate_plan(analyze_plan(
        "check Jarvis health and then tell me what model is running"
    ))

    assert validation.valid is True
    assert validation.execution_ready is True
    assert validation.capabilities_resolved == (
        "runtime.health",
        "runtime.active_model",
        "llm.respond",
    )
    assert validation.unsupported_capabilities == ()
    assert validation.unresolved_step_count == 0


def test_no_plan_is_not_execution_ready():
    validation = validate_plan(analyze_plan("hello"))

    assert validation.valid is True
    assert validation.status == "not_required"
    assert validation.execution_ready is False
    assert validation.capabilities_resolved == ()


def test_unresolved_step_prevents_execution_readiness():
    validation = validate_plan(_plan(
        PlanStep(1, "unsupported action", "system"),
        PlanStep(2, "summarize result", "summary"),
    ))

    assert validation.valid is True
    assert validation.execution_ready is False
    assert validation.capabilities_resolved == ("llm.respond",)
    assert validation.unresolved_step_count == 1


def test_unknown_capability_prevents_execution_readiness(monkeypatch):
    monkeypatch.setattr(
        "core.plan_validator.resolve_plan_step_capabilities",
        lambda step: ("missing.capability",),
    )

    validation = validate_plan(_plan(
        PlanStep(1, "inspect state", "system"),
        PlanStep(2, "summarize result", "summary"),
    ))

    assert validation.valid is True
    assert validation.execution_ready is False
    assert validation.unsupported_capabilities == ("missing.capability",)


def test_manual_only_capability_prevents_execution_readiness():
    validation = validate_plan(analyze_plan(
        "capture an image and analyze what is on the workbench"
    ))

    assert validation.valid is True
    assert validation.execution_ready is False
    assert "camera.capture" in validation.unsupported_capabilities


def test_registry_and_resolution_have_no_external_calls(monkeypatch):
    unexpected = Mock(side_effect=AssertionError("registry called a dependency"))
    monkeypatch.setattr("core.db.get_connection", unexpected)
    monkeypatch.setattr("skills.llm_skill.ask_local_llm", unexpected)
    monkeypatch.setattr("skills.camera_skill.capture_snapshot", unexpected)
    monkeypatch.setattr("core.semantic_memory.search_semantic_memories", unexpected)
    monkeypatch.setattr(orchestrator, "route", unexpected)

    assert list_capabilities()
    assert get_capability("runtime.health") is not None
    assert resolve_plan_step_capabilities(
        PlanStep(1, "check runtime health", "runtime")
    ) == ("runtime.health",)
    assert "runtime.health" in get_capabilities_response()
    assert unexpected.call_count == 0


def test_readiness_is_observe_only_and_router_runs_once(monkeypatch):
    routed = Mock(return_value="  unchanged response text  ")
    monkeypatch.setattr(orchestrator, "route", routed)

    result = orchestrator.process_request(
        "check Jarvis health and then tell me what model is running"
    )

    routed.assert_called_once_with(
        "check Jarvis health and then tell me what model is running"
    )
    assert result.response == "  unchanged response text  "
    assert result.plan_execution_ready is True
    assert result.plan_capabilities == (
        "runtime.health",
        "runtime.active_model",
        "llm.respond",
    )
    assert get_actual_route() == "unknown"
    assert get_active_request_context() is None


@pytest.mark.parametrize("command", ["brain capabilities", "jarvis capabilities"])
def test_capabilities_command_is_deterministic_and_safe(monkeypatch, command):
    llm = Mock(side_effect=AssertionError("unexpected LLM call"))
    monkeypatch.setattr(router, "get_llm_response", llm)

    expected = get_capabilities_response()
    response = router.route(command)

    assert response == expected == get_capabilities_response()
    assert response.startswith("Jarvis Brain v2 capabilities:")
    assert "memory.write_explicit [manual-only]" in response
    assert "runtime.health [future-executable]" in response
    assert "no capabilities are executed" in response
    llm.assert_not_called()


def test_capabilities_command_uses_one_router_call(monkeypatch):
    routed = Mock(wraps=router.route)
    monkeypatch.setattr(orchestrator, "route", routed)

    result = orchestrator.process_request("brain capabilities")

    routed.assert_called_once_with("brain capabilities")
    assert result.response == get_capabilities_response()
    assert result.intent.value == "help_or_docs"
    assert result.actual_route == "help_docs"


def test_status_exposes_only_capability_ids_and_readiness(monkeypatch):
    command = "check Jarvis health and then tell me what model is running"
    response = "private response content"
    monkeypatch.setattr(orchestrator, "route", lambda value: response)

    orchestrator.process_request(command)
    status = get_brain_v2_status()
    rendered = get_brain_v2_status_response()

    assert status.plan_capabilities == (
        "runtime.health",
        "runtime.active_model",
        "llm.respond",
    )
    assert status.plan_execution_ready is True
    assert "Capabilities: runtime.health, runtime.active_model, llm.respond" in rendered
    assert "Execution ready: yes" in rendered
    assert command not in repr(status)
    assert response not in repr(status)
    assert command not in rendered
    assert response not in rendered
