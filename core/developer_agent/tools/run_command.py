"""Controlled argv-only command execution inside the approved workspace."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import sys
import threading

from core.developer_agent.command_policy import (
    SAFE_SYSTEM_PATH,
    CommandPolicyError,
    validate_command,
)
from core.developer_agent.tool_models import ToolResult
from core.developer_agent.workspace import Workspace


TOOL_ID = "developer.run_command"
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 300
DEFAULT_MAX_OUTPUT_BYTES = 128 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
READ_CHUNK_BYTES = 8192
TERMINATE_GRACE_SECONDS = 2


class _BoundedCapture:
    def __init__(self, maximum_bytes: int) -> None:
        self._maximum_bytes = maximum_bytes
        self._remaining = maximum_bytes
        self._lock = threading.Lock()
        self._captured = {"stdout": bytearray(), "stderr": bytearray()}
        self._totals = {"stdout": 0, "stderr": 0}

    def consume(self, stream_name: str, chunk: bytes) -> None:
        with self._lock:
            self._totals[stream_name] += len(chunk)
            kept = chunk[:self._remaining]
            self._captured[stream_name].extend(kept)
            self._remaining -= len(kept)

    def text(self, stream_name: str) -> str:
        return bytes(self._captured[stream_name]).decode("utf-8", errors="replace")

    def total(self, stream_name: str) -> int:
        return self._totals[stream_name]

    @property
    def truncated(self) -> bool:
        return sum(self._totals.values()) > self._maximum_bytes


def _safe_environment(workspace: Workspace, command_family: str) -> dict[str, str]:
    environment = {
        "HOME": str(workspace.root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": SAFE_SYSTEM_PATH,
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    if sys.prefix != sys.base_prefix:
        environment["VIRTUAL_ENV"] = sys.prefix
    if command_family == "git":
        environment.update({
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "PAGER": "cat",
        })
    if command_family == "pytest":
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _bounded_number(
    value: object,
    *,
    default: int,
    maximum: int,
    name: str,
) -> int | float:
    if value is None:
        return default
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise CommandPolicyError("invalid_arguments", f"{name} must be a positive number")
    if value > maximum:
        raise CommandPolicyError("invalid_arguments", f"{name} exceeds the safe maximum")
    return value


def _read_stream(stream, stream_name: str, capture: _BoundedCapture) -> None:
    try:
        while True:
            chunk = stream.read(READ_CHUNK_BYTES)
            if not chunk:
                return
            capture.consume(stream_name, chunk)
    except (OSError, ValueError):
        return
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _signal_process(process: subprocess.Popen[bytes], *, force: bool) -> None:
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    elif force:
        process.kill()
    else:
        process.terminate()


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    try:
        _signal_process(process, force=False)
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        try:
            _signal_process(process, force=True)
            process.wait(timeout=TERMINATE_GRACE_SECONDS)
        except (OSError, subprocess.SubprocessError):
            pass
    finally:
        _kill_remaining_process_group(process.pid)


def _kill_remaining_process_group(process_group_id: int) -> None:
    if os.name != "posix":
        return
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except OSError:
        pass


def _render_output(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout.rstrip()}\n[stderr]\n{stderr.rstrip()}"
    return (stdout or stderr).rstrip()


def _result(
    *,
    success: bool,
    output: str,
    error_code: str | None,
    command_family: str,
    exit_code: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
    stdout_bytes: int,
    stderr_bytes: int,
    output_truncated: bool,
) -> ToolResult:
    return ToolResult(
        success,
        TOOL_ID,
        output,
        error_code=error_code,
        metadata={
            "command_family": command_family,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "output_truncated": output_truncated,
        },
    )


def run_command(
    argv: object,
    timeout_seconds: object = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: object = DEFAULT_MAX_OUTPUT_BYTES,
    *,
    workspace: Workspace | None = None,
) -> ToolResult:
    """Run one policy-approved argv vector without shell interpretation."""

    active_workspace = workspace or Workspace()
    try:
        timeout = _bounded_number(
            timeout_seconds,
            default=DEFAULT_TIMEOUT_SECONDS,
            maximum=MAX_TIMEOUT_SECONDS,
            name="timeout_seconds",
        )
        output_limit = _bounded_number(
            max_output_bytes,
            default=DEFAULT_MAX_OUTPUT_BYTES,
            maximum=MAX_OUTPUT_BYTES,
            name="max_output_bytes",
        )
        if not isinstance(output_limit, int):
            raise CommandPolicyError("invalid_arguments", "max_output_bytes must be an integer")
        approved = validate_command(argv, active_workspace)
    except CommandPolicyError as exc:
        return _result(
            success=False,
            output=exc.message,
            error_code=exc.code,
            command_family="unapproved",
            exit_code=None,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
        )
    except Exception:
        return _result(
            success=False,
            output="Command validation failed safely",
            error_code="validation_failed",
            command_family="unapproved",
            exit_code=None,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
        )

    capture = _BoundedCapture(output_limit)
    try:
        process = subprocess.Popen(
            approved.execution_argv,
            cwd=active_workspace.root,
            env=_safe_environment(active_workspace, approved.family),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=os.name == "posix",
        )
    except (OSError, subprocess.SubprocessError):
        return _result(
            success=False,
            output="Approved command could not start",
            error_code="command_unavailable",
            command_family=approved.family,
            exit_code=None,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
        )

    if process.stdout is None or process.stderr is None:
        _stop_process(process)
        return _result(
            success=False,
            output="Command output capture failed safely",
            error_code="execution_failed",
            command_family=approved.family,
            exit_code=process.returncode,
            timed_out=False,
            stdout="",
            stderr="",
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
        )
    readers = (
        threading.Thread(target=_read_stream, args=(process.stdout, "stdout", capture), daemon=True),
        threading.Thread(target=_read_stream, args=(process.stderr, "stderr", capture), daemon=True),
    )
    started_readers: list[threading.Thread] = []
    try:
        for reader in readers:
            reader.start()
            started_readers.append(reader)
    except RuntimeError:
        _stop_process(process)
        for reader in started_readers:
            reader.join(timeout=TERMINATE_GRACE_SECONDS)
        return _result(
            success=False,
            output="Command output capture failed safely",
            error_code="execution_failed",
            command_family=approved.family,
            exit_code=process.returncode,
            timed_out=False,
            stdout=capture.text("stdout"),
            stderr=capture.text("stderr"),
            stdout_bytes=capture.total("stdout"),
            stderr_bytes=capture.total("stderr"),
            output_truncated=capture.truncated,
        )

    timed_out = False
    process_error = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process(process)
    except (OSError, subprocess.SubprocessError):
        process_error = True
        _stop_process(process)
    else:
        _kill_remaining_process_group(process.pid)

    for reader in readers:
        reader.join(timeout=TERMINATE_GRACE_SECONDS)

    stdout = capture.text("stdout")
    stderr = capture.text("stderr")
    rendered = _render_output(stdout, stderr)
    if timed_out:
        return _result(
            success=False,
            output=rendered or "Command timed out",
            error_code="timeout",
            command_family=approved.family,
            exit_code=process.returncode,
            timed_out=True,
            stdout=stdout,
            stderr=stderr,
            stdout_bytes=capture.total("stdout"),
            stderr_bytes=capture.total("stderr"),
            output_truncated=capture.truncated,
        )
    if process_error:
        return _result(
            success=False,
            output=rendered or "Command execution failed safely",
            error_code="execution_failed",
            command_family=approved.family,
            exit_code=process.returncode,
            timed_out=False,
            stdout=stdout,
            stderr=stderr,
            stdout_bytes=capture.total("stdout"),
            stderr_bytes=capture.total("stderr"),
            output_truncated=capture.truncated,
        )

    exit_code = process.returncode
    return _result(
        success=exit_code == 0,
        output=rendered,
        error_code=None if exit_code == 0 else "command_failed",
        command_family=approved.family,
        exit_code=exit_code,
        timed_out=False,
        stdout=stdout,
        stderr=stderr,
        stdout_bytes=capture.total("stdout"),
        stderr_bytes=capture.total("stderr"),
        output_truncated=capture.truncated,
    )
