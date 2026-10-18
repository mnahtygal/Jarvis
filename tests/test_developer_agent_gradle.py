import hashlib
import importlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.capability_registry import get_capability, resolve_plan_step_capabilities
from core.developer_agent import VerificationEvidence, Workspace, execute_tool
from core.developer_agent.developer_session import (
    DeveloperSessionRequest,
    VerificationSpec,
    run_developer_session_request,
)
from core.developer_agent.registry import get_tool
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.tools.gradle_test import (
    DEFAULT_MAX_OUTPUT_BYTES,
    FIXED_ARGUMENTS,
    FIXED_TASK,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    gradle_test,
)
from core.developer_agent.tools.run_command import run_command
from core.developer_agent.verification import is_successful_verification
from core.planner import PlanStep


gradle_module = importlib.import_module("core.developer_agent.tools.gradle_test")


def _workspace(path: Path) -> Workspace:
    return Workspace(path)


def _properties_text(**changes: str | None) -> str:
    properties = dict(gradle_module._EXPECTED_PROPERTIES)
    for key, value in changes.items():
        if value is None:
            properties.pop(key, None)
        else:
            properties[key] = value
    return "".join(f"{key}={value}\n" for key, value in properties.items())


def _project(tmp_path: Path, monkeypatch) -> tuple[Path, object]:
    root = tmp_path / "project"
    wrapper_directory = root / "gradle" / "wrapper"
    wrapper_directory.mkdir(parents=True)
    wrapper = root / "gradlew"
    wrapper.write_bytes(b"#!/bin/sh\n")
    wrapper.chmod(0o755)
    wrapper_jar = wrapper_directory / "gradle-wrapper.jar"
    wrapper_jar.write_bytes(b"trusted wrapper jar fixture")
    (wrapper_directory / "gradle-wrapper.properties").write_text(
        _properties_text(),
        encoding="utf-8",
    )
    policy = replace(
        gradle_module._GRADLE_9_5_POLICY,
        wrapper_script_sha256=hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        wrapper_jar_sha256=hashlib.sha256(wrapper_jar.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        gradle_module,
        "SUPPORTED_WRAPPER_VERSIONS",
        {policy.version: policy},
    )
    return root, policy


def _mock_runtime(monkeypatch, tmp_path: Path, capture: dict[str, object]) -> None:
    sdk = tmp_path / "sdk"
    sdk.mkdir(exist_ok=True)
    monkeypatch.setattr(gradle_module, "_validate_android_sdk", lambda: sdk)
    monkeypatch.setattr(
        gradle_module,
        "_validate_aapt2_override",
        lambda: tmp_path / "trusted-aapt2",
    )
    monkeypatch.setattr(
        gradle_module,
        "_validate_distribution_cache",
        lambda policy: tmp_path / "cached-distribution",
    )
    monkeypatch.setattr(
        gradle_module,
        "_prepare_controlled_gradle_home",
        lambda destination: None,
    )

    def execute(argv, **kwargs):
        capture["argv"] = tuple(argv)
        capture.update(kwargs)
        return ToolResult(
            True,
            "developer.gradle_test",
            "BUILD SUCCESSFUL\n6 tests completed",
            metadata={
                "command_family": "gradle_test",
                "exit_code": 0,
                "timed_out": False,
                "stdout": "BUILD SUCCESSFUL\n6 tests completed",
                "stderr": "",
                "stdout_bytes": 35,
                "stderr_bytes": 0,
                "output_truncated": False,
            },
        )

    monkeypatch.setattr(gradle_module, "_execute_fixed_argv", execute)


def test_approval_is_required_before_validation_or_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gradle_module,
        "validate_gradle_project",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    result = gradle_test("missing", approved=False, workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "approval_required"


def test_supported_wrapper_constructs_only_fixed_offline_command(tmp_path, monkeypatch):
    root, _ = _project(tmp_path, monkeypatch)
    capture: dict[str, object] = {}
    _mock_runtime(monkeypatch, tmp_path, capture)

    result = gradle_test(".", approved=True, workspace=_workspace(root))

    assert result.success is True
    assert capture["argv"] == (str(root / "gradlew"), *FIXED_ARGUMENTS)
    assert FIXED_ARGUMENTS == (
        "--offline",
        "--no-daemon",
        "--console=plain",
        ":app:testDebugUnitTest",
    )
    assert result.metadata["command_family"] == "gradle_test"
    assert result.metadata["gradle_version"] == "9.5.0"
    assert result.metadata["task"] == FIXED_TASK


@pytest.mark.parametrize("field,value", [
    ("task", ":app:assembleDebug"),
    ("flags", ["--scan"]),
    ("argv", ["./gradlew", "help"]),
    ("environment", {"JAVA_TOOL_OPTIONS": "-javaagent:unsafe.jar"}),
])
def test_executor_rejects_task_flag_argv_and_environment_injection(
    tmp_path, field, value
):
    result = execute_tool(
        "developer.gradle_test",
        {"project_path": ".", "approved": True, field: value},
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "invalid_arguments"


@pytest.mark.parametrize(
    "changes,error_code",
    [
        (
            {
                "distributionUrl": (
                    "https\\://services.gradle.org/distributions/gradle-9.4.0-bin.zip"
                )
            },
            "unsupported_gradle_version",
        ),
        ({"distributionSha256Sum": None}, "invalid_distribution_sha256"),
        ({"distributionSha256Sum": "not-a-sha"}, "invalid_distribution_sha256"),
        (
            {"distributionUrl": "http\\://example.invalid/gradle-9.5.0-bin.zip"},
            "unsafe_wrapper_url",
        ),
        ({"distributionSha256Sum": "0" * 64}, "distribution_sha256_mismatch"),
    ],
)
def test_wrapper_version_url_and_hash_policy(tmp_path, monkeypatch, changes, error_code):
    root, _ = _project(tmp_path, monkeypatch)
    properties = root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    properties.write_text(_properties_text(**changes), encoding="utf-8")

    with pytest.raises(gradle_module._GradlePolicyError) as error:
        gradle_module._validate_wrapper(root)

    assert error.value.code == error_code


def test_missing_wrapper_components_return_stable_errors(tmp_path, monkeypatch):
    for relative, expected in (
        ("gradlew", "missing_gradlew"),
        ("gradle/wrapper/gradle-wrapper.jar", "missing_wrapper_jar"),
        ("gradle/wrapper/gradle-wrapper.properties", "missing_wrapper_properties"),
    ):
        case_root = tmp_path / expected
        root, _ = _project(case_root, monkeypatch)
        (root / relative).unlink()
        with pytest.raises(gradle_module._GradlePolicyError) as error:
            gradle_module._validate_wrapper(root)
        assert error.value.code == expected


def test_wrapper_script_and_jar_hashes_are_allowlisted(tmp_path, monkeypatch):
    root, _ = _project(tmp_path, monkeypatch)
    (root / "gradlew").write_text("#!/bin/sh\necho unsafe\n", encoding="utf-8")

    with pytest.raises(gradle_module._GradlePolicyError) as script_error:
        gradle_module._validate_wrapper(root)
    assert script_error.value.code == "untrusted_gradlew"

    root, _ = _project(tmp_path / "jar-case", monkeypatch)
    (root / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"unsafe")
    with pytest.raises(gradle_module._GradlePolicyError) as jar_error:
        gradle_module._validate_wrapper(root)
    assert jar_error.value.code == "untrusted_wrapper_jar"


def test_traversal_and_project_root_symlinks_are_rejected(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace_root / "linked").symlink_to(outside, target_is_directory=True)
    workspace = _workspace(workspace_root)

    traversal = gradle_test("../outside", approved=True, workspace=workspace)
    symlink = gradle_test("linked", approved=True, workspace=workspace)

    assert traversal.error_code == "project_path_not_allowed"
    assert symlink.error_code == "unsafe_project_symlink"


def test_project_local_init_and_gradle_injection_properties_are_rejected(
    tmp_path, monkeypatch
):
    root, _ = _project(tmp_path, monkeypatch)
    (root / "init.gradle").write_text("println('unsafe')\n", encoding="utf-8")
    with pytest.raises(gradle_module._GradlePolicyError) as init_error:
        gradle_module._validate_wrapper(root)
    assert init_error.value.code == "project_init_script_not_allowed"

    (root / "init.gradle").unlink()
    (root / "gradle.properties").write_text(
        "org.gradle.java.home=/tmp/unsafe\n",
        encoding="utf-8",
    )
    with pytest.raises(gradle_module._GradlePolicyError) as property_error:
        gradle_module._validate_wrapper(root)
    assert property_error.value.code == "unsafe_gradle_properties"


def test_environment_is_minimal_and_strips_java_gradle_project_injection(
    tmp_path, monkeypatch
):
    root, _ = _project(tmp_path, monkeypatch)
    capture: dict[str, object] = {}
    _mock_runtime(monkeypatch, tmp_path, capture)
    monkeypatch.setenv("JAVA_HOME", "/tmp/unsafe")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-javaagent:unsafe.jar")
    monkeypatch.setenv("GRADLE_OPTS", "-I /tmp/unsafe.gradle")
    monkeypatch.setenv("ORG_GRADLE_PROJECT_secret", "unsafe")

    result = gradle_test(".", approved=True, workspace=_workspace(root))
    environment = capture["environment"]

    assert result.success is True
    assert environment["ANDROID_HOME"] == str(tmp_path / "sdk")
    assert environment["ANDROID_SDK_ROOT"] == str(tmp_path / "sdk")
    assert environment["GRADLE_USER_HOME"] == environment["HOME"]
    assert environment["CI"] == "true"
    assert "JAVA_HOME" not in environment
    assert "JAVA_TOOL_OPTIONS" not in environment
    assert "GRADLE_OPTS" not in environment
    assert all(not key.startswith("ORG_GRADLE_PROJECT_") for key in environment)


@pytest.mark.parametrize(
    "arguments",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": MAX_TIMEOUT_SECONDS + 1},
        {"max_output_bytes": 0},
        {"max_output_bytes": MAX_OUTPUT_BYTES + 1},
        {"max_output_bytes": 1.5},
    ],
)
def test_timeout_and_output_bounds_are_enforced(tmp_path, arguments):
    result = gradle_test(
        ".",
        approved=True,
        workspace=_workspace(tmp_path),
        **arguments,
    )

    assert result.success is False
    assert result.error_code == "invalid_arguments"


def test_timeout_and_truncation_metadata_are_preserved(tmp_path, monkeypatch):
    root, _ = _project(tmp_path, monkeypatch)
    capture: dict[str, object] = {}
    _mock_runtime(monkeypatch, tmp_path, capture)

    def timed_out(argv, **kwargs):
        return ToolResult(
            False,
            "developer.gradle_test",
            "bounded output",
            error_code="timeout",
            metadata={
                "command_family": "gradle_test",
                "exit_code": -15,
                "timed_out": True,
                "stdout": "bounded output",
                "stderr": "",
                "stdout_bytes": 2 * MAX_OUTPUT_BYTES,
                "stderr_bytes": 0,
                "output_truncated": True,
            },
        )

    monkeypatch.setattr(gradle_module, "_execute_fixed_argv", timed_out)
    result = gradle_test(".", approved=True, workspace=_workspace(root))

    assert result.error_code == "timeout"
    assert result.metadata["timed_out"] is True
    assert result.metadata["output_truncated"] is True
    assert DEFAULT_MAX_OUTPUT_BYTES == 256 * 1024


def test_missing_offline_dependency_is_classified_as_cache_failure(tmp_path, monkeypatch):
    root, _ = _project(tmp_path, monkeypatch)
    capture: dict[str, object] = {}
    _mock_runtime(monkeypatch, tmp_path, capture)

    def cache_miss(argv, **kwargs):
        return ToolResult(
            False,
            "developer.gradle_test",
            "No cached version available for offline mode",
            error_code="command_failed",
            metadata={
                "command_family": "gradle_test",
                "exit_code": 1,
                "timed_out": False,
                "stdout": "",
                "stderr": "No cached version available for offline mode",
                "stdout_bytes": 0,
                "stderr_bytes": 44,
                "output_truncated": False,
            },
        )

    monkeypatch.setattr(gradle_module, "_execute_fixed_argv", cache_miss)
    result = gradle_test(".", approved=True, workspace=_workspace(root))

    assert result.success is False
    assert result.error_code == "offline_cache_miss"


def test_shared_subprocess_boundary_is_argv_only_and_shell_false():
    command_module = importlib.import_module("core.developer_agent.tools.run_command")
    source = Path(command_module.__file__).read_text(encoding="utf-8")

    assert "def _execute_fixed_argv(" in source
    assert "shell=False" in source.replace(" ", "")
    assert "subprocess" not in Path(gradle_module.__file__).read_text(encoding="utf-8")


def test_gradle_result_can_create_evidence_but_failure_cannot():
    success = ToolResult(
        True,
        "developer.gradle_test",
        "green",
        metadata={"command_family": "gradle_test", "exit_code": 0, "timed_out": False},
    )
    failure = ToolResult(
        False,
        "developer.gradle_test",
        "red",
        error_code="command_failed",
        metadata={"command_family": "gradle_test", "exit_code": 1, "timed_out": False},
    )

    success_evidence = VerificationEvidence.from_tool_result(success)
    failure_evidence = VerificationEvidence.from_tool_result(failure)
    assert success_evidence.successful is True
    assert is_successful_verification(success_evidence) is True
    assert failure_evidence.successful is False
    assert is_successful_verification(failure_evidence) is False


def test_existing_pytest_evidence_and_run_command_policy_are_unchanged(tmp_path):
    pytest_result = ToolResult(
        True,
        "developer.run_command",
        "green",
        metadata={"command_family": "pytest", "exit_code": 0, "timed_out": False},
    )
    rejected_gradle = run_command(
        ["./gradlew", ":app:testDebugUnitTest"],
        workspace=_workspace(tmp_path),
    )

    assert VerificationEvidence.from_tool_result(pytest_result).successful is True
    assert rejected_gradle.success is False
    assert rejected_gradle.error_code == "executable_not_allowed"


def test_phase7_failed_gradle_stops_before_unisolated_repair(tmp_path):
    (tmp_path / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []
    verifications = [
        ToolResult(
            False,
            "developer.gradle_test",
            "failure",
            error_code="command_failed",
            metadata={"exit_code": 1, "timed_out": False},
        ),
        ToolResult(
            True,
            "developer.gradle_test",
            "green",
            metadata={"exit_code": 0, "timed_out": False},
        ),
    ]

    def executor(tool_id, arguments, *, workspace):
        calls.append((tool_id, dict(arguments)))
        if tool_id == "developer.gradle_test":
            return verifications.pop(0)
        if tool_id == "developer.patch_file":
            path = workspace.root / arguments["path"]
            path.write_text("VALUE = 2\n", encoding="utf-8")
            return ToolResult(True, tool_id, "applied")
        raise AssertionError(tool_id)

    response = json.dumps({
        "proposal_type": "patch_file",
        "path": "example.py",
        "old_text": "VALUE = 1",
        "new_text": "VALUE = 2",
        "confidence": 0.95,
        "reason": "fix value",
    })
    request = DeveloperSessionRequest(
        verification_argv=None,
        verification_spec=VerificationSpec("gradle_test", project_path="."),
        candidate_files=("example.py",),
        allowed_mutation_paths=("example.py",),
        approved=True,
    )

    result = run_developer_session_request(
        request,
        workspace=_workspace(tmp_path),
        model_call=lambda *args: response,
        _executor=executor,
    )

    verification_calls = [call for call in calls if call[0] == "developer.gradle_test"]
    assert result.success is False
    assert result.status == "candidate_isolation_unavailable"
    assert result.verification_runs == 1
    assert result.proposals_generated == result.repairs_applied == 0
    assert verification_calls == [
        ("developer.gradle_test", {"project_path": ".", "approved": True}),
    ]
    assert calls == verification_calls
    assert (tmp_path / "example.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert all("task" not in arguments and "argv" not in arguments for _, arguments in calls)
    assert all(not tool_id.startswith("developer.git_") for tool_id, _ in calls)


def test_phase7_cache_failure_stops_before_model_reasoning(tmp_path):
    (tmp_path / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    model_calls: list[object] = []

    def executor(tool_id, arguments, *, workspace):
        return ToolResult(
            False,
            "developer.gradle_test",
            "cache miss",
            error_code="offline_cache_miss",
            metadata={"exit_code": 1, "timed_out": False},
        )

    request = DeveloperSessionRequest(
        verification_argv=None,
        verification_spec=VerificationSpec("gradle_test", project_path="."),
        candidate_files=("example.py",),
        allowed_mutation_paths=("example.py",),
        approved=True,
    )
    result = run_developer_session_request(
        request,
        workspace=_workspace(tmp_path),
        model_call=lambda *args: model_calls.append(args),
        _executor=executor,
    )

    assert result.status == "verification_infrastructure_failure"
    assert result.verification_runs == 1
    assert result.proposals_generated == result.repairs_applied == 0
    assert model_calls == []


def test_gradle_capability_is_manual_only_and_not_planner_mapped():
    capability = get_capability("developer.gradle_test")
    tool = get_tool("developer.gradle_test")

    assert capability.enabled is tool.enabled is True
    assert capability.read_only is tool.read_only is True
    assert capability.mutating is tool.mutating is False
    assert capability.requires_confirmation is tool.requires_confirmation is True
    assert capability.executable is tool.executable is False
    assert resolve_plan_step_capabilities(
        PlanStep(1, "run gradle tests", "developer")
    ) == ()
