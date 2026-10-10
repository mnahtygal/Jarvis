from dataclasses import FrozenInstanceError
import importlib
from pathlib import Path

import pytest

from core.developer_agent import Workspace
from core.developer_agent.repair_loop import (
    ALLOWED_REPAIR_TOOL_IDS,
    MAX_REPAIR_ATTEMPTS,
    MAX_VERIFICATION_RUNS,
    RepairAttempt,
    RepairResult,
    run_repair_loop,
)
from core.developer_agent.tool_models import ToolResult


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def _patch(path: str, old_text: str, new_text: str) -> dict[str, object]:
    return {
        "tool": "developer.patch_file",
        "arguments": {
            "path": path,
            "old_text": old_text,
            "new_text": new_text,
            "expected_matches": 1,
        },
    }


def _tool_result(
    success: bool,
    *,
    tool: str = "developer.run_command",
    error_code: str | None = None,
    exit_code: int | None = None,
    output: str = "bounded diagnostic",
) -> ToolResult:
    return ToolResult(
        success,
        tool,
        output,
        error_code=error_code,
        metadata={"exit_code": exit_code},
    )


def test_initial_verification_success_applies_no_repairs(tmp_path):
    result = run_repair_loop(
        ["pwd"],
        [_patch("unused.py", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.status == "verification_passed"
    assert result.verification_runs == 1
    assert result.repairs_attempted == 0
    assert result.patches_applied == 0
    assert result.attempts == (
        RepairAttempt(1, "developer.run_command", True, 0, False, "verification_passed"),
    )


def test_broken_fixture_is_patched_and_reverification_passes(tmp_path):
    source = tmp_path / "example.py"
    test_file = tmp_path / "test_example.py"
    source.write_text("VALUE = 10\n", encoding="utf-8")
    test_file.write_text(
        "from example import VALUE\n\ndef test_value():\n    assert VALUE == 200\n",
        encoding="utf-8",
    )

    result = run_repair_loop(
        ["python", "-m", "pytest", "-q", "test_example.py"],
        [
            _patch("example.py", "VALUE = 10", "VALUE = 200"),
            _patch("example.py", "VALUE = 200", "VALUE = 3000"),
        ],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.status == "verification_passed"
    assert result.verification_runs == 2
    assert result.repairs_attempted == 1
    assert result.patches_applied == 1
    assert tuple(attempt.status for attempt in result.attempts) == (
        "repair_applied",
        "verification_passed",
    )
    assert source.read_text(encoding="utf-8") == "VALUE = 200\n"


def test_multiple_predefined_repairs_run_one_at_a_time_until_success(tmp_path):
    source = tmp_path / "example.py"
    test_file = tmp_path / "test_example.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text(
        "from example import VALUE\n\ndef test_value():\n    assert VALUE == 333\n",
        encoding="utf-8",
    )

    result = run_repair_loop(
        ["pytest", "-q", "test_example.py"],
        [
            _patch("example.py", "VALUE = 1", "VALUE = 22"),
            _patch("example.py", "VALUE = 22", "VALUE = 333"),
        ],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.verification_runs == 3
    assert result.patches_applied == 2
    assert source.read_text(encoding="utf-8") == "VALUE = 333\n"


def test_persistent_failure_stops_at_attempt_limit(tmp_path):
    source = tmp_path / "example.py"
    test_file = tmp_path / "test_example.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text(
        "from example import VALUE\n\ndef test_value():\n    assert VALUE == 99\n",
        encoding="utf-8",
    )

    result = run_repair_loop(
        ["pytest", "-q", "test_example.py"],
        [
            _patch("example.py", "VALUE = 1", "VALUE = 2"),
            _patch("example.py", "VALUE = 2", "VALUE = 3"),
            _patch("example.py", "VALUE = 3", "VALUE = 4"),
        ],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.status == result.stopped_reason == "attempt_limit"
    assert result.verification_runs == MAX_VERIFICATION_RUNS == 4
    assert result.repairs_attempted == MAX_REPAIR_ATTEMPTS == 3
    assert result.patches_applied == 3


def test_no_available_repair_stops_after_failed_verification(tmp_path):
    (tmp_path / "test_fail.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )

    result = run_repair_loop(
        ["pytest", "-q", "test_fail.py"],
        [],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "no_repair_available"
    assert result.verification_runs == 1
    assert result.patches_applied == 0


def test_policy_rejected_repair_stops_immediately(tmp_path):
    protected = tmp_path / ".env"
    protected.write_text("VALUE=old\n", encoding="utf-8")
    (tmp_path / "test_fail.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )

    result = run_repair_loop(
        ["pytest", "-q", "test_fail.py"],
        [_patch(".env", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "repair_rejected"
    assert result.verification_runs == 1
    assert result.repairs_attempted == 1
    assert result.patches_applied == 0
    assert protected.read_text(encoding="utf-8") == "VALUE=old\n"


def test_repair_tool_failure_stops_without_reverification(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    calls: list[str] = []

    def fake_execute(tool_id, arguments, *, workspace):
        calls.append(tool_id)
        if tool_id == "developer.run_command":
            return _tool_result(False, error_code="command_failed", exit_code=1)
        return _tool_result(False, tool=tool_id, error_code="write_failed")

    monkeypatch.setattr(repair_module, "execute_tool", fake_execute)

    result = run_repair_loop(
        ["pytest", "test_sample.py"],
        [_patch("example.py", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "repair_failed"
    assert calls == ["developer.run_command", "developer.patch_file"]
    assert result.verification_runs == 1


def test_verification_timeout_stops_before_repair(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    calls: list[str] = []

    def fake_execute(tool_id, arguments, *, workspace):
        calls.append(tool_id)
        return _tool_result(False, error_code="timeout")

    monkeypatch.setattr(repair_module, "execute_tool", fake_execute)

    result = run_repair_loop(
        ["pytest", "test_sample.py"],
        [_patch("example.py", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "verification_timeout"
    assert calls == ["developer.run_command"]
    assert result.repairs_attempted == result.patches_applied == 0


def test_rejected_verification_uses_phase3_policy_and_never_mutates(tmp_path):
    source = tmp_path / "example.py"
    source.write_text("old\n", encoding="utf-8")

    result = run_repair_loop(
        ["python", "-c", "print('not allowed')"],
        [_patch("example.py", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "verification_policy_rejected"
    assert result.repairs_attempted == result.patches_applied == 0
    assert source.read_text(encoding="utf-8") == "old\n"


def test_missing_approval_performs_no_tool_calls(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")

    def unexpected(*args, **kwargs):
        raise AssertionError("executor must not be called")

    monkeypatch.setattr(repair_module, "execute_tool", unexpected)

    result = run_repair_loop(
        ["pwd"],
        [_patch("example.py", "old", "new")],
        approved=False,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "approval_required"
    assert result.attempts == ()
    assert result.verification_runs == result.repairs_attempted == 0


def test_duplicate_repair_is_never_applied_twice(tmp_path):
    source = tmp_path / "example.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "test_example.py").write_text(
        "from example import VALUE\n\ndef test_value():\n    assert VALUE == 3\n",
        encoding="utf-8",
    )
    duplicate = _patch("example.py", "VALUE = 1", "VALUE = 2")

    result = run_repair_loop(
        ["pytest", "-q", "test_example.py"],
        [duplicate, duplicate],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "duplicate_repair"
    assert result.repairs_attempted == 1
    assert result.patches_applied == 1
    assert source.read_text(encoding="utf-8") == "VALUE = 2\n"


def test_more_than_hard_maximum_repairs_is_rejected_without_execution(
    tmp_path,
    monkeypatch,
):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    monkeypatch.setattr(
        repair_module,
        "execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected call")),
    )

    result = run_repair_loop(
        ["pwd"],
        [_patch(f"file-{index}.py", "old", "new") for index in range(4)],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "too_many_repairs"
    assert result.verification_runs == result.repairs_attempted == 0


def test_unknown_repair_tool_is_rejected_without_execution(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    monkeypatch.setattr(
        repair_module,
        "execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected call")),
    )

    result = run_repair_loop(
        ["pwd"],
        [{"tool": "developer.git_status", "arguments": {}}],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "unknown_repair_tool"


@pytest.mark.parametrize(
    "repair,expected_status",
    [
        ({"tool": "developer.patch_file", "arguments": {}, "extra": True}, "invalid_repair"),
        ({"tool": "developer.patch_file", "arguments": {"path": "x"}}, "invalid_repair_arguments"),
        ({"tool": "developer.write_file", "arguments": {"path": "x", "content": "x", "mode": 0o777}}, "invalid_repair_arguments"),
    ],
)
def test_malformed_or_unknown_repair_fields_are_rejected(
    repair,
    expected_status,
    tmp_path,
):
    result = run_repair_loop(
        ["pwd"],
        [repair],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == expected_status
    assert result.verification_runs == 0


@pytest.mark.parametrize("max_attempts", [0, 4, True, 1.5])
def test_attempt_limit_cannot_exceed_or_bypass_hard_bounds(max_attempts, tmp_path):
    result = run_repair_loop(
        ["pwd"],
        [],
        approved=True,
        max_attempts=max_attempts,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "invalid_attempt_limit"
    assert result.verification_runs == 0


def test_only_fixed_executor_tool_ids_are_invoked(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    calls: list[tuple[str, dict[str, object]]] = []
    verification_count = 0

    def fake_execute(tool_id, arguments, *, workspace):
        nonlocal verification_count
        calls.append((tool_id, dict(arguments)))
        if tool_id == "developer.run_command":
            verification_count += 1
            return _tool_result(
                verification_count == 2,
                error_code=None if verification_count == 2 else "command_failed",
                exit_code=0 if verification_count == 2 else 1,
            )
        return _tool_result(True, tool=tool_id)

    monkeypatch.setattr(repair_module, "execute_tool", fake_execute)

    result = run_repair_loop(
        ["pytest", "test_sample.py"],
        [_patch("example.py", "old", "new")],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert [tool_id for tool_id, _ in calls] == [
        "developer.run_command",
        "developer.patch_file",
        "developer.run_command",
    ]
    assert set(tool_id for tool_id, _ in calls) <= {
        "developer.run_command",
        *ALLOWED_REPAIR_TOOL_IDS,
    }


def test_predefined_write_file_repair_is_supported(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    calls: list[str] = []

    def fake_execute(tool_id, arguments, *, workspace):
        calls.append(tool_id)
        if tool_id == "developer.run_command":
            succeeded = calls.count("developer.run_command") == 2
            return _tool_result(
                succeeded,
                error_code=None if succeeded else "command_failed",
                exit_code=0 if succeeded else 1,
            )
        return _tool_result(True, tool=tool_id)

    monkeypatch.setattr(repair_module, "execute_tool", fake_execute)

    result = run_repair_loop(
        ["pytest", "test_sample.py"],
        [{
            "tool": "developer.write_file",
            "arguments": {"path": "generated.py", "content": "VALUE = 1\n"},
        }],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert calls == [
        "developer.run_command",
        "developer.write_file",
        "developer.run_command",
    ]


def test_executor_exception_is_converted_to_internal_safe_failure(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")

    def fail_safely(*args, **kwargs):
        raise RuntimeError("private executor detail")

    monkeypatch.setattr(repair_module, "execute_tool", fail_safely)

    result = run_repair_loop(
        ["pwd"],
        [],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert result.status == "internal_safe_failure"
    assert "private executor detail" not in repr(result)


def test_results_do_not_retain_output_or_patch_contents(tmp_path, monkeypatch):
    repair_module = importlib.import_module("core.developer_agent.repair_loop")
    secret_output = "private diagnostic output"

    monkeypatch.setattr(
        repair_module,
        "execute_tool",
        lambda *args, **kwargs: _tool_result(
            False,
            error_code="command_failed",
            exit_code=1,
            output=secret_output,
        ),
    )

    result = run_repair_loop(
        ["pytest", "test_sample.py"],
        [],
        approved=True,
        workspace=_workspace(tmp_path),
    )

    assert secret_output not in repr(result)
    assert "test_sample.py" not in repr(result)
    assert not hasattr(result, "output")


def test_result_models_are_immutable():
    attempt = RepairAttempt(1, "developer.run_command", True, 0, False, "passed")
    result = RepairResult(True, "passed", (attempt,), 1, 0, 0, 0, "passed")

    with pytest.raises(FrozenInstanceError):
        attempt.status = "changed"
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"


def test_repair_loop_has_no_direct_execution_filesystem_or_autonomy_hooks():
    repository_root = Path(__file__).parents[1]
    source = (repository_root / "core/developer_agent/repair_loop.py").read_text(
        encoding="utf-8"
    )
    autonomous_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repository_root / "core").glob("*.py")
        if path.name != "capability_registry.py"
    )

    assert "subprocess" not in source
    assert "shell=True" not in source.replace(" ", "")
    assert "os.system" not in source
    assert "Path(" not in source
    assert "open(" not in source
    assert "write_text(" not in source
    assert "read_text(" not in source
    assert "developer.git_" not in source
    assert "developer.repair_loop" not in autonomous_source
    assert "llm" not in source.casefold()
