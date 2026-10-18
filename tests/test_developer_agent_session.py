from dataclasses import FrozenInstanceError, fields
import importlib
import json
from pathlib import Path

import pytest

from core.developer_agent import Workspace
from core.developer_agent.developer_session import (
    MAX_MUTATION_PATHS,
    MAX_SESSION_PROPOSAL_REQUESTS,
    MAX_SESSION_REPAIRS,
    MAX_SESSION_VERIFICATION_RUNS,
    DeveloperSessionAttempt,
    DeveloperSessionRequest,
    DeveloperSessionResult,
    build_diagnostic_excerpt,
    run_bounded_developer_session,
    run_developer_session_request,
)
from core.developer_agent.executor import execute_tool as real_execute_tool
from core.developer_agent.repair_proposal import MAX_FAILURE_OUTPUT_BYTES
from core.developer_agent.tool_models import ToolResult


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def _source(tmp_path: Path, text: str = "VALUE = 1\n") -> Path:
    path = tmp_path / "example.py"
    path.write_text(text, encoding="utf-8")
    return path


def _request(**changes) -> DeveloperSessionRequest:
    values = {
        "verification_argv": ("pytest", "-q", "test_example.py"),
        "candidate_files": ("example.py",),
        "allowed_mutation_paths": ("example.py",),
        "approved": True,
        "max_repairs": MAX_SESSION_REPAIRS,
        "max_verification_runs": MAX_SESSION_VERIFICATION_RUNS,
        "max_proposal_requests": MAX_SESSION_PROPOSAL_REQUESTS,
    }
    values.update(changes)
    return DeveloperSessionRequest(**values)


def _verification(
    success: bool,
    output: str = "failure",
    *,
    error_code: str | None = None,
    exit_code: int | None = None,
    timed_out: bool = False,
    output_truncated: bool = False,
) -> ToolResult:
    return ToolResult(
        success,
        "developer.run_command",
        output,
        error_code=error_code,
        metadata={
            "exit_code": 0 if success and exit_code is None else exit_code,
            "timed_out": timed_out,
            "output_truncated": output_truncated,
        },
    )


def _patch_response(
    *,
    path: str = "example.py",
    old_text: str = "VALUE = 1",
    new_text: str = "VALUE = 2",
    confidence: float = 0.95,
) -> str:
    return json.dumps({
        "proposal_type": "patch_file",
        "path": path,
        "old_text": old_text,
        "new_text": new_text,
        "confidence": confidence,
        "reason": "The assertion identifies the incorrect value",
    })


def _write_response(path: str = "created.py") -> str:
    return json.dumps({
        "proposal_type": "write_file",
        "path": path,
        "content": "VALUE = 2\n",
        "confidence": 0.95,
        "reason": "The missing module is required by the test",
    })


class _Responses:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system_prompt: str, user_prompt: str) -> object:
        self.calls.append((system_prompt, user_prompt))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _ScriptedExecutor:
    def __init__(self, verifications: list[ToolResult], *, mutation=None) -> None:
        self.verifications = list(verifications)
        self.mutation = mutation
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, tool_id, arguments, *, workspace):
        self.calls.append((tool_id, dict(arguments)))
        if tool_id == "developer.run_command":
            return self.verifications.pop(0)
        if self.mutation is not None:
            return self.mutation(tool_id, arguments, workspace=workspace)
        return ToolResult(True, tool_id, "applied", metadata={"path": arguments["path"]})


def test_missing_approval_does_no_work_even_with_invalid_scope(tmp_path):
    def unexpected(*args, **kwargs):
        raise AssertionError("no executor or model call is allowed")

    result = run_bounded_developer_session(
        ["not", "a", "tuple"],
        ("../outside.py",),
        (".env",),
        approved=False,
        workspace=_workspace(tmp_path),
        model_call=unexpected,
        _executor=unexpected,
    )

    assert result.status == "approval_required"
    assert result.verification_runs == result.proposals_generated == 0
    assert result.repairs_applied == 0
    assert result.attempts == result.changed_paths == ()


def test_initial_verification_passes_without_proposal_or_mutation(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([_verification(True)])
    model = _Responses(AssertionError("model must not run"))

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=model,
        _executor=executor,
    )

    assert result.success is True
    assert result.status == "verification_passed"
    assert result.verification_runs == 1
    assert result.proposals_generated == result.repairs_applied == 0
    assert [call[0] for call in executor.calls] == ["developer.run_command"]
    assert model.calls == []


def test_realistic_one_repair_session_reaches_green(tmp_path):
    source = _source(tmp_path, "def answer():\n    return 41\n")
    (tmp_path / "test_example.py").write_text(
        "from example import answer\n\ndef test_answer():\n    assert answer() == 420\n",
        encoding="utf-8",
    )
    model = _Responses(_patch_response(old_text="return 41", new_text="return 420"))

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=model,
    )

    assert result.success is True
    assert result.verification_runs == 2
    assert result.proposals_generated == result.repairs_applied == 1
    assert result.changed_paths == ("example.py",)
    assert source.read_text(encoding="utf-8") == "def answer():\n    return 420\n"
    assert len(model.calls) == 1
    assert tuple(attempt.mutation_status for attempt in result.attempts) == (
        "applied",
        None,
    )
    assert not (tmp_path / ".git").exists()


def test_realistic_two_repair_session_uses_new_state_and_failure(tmp_path):
    source = _source(tmp_path, "FIRST = 0\nSECOND = 0\n")
    (tmp_path / "test_example.py").write_text(
        "from example import FIRST, SECOND\n\n"
        "def test_values():\n"
        "    assert FIRST == 111\n"
        "    assert SECOND == 222\n",
        encoding="utf-8",
    )
    model = _Responses(
        _patch_response(old_text="FIRST = 0", new_text="FIRST = 111"),
        _patch_response(old_text="SECOND = 0", new_text="SECOND = 222"),
    )

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=model,
    )

    assert result.success is True
    assert result.verification_runs == 3
    assert result.proposals_generated == result.repairs_applied == 2
    assert source.read_text(encoding="utf-8") == "FIRST = 111\nSECOND = 222\n"
    assert len(model.calls) == 2
    assert "FIRST = 111" in model.calls[1][1]
    assert "SECOND == 222" in model.calls[1][1]


def test_hard_repair_limit_stops_before_third_proposal(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, "failure one", error_code="command_failed", exit_code=1),
        _verification(False, "failure two", error_code="command_failed", exit_code=1),
        _verification(False, "failure three", error_code="command_failed", exit_code=1),
    ], mutation=real_execute_tool)
    model = _Responses(
        _patch_response(),
        _patch_response(old_text="VALUE = 2", new_text="VALUE = 3"),
        AssertionError("third proposal is forbidden"),
    )

    result = run_developer_session_request(
        _request(), workspace=_workspace(tmp_path), model_call=model, _executor=executor
    )

    assert result.status == "repair_limit"
    assert result.verification_runs == 3
    assert result.proposals_generated == result.repairs_applied == 2
    assert len(model.calls) == 2


def test_caller_lower_verification_limit_is_enforced(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(max_verification_runs=2),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response()),
        _executor=executor,
    )

    assert result.status == "verification_limit"
    assert result.verification_runs == 2
    assert result.repairs_applied == result.proposals_generated == 1


def test_caller_lower_proposal_request_limit_is_enforced(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(max_proposal_requests=1),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response()),
        _executor=executor,
    )

    assert result.status == "proposal_request_limit"
    assert result.proposals_generated == result.repairs_applied == 1


@pytest.mark.parametrize(
    "change,status",
    [
        ({"max_repairs": MAX_SESSION_REPAIRS + 1}, "invalid_repair_limit"),
        ({"max_verification_runs": MAX_SESSION_VERIFICATION_RUNS + 1}, "invalid_verification_limit"),
        ({"max_proposal_requests": MAX_SESSION_PROPOSAL_REQUESTS + 1}, "invalid_proposal_limit"),
    ],
)
def test_caller_cannot_raise_hard_limits(tmp_path, change, status):
    _source(tmp_path)

    result = run_developer_session_request(
        _request(**change),
        workspace=_workspace(tmp_path),
        _executor=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    assert result.status == status
    assert result.verification_runs == 0


@pytest.mark.parametrize(
    "response,status",
    [
        (json.dumps({"proposal_type": "no_fix", "confidence": 0.2, "reason": "insufficient"}), "no_fix"),
        (RuntimeError("backend detail must not escape"), "model_failure"),
        (_patch_response(confidence=0.69), "low_confidence"),
    ],
)
def test_no_fix_model_failure_and_low_confidence_never_mutate(
    tmp_path, response, status
):
    source = _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=_Responses(response),
        _executor=executor,
    )

    assert result.status == status
    assert result.repairs_applied == 0
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert [call[0] for call in executor.calls] == ["developer.run_command"]


def test_readable_candidate_without_mutation_approval_is_rejected(tmp_path):
    _source(tmp_path)
    (tmp_path / "other.py").write_text("VALUE = 1\n", encoding="utf-8")
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(
            candidate_files=("example.py", "other.py"),
            allowed_mutation_paths=("example.py",),
        ),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response(path="other.py")),
        _executor=executor,
    )

    assert result.status == "proposal_outside_mutation_scope"
    assert result.repairs_applied == 0
    assert [call[0] for call in executor.calls] == ["developer.run_command"]


@pytest.mark.parametrize(
    "path",
    [
        "testbrain.py",
        "audio_pipeline_tester.py",
        ".env",
        "credentials.json",
        ".git/config",
        "../outside.py",
        "/tmp/outside.py",
        "*.py",
        ".",
    ],
)
def test_unsafe_static_scope_is_rejected_before_execution(tmp_path, path):
    _source(tmp_path)
    executor = _ScriptedExecutor([])

    result = run_developer_session_request(
        _request(candidate_files=(path,)),
        workspace=_workspace(tmp_path),
        _executor=executor,
    )

    assert result.success is False
    assert result.verification_runs == 0
    assert executor.calls == []


def test_unsafe_symlink_scope_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside-session.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "example.py").symlink_to(outside)

    result = run_developer_session_request(
        _request(), workspace=_workspace(tmp_path)
    )

    assert result.status == "unsafe_scope_symlink"
    assert result.verification_runs == 0


@pytest.mark.parametrize(
    "proposed_path",
    ("testbrain.py", "audio_pipeline_tester.py", ".env"),
)
def test_model_cannot_introduce_protected_or_unlisted_candidate(
    tmp_path, proposed_path
):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response(path=proposed_path)),
        _executor=executor,
    )

    assert result.status == "path_not_a_candidate"
    assert result.repairs_applied == 0


def test_verification_policy_rejection_stops_before_model_or_read(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, "safe refusal", error_code="python_form_not_allowed"),
    ])
    model = _Responses(AssertionError("model must not run"))

    result = run_developer_session_request(
        _request(), workspace=_workspace(tmp_path), model_call=model, _executor=executor
    )

    assert result.status == "verification_policy_rejected"
    assert result.proposals_generated == result.repairs_applied == 0
    assert model.calls == []


def test_malformed_proposal_uses_only_phase6_bounded_retry(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])
    model = _Responses("not json", "still not json")

    result = run_developer_session_request(
        _request(), workspace=_workspace(tmp_path), model_call=model, _executor=executor
    )

    assert result.status == "json_parse_failed"
    assert result.proposals_generated == 1
    assert result.repairs_applied == 0
    assert len(model.calls) == 2


def test_stale_proposal_conversion_stops_without_mutation(tmp_path, monkeypatch):
    _source(tmp_path)
    session_module = importlib.import_module("core.developer_agent.developer_session")
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])
    monkeypatch.setattr(session_module, "proposal_to_predefined_repair", lambda *a, **k: None)

    result = session_module.run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response()),
        _executor=executor,
    )

    assert result.status == "stale_or_invalid_proposal"
    assert result.repairs_applied == 0
    assert [call[0] for call in executor.calls] == ["developer.run_command"]


@pytest.mark.parametrize(
    "response,error_code",
    [
        (_patch_response(), "match_mismatch"),
        (_write_response(), "target_exists"),
    ],
)
def test_patch_and_write_mutation_rejection_stop(tmp_path, response, error_code):
    _source(tmp_path)
    if "created.py" in response:
        candidates = ("example.py", "created.py")
        allowed = ("created.py",)
    else:
        candidates = allowed = ("example.py",)

    def reject(tool_id, arguments, *, workspace):
        return ToolResult(False, tool_id, "safe refusal", error_code=error_code)

    executor = _ScriptedExecutor(
        [_verification(False, error_code="command_failed", exit_code=1)],
        mutation=reject,
    )
    result = run_developer_session_request(
        _request(candidate_files=candidates, allowed_mutation_paths=allowed),
        workspace=_workspace(tmp_path),
        model_call=_Responses(response),
        _executor=executor,
    )

    assert result.status == "mutation_rejected"
    assert result.repairs_applied == 0


def test_operational_mutation_failure_stops_without_reverification(tmp_path):
    _source(tmp_path)

    def fail_write(tool_id, arguments, *, workspace):
        return ToolResult(False, tool_id, "safe failure", error_code="write_failed")

    executor = _ScriptedExecutor(
        [_verification(False, error_code="command_failed", exit_code=1)],
        mutation=fail_write,
    )
    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response()),
        _executor=executor,
    )

    assert result.status == "mutation_failed"
    assert result.verification_runs == 1
    assert result.repairs_applied == 0


def test_new_file_succeeds_only_at_exact_preauthorized_path(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
        _verification(True),
    ], mutation=real_execute_tool)

    result = run_developer_session_request(
        _request(
            candidate_files=("example.py", "created.py"),
            allowed_mutation_paths=("created.py",),
        ),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_write_response()),
        _executor=executor,
    )

    assert result.success is True
    assert result.changed_paths == ("created.py",)
    assert (tmp_path / "created.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_unapproved_new_file_destination_is_rejected(tmp_path):
    _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
    ])

    result = run_developer_session_request(
        _request(
            candidate_files=("example.py", "created.py"),
            allowed_mutation_paths=("example.py",),
        ),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_write_response()),
        _executor=executor,
    )

    assert result.status == "proposal_outside_mutation_scope"
    assert not (tmp_path / "created.py").exists()


def test_timeout_after_mutation_leaves_authorized_change_and_does_not_rollback(tmp_path):
    source = _source(tmp_path)
    executor = _ScriptedExecutor([
        _verification(False, error_code="command_failed", exit_code=1),
        _verification(False, "timed out", error_code="timeout", timed_out=True),
    ], mutation=real_execute_tool)

    result = run_developer_session_request(
        _request(),
        workspace=_workspace(tmp_path),
        model_call=_Responses(_patch_response()),
        _executor=executor,
    )

    assert result.status == "verification_timeout"
    assert result.repairs_applied == 1
    assert result.changed_paths == ("example.py",)
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert "VALUE = 1" not in repr(result)
    assert "VALUE = 2" not in repr(result)
    assert all(not call[0].startswith("developer.git_") for call in executor.calls)


def test_verification_command_and_candidate_scope_are_frozen_across_cycles(tmp_path):
    _source(tmp_path)
    command = ("pytest", "-q", "test_example.py")
    executor = _ScriptedExecutor([
        _verification(False, "first diagnostic", error_code="command_failed", exit_code=1),
        _verification(False, "second diagnostic", error_code="command_failed", exit_code=1),
        _verification(True),
    ], mutation=real_execute_tool)
    model = _Responses(
        _patch_response(),
        _patch_response(old_text="VALUE = 2", new_text="VALUE = 3"),
    )

    result = run_developer_session_request(
        _request(verification_argv=command),
        workspace=_workspace(tmp_path),
        model_call=model,
        _executor=executor,
    )

    assert result.success is True
    assert [call[1]["argv"] for call in executor.calls if call[0] == "developer.run_command"] == [
        command,
        command,
        command,
    ]
    assert all('"candidate_files":["example.py"]' in call[1] for call in model.calls)
    assert "first diagnostic" in model.calls[0][1]
    assert "second diagnostic" in model.calls[1][1]


def test_large_diagnostic_is_deterministic_bounded_and_marks_truncation():
    output = "BEGIN-" + ("🙂" * 6000) + "-END"
    verification = _verification(
        False,
        output,
        error_code="command_failed",
        exit_code=1,
    )

    first = build_diagnostic_excerpt(verification)
    second = build_diagnostic_excerpt(verification)

    assert first == second
    assert first.truncated is True
    assert len(first.text.encode("utf-8")) <= MAX_FAILURE_OUTPUT_BYTES
    assert first.text.startswith("BEGIN-")
    assert first.text.endswith("-END")
    assert "diagnostic truncated" in first.text


def test_upstream_truncation_metadata_is_preserved_without_output_payload_in_result(tmp_path):
    _source(tmp_path)
    secret_output = "SECRET FAILURE PAYLOAD"
    executor = _ScriptedExecutor([
        _verification(
            False,
            secret_output,
            error_code="command_failed",
            exit_code=1,
            output_truncated=True,
        ),
    ])
    model = _Responses(json.dumps({
        "proposal_type": "no_fix",
        "confidence": 0.1,
        "reason": "insufficient",
    }))

    result = run_developer_session_request(
        _request(), workspace=_workspace(tmp_path), model_call=model, _executor=executor
    )

    assert "diagnostic_truncated=true" in model.calls[0][1]
    assert secret_output not in repr(result)
    assert not hasattr(result, "failure_output")
    assert not hasattr(result.attempts[0], "reason")


def test_result_models_are_immutable_and_contain_only_safe_fields():
    attempt = DeveloperSessionAttempt(1, "failed", None, None, None, None, None)
    result = DeveloperSessionResult(False, "failed", 1, 0, 0, (attempt,), (), "failed")

    with pytest.raises(FrozenInstanceError):
        result.status = "changed"
    with pytest.raises(FrozenInstanceError):
        attempt.verification_status = "changed"
    assert {item.name for item in fields(DeveloperSessionResult)} == {
        "success",
        "status",
        "verification_runs",
        "proposals_generated",
        "repairs_applied",
        "attempts",
        "changed_paths",
        "stopped_reason",
    }


def test_duplicate_and_excess_mutation_scopes_fail_before_execution(tmp_path):
    _source(tmp_path)
    duplicates = run_developer_session_request(
        _request(allowed_mutation_paths=("example.py", "example.py")),
        workspace=_workspace(tmp_path),
    )
    for index in range(MAX_MUTATION_PATHS):
        (tmp_path / f"file_{index}.py").write_text("", encoding="utf-8")
    excess = run_developer_session_request(
        _request(
            allowed_mutation_paths=tuple(
                f"file_{index}.py" for index in range(MAX_MUTATION_PATHS)
            ) + ("example.py",)
        ),
        workspace=_workspace(tmp_path),
    )

    assert duplicates.status == "duplicate_scope_path"
    assert excess.status == "invalid_mutation_path_count"
    assert duplicates.verification_runs == excess.verification_runs == 0


def test_session_source_has_no_direct_execution_git_persistence_or_autonomy_wiring():
    root = Path(__file__).parents[1]
    source = (root / "core/developer_agent/developer_session.py").read_text(encoding="utf-8")
    autonomous = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "core/planner.py",
            "core/plan_validator.py",
            "core/router.py",
            "core/orchestrator.py",
            "core/brain_status_v2.py",
        )
    )

    assert "subprocess" not in source
    assert "os.system" not in source
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
    assert ".open(" not in source
    assert "developer.git_stage" not in source
    assert "developer.git_commit" not in source
    assert "git push" not in source
    assert "git reset" not in source
    assert "git restore" not in source
    assert "git checkout" not in source
    assert "unlink(" not in source
    assert "core.memory" not in source
    assert "semantic_memory" not in source
    assert "developer.bounded_session" not in autonomous


def test_capability_is_manual_only_and_not_an_executor_tool():
    from core.capability_registry import get_capability, resolve_plan_step_capabilities
    from core.planner import PlanStep

    capability = get_capability("developer.bounded_session")
    assert capability.enabled is True
    assert capability.read_only is False
    assert capability.mutating is True
    assert capability.requires_confirmation is True
    assert capability.executable is False
    assert resolve_plan_step_capabilities(
        PlanStep(1, "run bounded session", "developer")
    ) == ()
    assert real_execute_tool("developer.bounded_session", {}).error_code == "unknown_tool"
