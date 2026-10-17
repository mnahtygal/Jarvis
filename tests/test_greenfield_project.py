"""Priority 5 exact-scope greenfield project orchestration tests."""

from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from core import developer_bridge, orchestrator
from core.capability_registry import (
    PHASE5_DEVELOPER_GREENFIELD_ALLOWLIST,
    get_capability,
)
from core.developer_agent import developer_session, greenfield_project
from core.developer_agent.executor import execute_tool
from core.developer_agent.greenfield_project import (
    GreenfieldFileSpec,
    GreenfieldProjectError,
    GreenfieldProjectRequest,
    classify_greenfield_request,
    prepare_greenfield_manifest,
    run_greenfield_project,
    validate_greenfield_manifest,
)
from core.developer_agent.registry import get_tool
from core.developer_agent.repair_proposal import propose_repair as real_propose_repair
from core.developer_agent.tool_models import failure_result
from core.developer_agent.developer_session import VerificationSpec


@pytest.fixture(autouse=True)
def _reset_approval_state():
    developer_bridge.reset_developer_approval_state()
    yield
    developer_bridge.reset_developer_approval_state()


@pytest.fixture
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(greenfield_project, "ALLOWED_PROJECTS_ROOT", root)
    monkeypatch.setattr(
        greenfield_project,
        "generation_config_signature",
        lambda: ("http://127.0.0.1:8080/v1/chat/completions", "test-model"),
    )
    return root


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


def _generation(files):
    return json.dumps({
        "files": [
            {"path": path, "content": content}
            for path, content in files
        ],
    })


def _request(root: Path, name: str = "demo") -> GreenfieldProjectRequest:
    files = (
        GreenfieldFileSpec("mathlib.py", "source"),
        GreenfieldFileSpec("test_mathlib.py", "test"),
    )
    return GreenfieldProjectRequest(
        workspace=str(root / name),
        files=files,
        verification=VerificationSpec(
            "run_command",
            argv=("pytest", "-q", "test_mathlib.py"),
        ),
        requirements="Build a small Python addition project and run pytest.",
    )


def _command(root: Path, name: str = "demo") -> str:
    return (
        f"Build a small Python project in {root / name} with files "
        "mathlib.py and test_mathlib.py and run pytest"
    )


def _install_generation(monkeypatch, *responses):
    model = _Responses(*responses)
    real_prepare = prepare_greenfield_manifest

    def prepare(request):
        return real_prepare(request, model_call=model)

    monkeypatch.setattr(developer_bridge, "prepare_greenfield_manifest", prepare)
    return model


def _patch_response(path, old_text, new_text):
    return json.dumps({
        "proposal_type": "patch_file",
        "path": path,
        "old_text": old_text,
        "new_text": new_text,
        "confidence": 0.95,
        "reason": "The failing assertion identifies this exact repair",
    })


def _install_repairs(monkeypatch, *responses):
    model = _Responses(*responses)

    def propose(request, *, workspace, model_call=None):
        return real_propose_repair(request, workspace=workspace, model_call=model)

    monkeypatch.setattr(developer_session, "propose_repair", propose)
    return model


def test_greenfield_capability_is_dedicated_manual_only():
    assert PHASE5_DEVELOPER_GREENFIELD_ALLOWLIST == frozenset({
        "developer.greenfield_project",
    })
    capability = get_capability("developer.greenfield_project")
    tool = get_tool("developer.greenfield_project")
    assert capability is not None and tool is not None
    assert capability.enabled and tool.enabled
    assert capability.requires_confirmation and tool.requires_confirmation
    assert capability.mutating and tool.mutating
    assert not capability.executable and not tool.executable
    assert execute_tool("developer.greenfield_project", {}).error_code == "unknown_tool"


def test_classifier_requires_exact_bounded_greenfield_shape(projects_root):
    request, recognized = classify_greenfield_request(_command(projects_root))
    assert recognized is True
    assert request is not None
    assert request.workspace == str(projects_root / "demo")
    assert tuple(item.path for item in request.files) == (
        "mathlib.py",
        "test_mathlib.py",
    )
    assert request.verification.argv == ("pytest", "-q", "test_mathlib.py")

    vague, vague_recognized = classify_greenfield_request("Build me something cool")
    assert vague is None
    assert vague_recognized is False


def test_classifier_infers_frozen_pytest_target_from_explicit_test_file(projects_root):
    command = (
        f"Build a small Python project in {projects_root / 'implicit-pytest'} "
        "with files app.py and test_app.py"
    )

    request, recognized = classify_greenfield_request(command)

    assert recognized is True
    assert request is not None
    assert request.verification.argv == ("pytest", "-q", "test_app.py")


def test_green_project_requires_approval_and_stops_without_repair(
    projects_root, monkeypatch
):
    target = projects_root / "green"
    generator = _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "def add(a, b):\n    return a + b\n"),
            (
                "test_mathlib.py",
                "from mathlib import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            ),
        )),
    )
    unexpected_repair = Mock(side_effect=AssertionError("repair model must not run"))
    monkeypatch.setattr(developer_session, "propose_repair", unexpected_repair)

    proposed = orchestrator.process_request(_command(projects_root, "green"))

    assert proposed.developer_status == "confirmation_required"
    assert proposed.developer_capability_id == "developer.greenfield_project"
    assert not target.exists()
    assert len(generator.calls) == 1

    approved = orchestrator.process_request("approve")

    assert approved.developer_status == "executed_success"
    assert approved.developer_tool_success is True
    assert approved.developer_result.verification_count == 1
    assert approved.developer_result.repair_count == 0
    assert sorted(path.name for path in target.glob("*.py")) == [
        "mathlib.py",
        "test_mathlib.py",
    ]
    assert not (target / ".git").exists()
    unexpected_repair.assert_not_called()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_cancel_discards_manifest_without_creating_project(projects_root, monkeypatch):
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "def add(a, b):\n    return a + b\n"),
            ("test_mathlib.py", "def test_placeholder():\n    assert True\n"),
        )),
    )
    target = projects_root / "cancelled"

    assert orchestrator.process_request(_command(projects_root, "cancelled")).developer_status == "confirmation_required"
    assert orchestrator.process_request("cancel").developer_status == "cancelled"
    assert not target.exists()
    assert orchestrator.process_request("approve").developer_error_code == "no_pending_action"


def test_red_project_repairs_source_only_and_preserves_test(projects_root, monkeypatch):
    target = projects_root / "repair"
    test_content = "from mathlib import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "def add(a, b):\n    return a - b\n"),
            ("test_mathlib.py", test_content),
        )),
    )
    repairs = _install_repairs(
        monkeypatch,
        _patch_response("mathlib.py", "return a - b", "return a + b"),
    )

    assert orchestrator.process_request(_command(projects_root, "repair")).developer_status == "confirmation_required"
    approved = orchestrator.process_request("approve")

    assert approved.developer_status == "executed_success"
    assert approved.developer_result.verification_count == 2
    assert approved.developer_result.repair_count == 1
    assert (target / "mathlib.py").read_text(encoding="utf-8").endswith("return a + b\n")
    assert (target / "test_mathlib.py").read_text(encoding="utf-8") == test_content
    assert len(repairs.calls) == 1
    assert not (target / ".git").exists()


def test_two_repairs_then_red_stops_and_retains_visible_state(projects_root, monkeypatch):
    target = projects_root / "still-red"
    source = "FIRST = 0\nSECOND = 0\n"
    test_content = (
        "from mathlib import FIRST, SECOND\n\n"
        "def test_values():\n"
        "    assert FIRST == 1\n"
        "    assert SECOND == 2\n"
        "    assert FIRST + SECOND == 99\n"
    )
    _install_generation(
        monkeypatch,
        _generation((("mathlib.py", source), ("test_mathlib.py", test_content))),
    )
    repairs = _install_repairs(
        monkeypatch,
        _patch_response("mathlib.py", "FIRST = 0", "FIRST = 1"),
        _patch_response("mathlib.py", "SECOND = 0", "SECOND = 2"),
    )

    assert orchestrator.process_request(_command(projects_root, "still-red")).developer_status == "confirmation_required"
    result = orchestrator.process_request("approve")

    assert result.developer_status == "project_not_verified"
    assert result.developer_result.verification_count == 3
    assert result.developer_result.repair_count == 2
    assert result.developer_error_code == "repair_limit"
    assert len(repairs.calls) == 2
    assert "FIRST = 1" in (target / "mathlib.py").read_text(encoding="utf-8")
    assert "SECOND = 2" in (target / "mathlib.py").read_text(encoding="utf-8")
    assert (target / "test_mathlib.py").read_text(encoding="utf-8") == test_content
    assert not (target / ".git").exists()


def test_repair_proposal_cannot_mutate_test_file(projects_root, monkeypatch):
    target = projects_root / "test-immutable"
    test_content = "from mathlib import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "def add(a, b):\n    return a - b\n"),
            ("test_mathlib.py", test_content),
        )),
    )
    _install_repairs(
        monkeypatch,
        _patch_response("test_mathlib.py", "== 5", "== -1"),
    )

    assert orchestrator.process_request(_command(projects_root, "test-immutable")).developer_status == "confirmation_required"
    result = orchestrator.process_request("approve")

    assert result.developer_status == "project_not_verified"
    assert result.developer_error_code == "proposal_outside_mutation_scope"
    assert (target / "test_mathlib.py").read_text(encoding="utf-8") == test_content


def test_partial_bootstrap_is_reported_and_retained(projects_root):
    model = _Responses(_generation((
        ("mathlib.py", "VALUE = 1\n"),
        ("test_mathlib.py", "def test_value():\n    assert True\n"),
    )))
    manifest = prepare_greenfield_manifest(_request(projects_root, "partial"), model_call=model)
    calls = 0

    def executor(tool_id, arguments, *, workspace):
        nonlocal calls
        calls += 1
        if calls == 2:
            return failure_result(tool_id, "write_failed", "failed")
        return execute_tool(tool_id, arguments, workspace=workspace)

    result = run_greenfield_project(manifest, _executor=executor)

    assert result.success is False
    assert result.status == "bootstrap_partial_failure"
    assert result.created_files == ("mathlib.py",)
    assert (projects_root / "partial/mathlib.py").exists()
    assert not (projects_root / "partial/test_mathlib.py").exists()


def test_workspace_initialization_failure_reports_created_directory(
    projects_root, monkeypatch
):
    model = _Responses(_generation((
        ("mathlib.py", "VALUE = 1\n"),
        ("test_mathlib.py", "def test_value():\n    assert True\n"),
    )))
    manifest = prepare_greenfield_manifest(
        _request(projects_root, "workspace-failure"),
        model_call=model,
    )
    monkeypatch.setattr(
        greenfield_project,
        "Workspace",
        Mock(side_effect=ValueError("unavailable")),
    )

    result = run_greenfield_project(manifest)

    assert result.success is False
    assert result.status == "project_directory_state_changed"
    assert result.directory_created is True
    assert result.created_files == ()
    assert (projects_root / "workspace-failure").is_dir()


def test_destination_created_after_confirmation_fails_closed(projects_root, monkeypatch):
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "VALUE = 1\n"),
            ("test_mathlib.py", "def test_value():\n    assert True\n"),
        )),
    )
    target = projects_root / "race"
    assert orchestrator.process_request(_command(projects_root, "race")).developer_status == "confirmation_required"
    target.mkdir()

    result = orchestrator.process_request("approve")

    assert result.developer_status == "validation_failed"
    assert result.developer_error_code == "project_already_exists"
    assert list(target.iterdir()) == []


def test_generation_config_change_after_confirmation_fails_closed(projects_root, monkeypatch):
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "VALUE = 1\n"),
            ("test_mathlib.py", "def test_value():\n    assert True\n"),
        )),
    )
    target = projects_root / "config-change"
    assert orchestrator.process_request(_command(projects_root, "config-change")).developer_status == "confirmation_required"
    monkeypatch.setattr(
        greenfield_project,
        "generation_config_signature",
        lambda: ("http://127.0.0.1:8080/v1/chat/completions", "different-model"),
    )

    result = orchestrator.process_request("approve")

    assert result.developer_status == "validation_failed"
    assert result.developer_error_code == "generation_config_changed"
    assert not target.exists()


def test_projects_root_replacement_after_confirmation_fails_closed(
    projects_root, monkeypatch
):
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "VALUE = 1\n"),
            ("test_mathlib.py", "def test_value():\n    assert True\n"),
        )),
    )
    target = projects_root / "root-replaced"
    assert orchestrator.process_request(_command(projects_root, "root-replaced")).developer_status == "confirmation_required"
    original_root = projects_root.with_name("original-projects")
    projects_root.rename(original_root)
    projects_root.mkdir()

    result = orchestrator.process_request("approve")

    assert result.developer_status == "validation_failed"
    assert result.developer_error_code == "projects_root_changed"
    assert not target.exists()
    assert not (original_root / "root-replaced").exists()


def test_pending_workspace_tampering_fails_seal_revalidation(projects_root, monkeypatch):
    _install_generation(
        monkeypatch,
        _generation((
            ("mathlib.py", "VALUE = 1\n"),
            ("test_mathlib.py", "def test_value():\n    assert True\n"),
        )),
    )
    assert orchestrator.process_request(_command(projects_root, "sealed")).developer_status == "confirmation_required"
    pending = developer_bridge._pending_action
    manifest = pending.arguments["manifest"]
    tampered = replace(manifest, workspace=str(projects_root / "different"))
    object.__setattr__(tampered, "_seal", manifest._seal)
    object.__setattr__(tampered, "digest", greenfield_project._manifest_digest(tampered))
    developer_bridge._pending_action = replace(
        pending,
        arguments={"manifest": tampered},
    )

    result = orchestrator.process_request("approve")

    assert result.developer_status == "validation_failed"
    assert result.developer_error_code == "validation_state_changed"
    assert not (projects_root / "sealed").exists()
    assert not (projects_root / "different").exists()


@pytest.mark.parametrize("workspace", (
    "/home/mnahtygal/jarvis/new-project",
    "/tmp/arbitrary-project",
    "/home/mnahtygal/projects/../escape",
    "/home/mnahtygal/projects/$HOME",
))
def test_disallowed_project_paths_are_rejected(projects_root, workspace):
    request = replace(_request(projects_root), workspace=workspace)
    with pytest.raises(GreenfieldProjectError):
        prepare_greenfield_manifest(request, model_call=Mock())


def test_symlink_projects_root_and_existing_destination_are_rejected(tmp_path, monkeypatch):
    real_root = tmp_path / "real-projects"
    real_root.mkdir()
    linked_root = tmp_path / "linked-projects"
    linked_root.symlink_to(real_root, target_is_directory=True)
    monkeypatch.setattr(greenfield_project, "ALLOWED_PROJECTS_ROOT", linked_root)

    with pytest.raises(GreenfieldProjectError, match="invalid_projects_root"):
        prepare_greenfield_manifest(_request(linked_root), model_call=Mock())

    monkeypatch.setattr(greenfield_project, "ALLOWED_PROJECTS_ROOT", real_root)
    (real_root / "existing").mkdir()
    with pytest.raises(GreenfieldProjectError, match="project_already_exists"):
        prepare_greenfield_manifest(_request(real_root, "existing"), model_call=Mock())


@pytest.mark.parametrize("output", (
    '{"files":[{"path":"/tmp/mathlib.py","content":"x"},{"path":"test_mathlib.py","content":"x"}]}',
    '{"files":[{"path":"wrong.py","content":"x"},{"path":"test_mathlib.py","content":"x"}]}',
    '{"files":[{"path":"mathlib.py","content":"x"},{"path":"mathlib.py","content":"y"}]}',
    '{"files":[{"path":"mathlib.py","content":"x"},{"path":"test_mathlib.py","content":"x"},{"path":"extra.py","content":"x"}]}',
    '{"files":[{"path":"mathlib.py","content":"x"},{"path":"test_mathlib.py","content":"x"}],"command":"pip install x"}',
    '```json\n{"files":[]}\n```',
))
def test_generated_scope_attacks_are_rejected(projects_root, output):
    model = _Responses(output, output)
    with pytest.raises(GreenfieldProjectError):
        prepare_greenfield_manifest(_request(projects_root), model_call=model)
    assert not (projects_root / "demo").exists()


def test_generated_file_and_total_size_limits_are_enforced(projects_root):
    oversized_file = _generation((
        ("mathlib.py", "x = '" + ("a" * (8 * 1024)) + "'\n"),
        ("test_mathlib.py", "def test_placeholder():\n    assert True\n"),
    ))
    model = _Responses(oversized_file, oversized_file)

    with pytest.raises(GreenfieldProjectError, match="generated_file_too_large"):
        prepare_greenfield_manifest(_request(projects_root), model_call=model)

    specs = (
        GreenfieldFileSpec("first.py", "source"),
        GreenfieldFileSpec("second.py", "source"),
        GreenfieldFileSpec("third.py", "source"),
        GreenfieldFileSpec("test_first.py", "test"),
        GreenfieldFileSpec("test_second.py", "test"),
    )
    total_request = GreenfieldProjectRequest(
        workspace=str(projects_root / "oversized-total"),
        files=specs,
        verification=VerificationSpec(
            "run_command",
            argv=("pytest", "-q", "test_first.py", "test_second.py"),
        ),
        requirements="Build an exact five-file Python project.",
    )
    total_output = _generation(tuple(
        (item.path, f'DATA = "{"a" * 5000}"\n')
        for item in specs
    ))
    total_model = _Responses(total_output, total_output)

    with pytest.raises(GreenfieldProjectError, match="generated_project_too_large"):
        prepare_greenfield_manifest(total_request, model_call=total_model)


def test_request_file_count_limit_is_enforced(projects_root):
    files = tuple(
        GreenfieldFileSpec(f"module_{index}.py", "source")
        for index in range(5)
    ) + (GreenfieldFileSpec("test_modules.py", "test"),)
    request = replace(
        _request(projects_root),
        files=files,
        verification=VerificationSpec(
            "run_command",
            argv=("pytest", "-q", "test_modules.py"),
        ),
    )

    with pytest.raises(GreenfieldProjectError, match="invalid_file_count"):
        prepare_greenfield_manifest(request, model_call=Mock())


@pytest.mark.parametrize("source", (
    "import subprocess\nsubprocess.run(['pip', 'install', 'x'])\n",
    "import socket\nsocket.create_connection(('example.com', 80))\n",
    "import requests\nrequests.get('https://example.com')\n",
    "from xmlrpc.client import ServerProxy\nServerProxy('http://example.com')\n",
    "import sys\nsys.modules['os'].system('echo unsafe')\n",
    "eval('1 + 1')\n",
    "getattr(object(), '__class__')\n",
    "import pathlib\nrunner = pathlib.os.system\n",
    "object().__class__\n",
))
def test_generated_executable_content_rejects_process_network_and_dynamic_access(
    projects_root, source
):
    output = _generation((
        ("mathlib.py", source),
        ("test_mathlib.py", "def test_placeholder():\n    assert True\n"),
    ))
    model = _Responses(output, output)

    with pytest.raises(GreenfieldProjectError):
        prepare_greenfield_manifest(_request(projects_root), model_call=model)

    assert not (projects_root / "demo").exists()


def test_changed_verification_or_workspace_invalidates_manifest(projects_root):
    model = _Responses(_generation((
        ("mathlib.py", "VALUE = 1\n"),
        ("test_mathlib.py", "def test_value():\n    assert True\n"),
    )))
    manifest = prepare_greenfield_manifest(_request(projects_root), model_call=model)

    with pytest.raises(GreenfieldProjectError):
        validate_greenfield_manifest(replace(
            manifest,
            verification=VerificationSpec(
                "run_command",
                argv=("pytest", "-q", "mathlib.py"),
            ),
        ))
    with pytest.raises(GreenfieldProjectError):
        validate_greenfield_manifest(replace(
            manifest,
            workspace=str(projects_root / "different"),
        ))


def test_multiline_benchmark_shape_is_recognized_without_execution(projects_root):
    command = f"""Build a small Python command-line application in:

{projects_root / 'future-challenge'}

Create exactly:

inventory.py
app.py
test_inventory.py

Use pytest verification."""

    request, recognized = classify_greenfield_request(command)

    assert recognized is True
    assert request is not None
    assert tuple(item.path for item in request.files) == (
        "inventory.py",
        "app.py",
        "test_inventory.py",
    )
    assert request.verification.argv == ("pytest", "-q", "test_inventory.py")
    assert not (projects_root / "future-challenge").exists()
