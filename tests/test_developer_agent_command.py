import importlib
from pathlib import Path
import subprocess

import pytest

from core.developer_agent import Workspace, execute_tool
from core.developer_agent.command_policy import (
    SAFE_SYSTEM_PATH,
    CommandPolicyError,
    validate_command,
)
from core.developer_agent.tools.run_command import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    _safe_environment,
    run_command,
)


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def _write_test(tmp_path: Path, content: str) -> None:
    (tmp_path / "test_sample.py").write_text(content, encoding="utf-8")


def test_allowed_fixed_commands_validate(tmp_path):
    workspace = _workspace(tmp_path)

    commands = (
        ["pwd"],
        ["git", "status", "--short", "--branch"],
        ["git", "diff"],
        ["git", "diff", "--check"],
        ["git", "diff", "--cached"],
        ["git", "diff", "--cached", "--check"],
        ["git", "branch", "--show-current"],
    )

    approved = tuple(validate_command(command, workspace) for command in commands)

    assert tuple(command.family for command in approved) == (
        "pwd",
        "git",
        "git",
        "git",
        "git",
        "git",
        "git",
    )
    assert all(Path(command.execution_argv[0]).is_absolute() for command in approved)


def test_git_execution_vector_disables_external_helpers(tmp_path):
    approved = validate_command(["git", "diff", "--check"], _workspace(tmp_path))

    assert approved.requested_argv == ("git", "diff", "--check")
    assert "--no-pager" in approved.execution_argv
    assert "core.fsmonitor=false" in approved.execution_argv
    assert "diff.external=" in approved.execution_argv
    assert "--no-ext-diff" in approved.execution_argv
    assert "--no-textconv" in approved.execution_argv


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "status", "--short", "--branch"],
        ["git", "diff"],
        ["git", "diff", "--check"],
        ["git", "diff", "--cached"],
        ["git", "diff", "--cached", "--check"],
        ["git", "branch", "--show-current"],
    ],
)
def test_approved_git_forms_execute(argv, tmp_path):
    subprocess.run(
        ["/usr/bin/git", "init", "--quiet"],
        cwd=tmp_path,
        check=True,
    )

    result = run_command(argv, workspace=_workspace(tmp_path))

    assert result.success is True
    assert result.metadata["command_family"] == "git"
    assert result.metadata["exit_code"] == 0


@pytest.mark.parametrize("executable", ["python", "python3", "pytest"])
def test_approved_pytest_forms_execute(executable, tmp_path):
    _write_test(tmp_path, "def test_ok():\n    assert True\n")
    argv = (
        [executable, "-q", "test_sample.py"]
        if executable == "pytest"
        else [executable, "-m", "pytest", "-q", "test_sample.py"]
    )

    result = run_command(argv, workspace=_workspace(tmp_path))

    assert result.success is True
    assert result.metadata["command_family"] == "pytest"
    assert result.metadata["exit_code"] == 0
    assert result.metadata["timed_out"] is False
    assert "1 passed" in result.metadata["stdout"]


@pytest.mark.parametrize("executable", ["python", "python3"])
def test_approved_compileall_forms_execute(executable, tmp_path):
    (tmp_path / "module.py").write_text("answer = 42\n", encoding="utf-8")

    result = run_command(
        [executable, "-m", "compileall", "-q", "module.py"],
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.metadata["command_family"] == "compileall"
    assert (tmp_path / "__pycache__").is_dir()


@pytest.mark.parametrize("executable", ["python", "python3"])
def test_approved_py_compile_forms_execute(executable, tmp_path):
    (tmp_path / "module.py").write_text("answer = 42\n", encoding="utf-8")

    result = run_command(
        [executable, "-m", "py_compile", "module.py"],
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.metadata["command_family"] == "py_compile"
    assert (tmp_path / "__pycache__").is_dir()


def test_workspace_cannot_shadow_approved_python_modules(tmp_path):
    (tmp_path / "pytest.py").write_text(
        "raise RuntimeError('workspace module shadow executed')\n",
        encoding="utf-8",
    )
    (tmp_path / "compileall.py").write_text(
        "raise RuntimeError('workspace module shadow executed')\n",
        encoding="utf-8",
    )
    (tmp_path / "module.py").write_text("answer = 42\n", encoding="utf-8")
    _write_test(tmp_path, "def test_ok():\n    assert True\n")
    workspace = _workspace(tmp_path)

    pytest_result = run_command(["pytest", "-q", "test_sample.py"], workspace=workspace)
    compile_result = run_command(
        ["python", "-m", "compileall", "-q", "module.py"],
        workspace=workspace,
    )

    assert pytest_result.success is True
    assert compile_result.success is True
    assert "workspace module shadow executed" not in repr(pytest_result)
    assert "workspace module shadow executed" not in repr(compile_result)


def test_python_execution_uses_policy_selected_absolute_interpreter(tmp_path):
    _write_test(tmp_path, "def test_ok():\n    assert True\n")

    approved = validate_command(
        ["python", "-m", "pytest", "test_sample.py"],
        _workspace(tmp_path),
    )

    assert Path(approved.execution_argv[0]).is_absolute()
    assert approved.execution_argv[0] != "python"
    assert approved.execution_argv[0] != "python3"


@pytest.mark.parametrize(
    "argv",
    [
        ["bash", "-c", "pwd"],
        ["sh", "-c", "pwd"],
        ["python", "-c", "print('unsafe')"],
        ["python3", "-c", "print('unsafe')"],
        ["python", "script.py"],
        ["python", "-m", "os"],
        ["git", "add", "."],
        ["git", "commit", "-m", "unsafe"],
        ["git", "push"],
        ["git", "reset", "--hard"],
        ["git", "clean", "-fd"],
        ["git", "checkout", "main"],
        ["git", "restore", "."],
        ["git", "switch", "main"],
        ["rm", "-rf", "."],
        ["curl", "https://example.com"],
        ["wget", "https://example.com"],
        ["unknown-command"],
        ["/usr/bin/python", "-m", "pytest"],
        ["/usr/bin/git", "status", "--short", "--branch"],
        ["./python", "-m", "pytest"],
        ["../bin/python", "-m", "pytest"],
        ["python3.12", "-m", "pytest"],
        ["pythοn", "-m", "pytest"],
        ["ｐｙｔｈｏｎ", "-m", "pytest"],
        ["PATH=/tmp", "pwd"],
        ["python", "-"],
        ["git", "st"],
        ["git", "-c", "alias.status=reset --hard", "status"],
        ["zsh", "-c", "pwd"],
        ["fish", "-c", "pwd"],
        ["sudo", "pwd"],
        ["su", "root"],
        ["ssh", "localhost"],
        ["scp", "source", "target"],
        ["nc", "localhost", "80"],
        ["ncat", "localhost", "80"],
        ["socat", "-", "TCP:localhost:80"],
        ["apt", "install", "package"],
        ["apt-get", "install", "package"],
        ["pip", "install", "package"],
        ["pipx", "install", "package"],
        ["npm", "install", "package"],
        ["pnpm", "install", "package"],
        ["mv", "source", "target"],
        ["cp", "source", "target"],
        ["chmod", "777", "."],
        ["chown", "root", "."],
        ["dd", "if=/dev/zero", "of=file"],
        ["mount", "/dev/sda", "/mnt"],
        ["docker", "ps"],
        ["systemctl", "restart", "service"],
        ["kill", "1"],
        ["pkill", "python"],
        [],
        ["pwd", 1],
        ["pwd", "bad\x00argument"],
    ],
)
def test_rejected_command_matrix(argv, tmp_path):
    result = run_command(argv, workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.metadata["exit_code"] is None
    assert result.metadata["command_family"] == "unapproved"


@pytest.mark.parametrize(
    "argv",
    [
        "pwd",
        ["pwd", *("value" for _ in range(128))],
        ["pwd", "x" * 4097],
    ],
)
def test_argv_shape_and_size_limits_are_enforced(argv, tmp_path):
    result = run_command(argv, workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.metadata["exit_code"] is None


@pytest.mark.parametrize(
    "argv",
    [
        ["pwd", ";", "rm"],
        ["pwd", "&&", "rm"],
        ["pwd", "$(id)"],
        ["pwd", "|", "id"],
        ["pwd", "\t"],
        ["pwd", "\u202e"],
        ["pytest", "-p", "plugin", "test_sample.py"],
        ["pytest", "--pyargs", "os"],
        ["pytest", "--basetemp=/tmp/outside", "test_sample.py"],
        ["pytest", "--override-ini=addopts=-p unsafe", "test_sample.py"],
        ["python", "-m", "pytest", "@arguments.txt"],
        ["python", "-m", "compileall", "-x", ".*"],
        ["python", "-m", "py_compile", "-q", "module.py"],
    ],
)
def test_shell_and_injection_style_arguments_are_rejected(argv, tmp_path):
    _write_test(tmp_path, "def test_ok():\n    assert True\n")
    (tmp_path / "module.py").write_text("answer = 42\n", encoding="utf-8")

    result = run_command(argv, workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.metadata["exit_code"] is None


def test_shell_redirection_is_rejected_without_creating_a_file(tmp_path):
    result = run_command(
        ["pwd", ">", "created-by-shell.txt"],
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "shell_syntax"
    assert not (tmp_path / "created-by-shell.txt").exists()


def test_glob_syntax_is_not_expanded(tmp_path):
    _write_test(tmp_path, "def test_ok():\n    assert True\n")
    (tmp_path / "test_other.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")

    result = run_command(["pytest", "*.py"], workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "path_not_allowed"


def test_command_paths_must_exist_inside_workspace(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("answer = 42\n", encoding="utf-8")
    (workspace_root / "escape.py").symlink_to(outside)
    workspace = _workspace(workspace_root)

    results = (
        run_command(["pytest", str(outside)], workspace=workspace),
        run_command(["python", "-m", "py_compile", "../outside.py"], workspace=workspace),
        run_command(["python", "-m", "compileall", "escape.py"], workspace=workspace),
    )

    assert all(result.success is False for result in results)
    assert all(result.error_code == "path_not_allowed" for result in results)


def test_pwd_runs_at_fixed_workspace_root(tmp_path):
    result = run_command(["pwd"], workspace=_workspace(tmp_path))

    assert result.success is True
    assert result.output == str(tmp_path.resolve())
    assert result.metadata["command_family"] == "pwd"


def test_executor_runs_only_supported_command_arguments(tmp_path):
    result = execute_tool(
        "developer.run_command",
        {
            "argv": ["pwd"],
            "timeout_seconds": 1,
            "max_output_bytes": 1024,
        },
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.output == str(tmp_path.resolve())


def test_environment_is_minimal_and_rejects_ambient_injection(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PRIVATE_VALUE", "must-not-pass")
    monkeypatch.setenv("PYTHONPATH", "/tmp/unsafe")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p unsafe")
    monkeypatch.setenv("PYTHONHOME", "/tmp/unsafe")
    monkeypatch.setenv("PYTEST_PLUGINS", "unsafe")

    environment = _safe_environment(_workspace(tmp_path), "pytest")

    assert environment["PATH"] == SAFE_SYSTEM_PATH
    assert environment["HOME"] == str(tmp_path.resolve())
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONSAFEPATH"] == "1"
    assert "JARVIS_PRIVATE_VALUE" not in environment
    assert "PYTHONPATH" not in environment
    assert "PYTEST_ADDOPTS" not in environment
    assert "PYTHONHOME" not in environment
    assert "PYTEST_PLUGINS" not in environment


def test_git_environment_disables_ambient_helpers(tmp_path, monkeypatch):
    unsafe_names = (
        "GIT_CONFIG_COUNT",
        "GIT_EXTERNAL_DIFF",
        "GIT_EDITOR",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
    )
    for name in unsafe_names:
        monkeypatch.setenv(name, "unsafe")

    environment = _safe_environment(_workspace(tmp_path), "git")

    assert environment["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"
    assert environment["GIT_PAGER"] == "cat"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["PAGER"] == "cat"
    assert all(name not in environment for name in unsafe_names)


def test_timeout_terminates_command_and_returns_stable_metadata(tmp_path):
    _write_test(
        tmp_path,
        "import time\n\ndef test_slow():\n    time.sleep(5)\n",
    )

    result = run_command(
        ["pytest", "-q", "test_sample.py"],
        timeout_seconds=0.1,
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "timeout"
    assert result.metadata["timed_out"] is True
    assert result.metadata["exit_code"] is not None


def test_combined_output_is_bounded_and_streams_remain_separate(tmp_path):
    _write_test(
        tmp_path,
        "import sys\n\ndef test_output():\n"
        "    print('o' * 4096)\n"
        "    sys.stderr.write('e' * 4096)\n",
    )

    result = run_command(
        ["pytest", "-q", "-s", "test_sample.py"],
        max_output_bytes=128,
        workspace=_workspace(tmp_path),
    )

    stdout = result.metadata["stdout"]
    stderr = result.metadata["stderr"]
    assert result.success is True
    assert result.metadata["stdout_bytes"] > 128
    assert result.metadata["stderr_bytes"] > 128
    assert result.metadata["output_truncated"] is True
    assert len(stdout.encode()) + len(stderr.encode()) <= 128


@pytest.mark.parametrize(
    "arguments",
    [
        {"argv": ["pwd"], "cwd": "/tmp"},
        {"argv": ["pwd"], "env": {"SECRET": "value"}},
        {"argv": ["pwd"], "shell": True},
        {"timeout_seconds": 1},
    ],
)
def test_executor_rejects_unsupported_or_missing_arguments(arguments, tmp_path):
    result = execute_tool(
        "developer.run_command",
        arguments,
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "invalid_arguments"


@pytest.mark.parametrize(
    "arguments",
    [
        {"argv": ["pwd"], "timeout_seconds": 0},
        {"argv": ["pwd"], "timeout_seconds": MAX_TIMEOUT_SECONDS + 1},
        {"argv": ["pwd"], "timeout_seconds": float("nan")},
        {"argv": ["pwd"], "max_output_bytes": 0},
        {"argv": ["pwd"], "max_output_bytes": MAX_OUTPUT_BYTES + 1},
        {"argv": ["pwd"], "max_output_bytes": 1.5},
    ],
)
def test_timeout_and_output_limits_are_validated(arguments, tmp_path):
    result = run_command(workspace=_workspace(tmp_path), **arguments)

    assert result.success is False
    assert result.error_code == "invalid_arguments"


def test_default_limits_are_bounded():
    assert DEFAULT_TIMEOUT_SECONDS == 60
    assert MAX_TIMEOUT_SECONDS == 300
    assert DEFAULT_MAX_OUTPUT_BYTES == 128 * 1024
    assert MAX_OUTPUT_BYTES == 1024 * 1024


def test_raw_process_error_is_not_leaked(tmp_path, monkeypatch):
    command_module = importlib.import_module("core.developer_agent.tools.run_command")

    def fail_safely(*args, **kwargs):
        raise OSError("private process detail")

    monkeypatch.setattr(command_module.subprocess, "Popen", fail_safely)

    result = run_command(["pwd"], workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "command_unavailable"
    assert "private process detail" not in result.output
    assert "private process detail" not in repr(result)


def test_reader_start_failure_stops_child_and_fails_safely(tmp_path, monkeypatch):
    command_module = importlib.import_module("core.developer_agent.tools.run_command")

    def fail_safely(*args, **kwargs):
        raise RuntimeError("private thread detail")

    monkeypatch.setattr(command_module.threading.Thread, "start", fail_safely)

    result = run_command(["pwd"], workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "execution_failed"
    assert "private thread detail" not in result.output
    assert "private thread detail" not in repr(result)


def test_no_shell_or_autonomous_invocation_is_present():
    repository_root = Path(__file__).parents[1]
    developer_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repository_root / "core" / "developer_agent").rglob("*.py")
    )
    autonomous_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repository_root / "core").glob("*.py")
        if path.name != "capability_registry.py"
    )

    assert "shell=True" not in developer_source.replace(" ", "")
    assert "developer.run_command" not in autonomous_source


def test_policy_errors_are_stable(tmp_path):
    with pytest.raises(CommandPolicyError) as error:
        validate_command(["sudo", "pwd"], _workspace(tmp_path))

    assert error.value.code == "executable_not_allowed"
    assert "sudo" not in error.value.message
