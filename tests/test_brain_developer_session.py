"""Brain v2 Phase 3 approved bounded-session integration tests."""

import json
from dataclasses import replace
from pathlib import Path
import py_compile
import threading
from unittest.mock import Mock

import pytest

import api
from core import brain, developer_bridge, orchestrator
from core.brain_status_v2 import get_brain_v2_status
from core.developer_agent import developer_session
from core.developer_agent.candidate_verification import CandidateVerification
from core.developer_agent.repair_proposal import propose_repair as real_propose_repair
from core.developer_agent.tool_models import success_result
from core.developer_agent.workspace import Workspace


@pytest.fixture(autouse=True)
def _reset_approval_state():
    developer_bridge.reset_developer_approval_state()
    yield
    developer_bridge.reset_developer_approval_state()


@pytest.fixture
def isolated_workspace(monkeypatch, tmp_path):
    workspace = Workspace(tmp_path)
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: workspace)
    return workspace


class _Responses:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _patch_response(path, old_text, new_text, *, confidence=0.95):
    return json.dumps({
        "proposal_type": "patch_file",
        "path": path,
        "old_text": old_text,
        "new_text": new_text,
        "confidence": confidence,
        "reason": "The failing assertion identifies this exact repair",
    })


def _write_response(path, content):
    return json.dumps({
        "proposal_type": "write_file",
        "path": path,
        "content": content,
        "confidence": 0.95,
        "reason": "The failing assertion identifies this exact repair",
    })


def _install_model(monkeypatch, *responses):
    model = _Responses(*responses)

    def propose(request, *, workspace, model_call=None):
        return real_propose_repair(
            request,
            workspace=workspace,
            model_call=model,
        )

    monkeypatch.setattr(developer_session, "propose_repair", propose)
    return model


def _calculator(workspace, *, correct=False):
    source = workspace.root / "calculator.py"
    test = workspace.root / "test_calculator.py"
    operator = "+" if correct else "-"
    source.write_text(
        f"def add(a, b):\n    return a {operator} b\n",
        encoding="utf-8",
    )
    test.write_text(
        "from calculator import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return source, test


def _request():
    return "Fix calculator.py until test_calculator.py passes"


_EXACT_REPAIR_BENCHMARK_REQUEST = """Run a bounded developer session on /home/mnahtygal/projects/jarvis-repair-challenge.

Source file:
stock.py

Test file:
test_stock.py

Verification:
pytest -q test_stock.py

Only stock.py may be modified.
test_stock.py must remain read-only.

Ask for approval before making any change.
Do not use Git."""


def test_phase3_allowlist_is_exact():
    assert developer_bridge.PHASE3_SESSION_ALLOWLIST == frozenset({
        "developer.bounded_session",
    })


def test_exact_repair_benchmark_routes_to_bounded_session_before_execution(
    isolated_workspace,
    monkeypatch,
):
    source = isolated_workspace.root / "stock.py"
    test = isolated_workspace.root / "test_stock.py"
    source.write_text("STOCK = 1\n", encoding="utf-8")
    test.write_text(
        "from stock import STOCK\n\ndef test_stock():\n    assert STOCK == 1\n",
        encoding="utf-8",
    )
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    workspace_factory = Mock(return_value=isolated_workspace)
    executor = Mock(side_effect=AssertionError("verification must await approval"))
    bridge_executor = Mock(side_effect=AssertionError("no direct tool may run"))
    model = Mock(side_effect=AssertionError("model must await failed verification"))
    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        workspace_factory,
    )
    monkeypatch.setattr(developer_bridge, "execute_tool", bridge_executor)
    monkeypatch.setattr(developer_session, "execute_tool", executor)
    monkeypatch.setattr(developer_session, "propose_repair", model)

    parsed = developer_bridge.classify_developer_request(
        _EXACT_REPAIR_BENCHMARK_REQUEST
    )
    assert parsed.capability_id == "developer.bounded_session"
    assert parsed.capability_id != "developer.repair_loop"
    normalized = developer_bridge.classify_developer_request(
        " ".join(_EXACT_REPAIR_BENCHMARK_REQUEST.split())
    )
    assert normalized.capability_id == "developer.bounded_session"
    assert normalized.capability_id != "developer.repair_loop"
    proposed = orchestrator.process_request(_EXACT_REPAIR_BENCHMARK_REQUEST)

    assert proposed.developer_status == "confirmation_required"
    assert proposed.developer_capability_id == "developer.bounded_session"
    assert proposed.developer_tool_invoked is False
    assert proposed.metadata["llm_called"] is False
    assert developer_bridge._pending_action is not None
    assert developer_bridge._pending_action.capability_id == "developer.bounded_session"
    assert developer_bridge._pending_action.explicit_workspace is True
    workspace_factory.assert_called_once_with(
        "/home/mnahtygal/projects/jarvis-repair-challenge"
    )
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before
    assert not (isolated_workspace.root / ".git").exists()
    executor.assert_not_called()
    bridge_executor.assert_not_called()
    model.assert_not_called()


def test_exact_repair_benchmark_approval_uses_canonical_session_once(
    isolated_workspace,
    monkeypatch,
):
    source = isolated_workspace.root / "stock.py"
    test = isolated_workspace.root / "test_stock.py"
    source.write_text("STOCK = 1\n", encoding="utf-8")
    test.write_text(
        "from stock import STOCK\n\ndef test_stock():\n    assert STOCK == 1\n",
        encoding="utf-8",
    )
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    verification = Mock(return_value=success_result(
        "developer.run_command",
        "1 passed",
        metadata={"command_family": "pytest", "exit_code": 0},
    ))
    model = Mock(side_effect=AssertionError("green verification must not call model"))
    real_handler = developer_bridge.run_developer_session_request
    handler_calls = []

    def canonical_handler(request, *, workspace):
        handler_calls.append((request, workspace))
        return real_handler(request, workspace=workspace)

    monkeypatch.setattr(
        developer_bridge,
        "_workspace_from_explicit_root",
        lambda value: isolated_workspace,
    )
    monkeypatch.setattr(
        developer_bridge,
        "Workspace",
        lambda root=None: isolated_workspace,
    )
    monkeypatch.setattr(developer_session, "execute_tool", verification)
    monkeypatch.setattr(developer_session, "propose_repair", model)
    monkeypatch.setattr(
        developer_bridge,
        "run_developer_session_request",
        canonical_handler,
    )
    monkeypatch.setattr(
        developer_bridge,
        "_CANONICAL_BOUNDED_SESSION_HANDLER",
        canonical_handler,
    )

    proposed = orchestrator.process_request(_EXACT_REPAIR_BENCHMARK_REQUEST)
    assert proposed.developer_status == "confirmation_required"
    approved = orchestrator.process_request("approve")

    assert approved.developer_status == "executed_success"
    assert approved.developer_capability_id == "developer.bounded_session"
    assert approved.developer_result.verification_count == 1
    assert approved.developer_result.repair_count == 0
    assert len(handler_calls) == 1
    assert handler_calls[0][0].approved is True
    assert handler_calls[0][1] is isolated_workspace
    verification.assert_not_called()
    model.assert_not_called()
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before
    assert not (isolated_workspace.root / ".git").exists()


@pytest.mark.parametrize(
    "command",
    [
        "fix this bug",
        "repair this project",
        "why is pytest failing?",
        "run the tests",
        "patch stock.py",
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace(
            " on /home/mnahtygal/projects/jarvis-repair-challenge", ""
        ),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace("Source file:\nstock.py\n\n", ""),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace("Test file:\ntest_stock.py\n\n", ""),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace(
            "Verification:\npytest -q test_stock.py\n\n", ""
        ),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace(
            "Only stock.py may be modified.\n", ""
        ),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace(
            "pytest -q test_stock.py", "python -m pytest test_stock.py"
        ),
        _EXACT_REPAIR_BENCHMARK_REQUEST.replace(
            "Source file:\nstock.py", "Source file:\nstock.py helper.py"
        ),
    ],
)
def test_incomplete_or_ambiguous_requests_do_not_become_bounded_sessions(command):
    request = developer_bridge.classify_developer_request(command)
    assert request is None or request.capability_id != "developer.bounded_session"
    assert developer_bridge._pending_action is None


def test_valid_session_is_frozen_and_executes_only_after_approval(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    py_compile.compile(str(source), doraise=True)
    original_test = test.read_text(encoding="utf-8")
    model = _install_model(
        monkeypatch,
        _patch_response("calculator.py", "return a - b", "return a + b"),
    )

    proposed = orchestrator.process_request(_request())
    assert proposed.developer_status == "confirmation_required"
    assert proposed.developer_capability_id == "developer.bounded_session"
    assert proposed.actual_route == "developer_confirmation"
    assert source.read_text(encoding="utf-8").endswith("return a - b\n")

    approved = orchestrator.process_request("approve")
    assert approved.developer_status == "executed_success"
    assert approved.actual_route == "developer_tool"
    assert approved.developer_tool_invoked is True
    assert approved.developer_tool_success is True
    assert approved.developer_result.verification_kind == "pytest"
    assert approved.developer_result.verification_count == 2
    assert approved.developer_result.repair_count == 1
    assert approved.developer_result.proposal_count == 1
    assert approved.developer_result.candidate_repair_count == 1
    assert approved.developer_result.candidate_rejected_count == 0
    assert approved.developer_result.promoted_repair_count == 1
    assert approved.developer_result.attempt_summaries == (
        "Repair attempt 1: proposal=accepted, confidence=0.95, "
        "candidate=candidate_verification_passed, disposition=promoted, "
        "original_source_modified=yes",
    )
    assert approved.developer_result.final_state == "verification_passed"
    assert source.read_text(encoding="utf-8").endswith("return a + b\n")
    assert test.read_text(encoding="utf-8") == original_test
    assert len(model.calls) == 1
    assert not (isolated_workspace.root / ".git").exists()
    assert "Git stage, commit, and push performed: no" in approved.response
    assert "Candidate repairs attempted: 1" in approved.response
    assert "Candidate repairs rejected: 0" in approved.response
    assert "Repairs promoted to original source: 1" in approved.response

    replay = orchestrator.process_request("approve")
    assert replay.developer_error_code == "no_pending_action"


def test_isolation_failure_is_not_reported_as_a_proposal_failure():
    session = developer_session.DeveloperSessionResult(
        success=False,
        status="candidate_isolation_unavailable",
        verification_runs=0,
        proposals_generated=0,
        repairs_applied=0,
        attempts=(),
        changed_paths=(),
        stopped_reason="candidate_isolation_unavailable",
    )

    adapted = developer_bridge._adapt_session_result(
        session,
        (),
        "run_command",
    )

    assert adapted.status == "executed_failed"
    assert adapted.proposal_count == 0
    assert adapted.candidate_repair_count == 0
    assert adapted.model_invoked is False


def test_initially_green_session_verifies_once_without_model_or_mutation(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace, correct=True)
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    unexpected = Mock(side_effect=AssertionError("repair model must not run"))
    monkeypatch.setattr(developer_session, "propose_repair", unexpected)

    assert orchestrator.process_request(_request()).developer_status == "confirmation_required"
    result = orchestrator.process_request("approve")

    assert result.developer_status == "executed_success"
    assert result.developer_result.verification_count == 1
    assert result.developer_result.repair_count == 0
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before
    unexpected.assert_not_called()


def test_gradle_session_uses_only_fixed_gradle_verification(
    isolated_workspace, monkeypatch
):
    source = isolated_workspace.root / "app/src/main/Calculator.kt"
    test = isolated_workspace.root / "app/src/test/CalculatorTest.kt"
    source.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    source.write_text("class Calculator\n", encoding="utf-8")
    test.write_text("class CalculatorTest\n", encoding="utf-8")
    policy = object()
    validate = Mock(return_value=(isolated_workspace.root, policy, isolated_workspace.root))
    execute = Mock(return_value=success_result(
        "developer.gradle_test",
        "passed",
        metadata={"command_family": "gradle_test", "exit_code": 0},
    ))
    monkeypatch.setattr(developer_bridge, "validate_gradle_project", validate)
    monkeypatch.setattr(developer_session, "execute_tool", execute)
    command = (
        "Fix app/src/main/Calculator.kt using app/src/test/CalculatorTest.kt "
        "until Gradle tests pass in ."
    )

    assert orchestrator.process_request(command).developer_status == "confirmation_required"
    result = orchestrator.process_request("approve")

    assert result.developer_status == "executed_success"
    assert result.developer_result.verification_kind == "gradle_test"
    assert result.developer_result.verification_count == 1
    assert result.developer_result.repair_count == 0
    execute.assert_called_once_with(
        "developer.gradle_test",
        {"project_path": ".", "approved": True},
        workspace=isolated_workspace,
    )
    assert validate.call_count == 2


def test_two_repairs_then_green_never_exceeds_hard_limits(
    isolated_workspace, monkeypatch
):
    source = isolated_workspace.root / "calculator.py"
    test = isolated_workspace.root / "test_calculator.py"
    source.write_text("FIRST = 0\nSECOND = 0\n", encoding="utf-8")
    test.write_text(
        "from calculator import FIRST, SECOND\n\n"
        "def test_values():\n"
        "    assert FIRST == 1\n"
        "    assert SECOND == 2\n",
        encoding="utf-8",
    )
    model = _install_model(
        monkeypatch,
        _patch_response("calculator.py", "FIRST = 0", "FIRST = 1"),
        _patch_response(
            "calculator.py",
            "FIRST = 0\nSECOND = 0",
            "FIRST = 1\nSECOND = 2",
        ),
    )

    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")

    assert result.developer_status == "executed_success"
    assert result.developer_result.verification_count == 3
    assert result.developer_result.repair_count == 1
    assert result.developer_result.candidate_repair_count == 2
    assert result.developer_result.candidate_rejected_count == 1
    assert result.developer_result.promoted_repair_count == 1
    assert len(model.calls) == 2


def test_two_failed_repairs_stop_without_third_mutation(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    test_before = test.read_bytes()
    model = _install_model(
        monkeypatch,
        _patch_response("calculator.py", "return a - b", "return a * b"),
        _patch_response("calculator.py", "return a - b", "return a // b"),
    )

    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")

    assert result.developer_status == "repair_limit"
    assert result.developer_result.final_state == "repair_limit"
    assert result.developer_result.verification_count == 3
    assert result.developer_result.repair_count == 0
    assert result.developer_result.candidate_repair_count == 2
    assert result.developer_result.candidate_rejected_count == 2
    assert len(model.calls) == 2
    assert source.read_text(encoding="utf-8").endswith("return a - b\n")
    assert test.read_bytes() == test_before
    assert "Modified paths: none" in result.response


def test_test_file_proposal_is_rejected_without_test_mutation(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    _install_model(
        monkeypatch,
        _patch_response(
            "test_calculator.py",
            "assert add(2, 3) == 5",
            "assert add(2, 3) == -1",
        ),
    )

    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")

    assert result.developer_status == "executed_failed"
    assert result.developer_error_code == "proposal_outside_mutation_scope"
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before


def test_write_file_proposal_against_test_is_rejected_without_mutation(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    _install_model(
        monkeypatch,
        _write_response("test_calculator.py", "def test_add():\n    assert True\n"),
    )

    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")

    assert result.developer_tool_success is False
    assert result.developer_result.repair_count == 0
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before


def test_model_failure_and_low_confidence_fail_without_mutation(
    isolated_workspace, monkeypatch
):
    source, _ = _calculator(isolated_workspace)
    before = source.read_bytes()
    monkeypatch.setattr(
        developer_session,
        "propose_repair",
        Mock(side_effect=RuntimeError("offline")),
    )
    orchestrator.process_request(_request())
    offline = orchestrator.process_request("approve")
    assert offline.developer_status == "proposal_failed"
    assert offline.developer_error_code == "model_failure"
    assert source.read_bytes() == before

    model = _install_model(
        monkeypatch,
        _patch_response(
            "calculator.py",
            "return a - b",
            "return a + b",
            confidence=0.5,
        ),
    )
    orchestrator.process_request(_request())
    low = orchestrator.process_request("approve")
    assert low.developer_status == "proposal_failed"
    assert low.developer_error_code == "low_confidence"
    assert source.read_bytes() == before
    assert len(model.calls) == 1


def test_malformed_out_of_scope_and_inexact_proposals_do_not_mutate(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    before = source.read_bytes()

    malformed_model = _install_model(monkeypatch, "not json", "still not json")
    orchestrator.process_request(_request())
    malformed = orchestrator.process_request("approve")
    assert malformed.developer_status == "proposal_failed"
    assert malformed.developer_result.repair_count == 0
    assert len(malformed_model.calls) == 2
    assert source.read_bytes() == before

    outside_model = _install_model(
        monkeypatch,
        _patch_response("new.py", "missing", "replacement"),
    )
    orchestrator.process_request(_request())
    outside = orchestrator.process_request("approve")
    assert outside.developer_tool_success is False
    assert outside.developer_result.repair_count == 0
    assert len(outside_model.calls) >= 1
    assert not (isolated_workspace.root / "new.py").exists()
    assert source.read_bytes() == before

    exact_model = _install_model(
        monkeypatch,
        _patch_response("calculator.py", "not present", "replacement"),
    )
    orchestrator.process_request(_request())
    exact = orchestrator.process_request("approve")
    assert exact.developer_tool_success is False
    assert exact.developer_result.repair_count == 0
    assert len(exact_model.calls) >= 1
    assert source.read_bytes() == before
    assert test.exists()


def test_unsupported_and_protected_model_proposals_fail_closed(
    isolated_workspace, monkeypatch
):
    source, test = _calculator(isolated_workspace)
    before = (source.read_bytes(), test.read_bytes())
    unsupported = json.dumps({
        "proposal_type": "delete_file",
        "path": "calculator.py",
        "confidence": 0.99,
        "reason": "unsupported",
    })
    model = _install_model(monkeypatch, unsupported, unsupported)

    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")

    assert result.developer_status == "proposal_failed"
    assert result.developer_result.repair_count == 0
    assert len(model.calls) == 2
    assert (source.read_bytes(), test.read_bytes()) == before

    protected_model = _install_model(
        monkeypatch,
        _patch_response(".git/config", "old", "new"),
    )
    orchestrator.process_request(_request())
    protected = orchestrator.process_request("approve")
    assert protected.developer_tool_success is False
    assert protected.developer_result.repair_count == 0
    assert len(protected_model.calls) >= 1
    assert not (isolated_workspace.root / ".git").exists()
    assert (source.read_bytes(), test.read_bytes()) == before


def test_stale_scope_protected_paths_and_ambiguous_requests_fail_closed(
    isolated_workspace
):
    source, _ = _calculator(isolated_workspace)
    assert orchestrator.process_request(_request()).developer_status == "confirmation_required"
    source.write_text("def add(a, b):\n    return 999\n", encoding="utf-8")
    stale = orchestrator.process_request("approve")
    assert stale.developer_status == "validation_failed"
    assert stale.developer_tool_invoked is False

    for command in (
        "Fix ../calculator.py until test_calculator.py passes",
        "Fix testbrain.py until test_calculator.py passes",
        "Fix one.py and two.py until test_one.py passes",
        "Fix calculator.py until test_calculator.py passes using tox",
        "Run the approved bounded repair session",
    ):
        refused = orchestrator.process_request(command)
        assert refused.developer_tool_invoked is False
        assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_test_file_change_after_confirmation_invalidates_session(
    isolated_workspace
):
    source, test = _calculator(isolated_workspace, correct=True)
    source_before = source.read_bytes()
    assert orchestrator.process_request(_request()).developer_status == "confirmation_required"
    test.write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 6\n",
        encoding="utf-8",
    )

    result = orchestrator.process_request("approve")

    assert result.developer_status == "validation_failed"
    assert result.developer_tool_invoked is False
    assert source.read_bytes() == source_before


def test_approval_payload_cannot_expand_scope_or_limits(isolated_workspace):
    _calculator(isolated_workspace, correct=True)
    (isolated_workspace.root / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    parsed = developer_bridge.classify_developer_request(_request())
    request = parsed.arguments["request"]
    changes = (
        {"allowed_mutation_paths": ("calculator.py", "test_calculator.py")},
        {
            "candidate_files": (
                "calculator.py",
                "helper.py",
                "test_calculator.py",
            ),
            "allowed_mutation_paths": ("calculator.py", "helper.py"),
        },
        {"max_repairs": developer_session.MAX_SESSION_REPAIRS + 1},
        {
            "max_verification_runs":
                developer_session.MAX_SESSION_VERIFICATION_RUNS + 1,
        },
        {
            "max_proposal_requests":
                developer_session.MAX_SESSION_PROPOSAL_REQUESTS + 1,
        },
    )

    for change in changes:
        crafted = developer_bridge.DeveloperRequest(
            developer_bridge.DEVELOPER_CONFIRMATION_REQUIRED,
            "developer.bounded_session",
            {"request": replace(request, **change)},
        )
        proposed = developer_bridge.execute_developer_request(crafted)
        assert proposed.status == "validation_failed"
        assert proposed.tool_invoked is False
        assert developer_bridge.execute_developer_request(
            developer_bridge.DeveloperRequest(developer_bridge.DEVELOPER_APPROVAL)
        ).error_code == "no_pending_action"


def test_parser_requires_distinct_supported_source_and_test_files(
    isolated_workspace
):
    _calculator(isolated_workspace, correct=True)
    for command in (
        "Fix calculator.py until calculator.py passes",
        "Fix calculator.txt until test_calculator.txt passes",
        "Fix app/src/main/Calculator.txt using app/src/test/CalculatorTest.txt "
        "until Gradle tests pass in .",
    ):
        result = orchestrator.process_request(command)
        assert result.developer_tool_invoked is False
        assert developer_bridge.execute_developer_request(
            developer_bridge.DeveloperRequest(developer_bridge.DEVELOPER_APPROVAL)
        ).error_code == "no_pending_action"


def test_missing_workspace_fails_safely(monkeypatch):
    monkeypatch.setattr(
        developer_bridge,
        "Workspace",
        Mock(side_effect=ValueError("missing workspace")),
    )
    result = orchestrator.process_request(_request())
    assert result.developer_status == "validation_failed"
    assert result.developer_error_code == "workspace_unavailable"
    assert result.developer_tool_invoked is False


def test_phase3_registry_or_handler_drift_fails_closed(
    isolated_workspace, monkeypatch
):
    _calculator(isolated_workspace, correct=True)
    orchestrator.process_request(_request())
    real = developer_bridge.get_tool("developer.bounded_session")
    monkeypatch.setattr(
        developer_bridge,
        "get_tool",
        lambda tool_id: type(real)(
            real.tool_id,
            real.description,
            real.read_only,
            real.mutating,
            real.requires_confirmation,
            real.enabled,
            True,
        ),
    )
    metadata = orchestrator.process_request("approve")
    assert metadata.developer_status == "policy_blocked"
    assert metadata.developer_tool_invoked is False

    monkeypatch.undo()
    monkeypatch.setattr(developer_bridge, "Workspace", lambda: isolated_workspace)
    orchestrator.process_request(_request())
    monkeypatch.setattr(
        developer_bridge,
        "run_developer_session_request",
        Mock(),
    )
    handler = orchestrator.process_request("approve")
    assert handler.developer_error_code == "capability_not_dispatchable"
    assert handler.developer_tool_invoked is False


def test_session_approval_cancel_expiry_interruption_and_replacement(
    isolated_workspace, monkeypatch
):
    _calculator(isolated_workspace, correct=True)
    monkeypatch.setattr(orchestrator, "route", lambda command: "ordinary answer")

    orchestrator.process_request(_request())
    assert orchestrator.process_request("yes").developer_error_code == "approval_not_recognized"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"

    orchestrator.process_request(_request())
    assert orchestrator.process_request("cancel").developer_status == "cancelled"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"

    orchestrator.process_request(_request())
    assert orchestrator.process_request("What time is it?").developer_error_code == "approval_not_recognized"
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"

    other = isolated_workspace.root / "other.py"
    other_test = isolated_workspace.root / "test_other.py"
    other.write_text("VALUE = 1\n", encoding="utf-8")
    other_test.write_text(
        "from other import VALUE\n\ndef test_value():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    orchestrator.process_request(_request())
    second = "Fix other.py until test_other.py passes"
    assert orchestrator.process_request(second).developer_status == "confirmation_required"
    (isolated_workspace.root / "calculator.py").write_text(
        "def add(a, b):\n    return 999\n",
        encoding="utf-8",
    )
    assert orchestrator.process_request("approve").developer_status == "executed_success"


def test_expired_session_never_executes(isolated_workspace, monkeypatch):
    _calculator(isolated_workspace, correct=True)
    clock = iter((100.0, 100.0 + developer_bridge.PENDING_ACTION_TTL_SECONDS + 1))
    monkeypatch.setattr(developer_bridge.time, "monotonic", lambda: next(clock))
    orchestrator.process_request(_request())
    result = orchestrator.process_request("approve")
    assert result.developer_status == "expired"
    assert result.developer_tool_invoked is False


def test_two_concurrent_session_approvals_execute_at_most_once(
    isolated_workspace, monkeypatch
):
    _calculator(isolated_workspace, correct=True)
    started = threading.Event()
    release = threading.Event()
    results = []

    def verify_candidate(**kwargs):
        started.set()
        assert release.wait(timeout=5)
        return CandidateVerification(
            "candidate_verification_passed",
            success_result(
                "developer.run_command",
                "passed",
                metadata={"command_family": "pytest", "exit_code": 0},
            ),
            None,
            None,
            True,
        )

    monkeypatch.setattr(
        developer_session,
        "verify_disposable_candidate",
        verify_candidate,
    )
    orchestrator.process_request(_request())
    first = threading.Thread(
        target=lambda: results.append(orchestrator.process_request("approve")),
        daemon=True,
    )
    first.start()
    assert started.wait(timeout=5)
    second = orchestrator.process_request("approve")
    release.set()
    first.join(timeout=5)

    assert not first.is_alive()
    assert len(results) == 1
    assert results[0].developer_tool_invoked is True
    assert second.developer_tool_invoked is False
    assert second.developer_error_code == "no_pending_action"


def test_phase3_status_and_memory_are_payload_free(isolated_workspace, monkeypatch):
    _calculator(isolated_workspace, correct=True)
    remember_user = Mock()
    remember_assistant = Mock()
    monkeypatch.setattr(brain, "remember_user_message", remember_user)
    monkeypatch.setattr(brain, "remember_assistant_message", remember_assistant)

    brain.think(_request())
    brain.think("approve")
    status = get_brain_v2_status()

    assert status.developer_capability_id == "developer.bounded_session"
    assert status.developer_verification_kind == "pytest"
    assert status.developer_repair_count == 0
    assert status.developer_verification_count == 1
    assert status.developer_final_state == "verification_passed"
    assert "calculator.py" not in repr(status)
    assert "return a + b" not in repr(status)
    remember_user.assert_not_called()
    remember_assistant.assert_not_called()


def test_text_and_ask_api_remain_string_compatible(isolated_workspace, monkeypatch):
    _calculator(isolated_workspace, correct=True)
    monkeypatch.setattr(brain, "remember_user_message", Mock())
    monkeypatch.setattr(brain, "remember_assistant_message", Mock())
    client = api.app.test_client()

    proposed = client.post("/text", json={"command": _request()})
    approved = client.post("/text", json={"command": "approve"})
    assert proposed.status_code == approved.status_code == 200
    assert isinstance(proposed.get_json()["response"], str)
    assert "Bounded developer session passed" in approved.get_json()["response"]

    heard = iter((_request(), "approve"))
    monkeypatch.setattr(api, "listen_command", lambda: next(heard))
    proposed = client.post("/ask", json={"use_voice": False})
    approved = client.post("/ask", json={"use_voice": False})
    assert proposed.status_code == approved.status_code == 200
    assert isinstance(approved.get_json()["response"], str)


def test_phase3_does_not_make_internal_repair_capabilities_approval_executable(
    monkeypatch
):
    execute = Mock(side_effect=AssertionError("internal capability must not run"))
    monkeypatch.setattr(developer_bridge, "execute_tool", execute)
    for command in ("Repair the failing test", "Propose a repair"):
        proposed = orchestrator.process_request(command)
        assert proposed.developer_status == "confirmation_required"
        assert "no approval is pending" in proposed.response
        assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"
    execute.assert_not_called()


def test_no_git_command_is_introduced_by_phase3_source():
    source = Path(developer_bridge.__file__).read_text(encoding="utf-8")
    session_source = Path(developer_session.__file__).read_text(encoding="utf-8")
    forbidden = (
        "git add",
        "git commit",
        "git push",
        "git reset",
        "git restore",
        "git checkout",
    )
    assert all(command not in session_source for command in forbidden)
    assert "developer.git_stage" not in session_source
    assert "developer.git_commit" not in session_source
    assert "subprocess" not in source
