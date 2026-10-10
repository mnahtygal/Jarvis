"""Fixed argument policy for controlled Developer Agent commands."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
import unicodedata

from core.developer_agent.workspace import Workspace, WorkspacePathError


MAX_ARGUMENTS = 128
MAX_ARGUMENT_BYTES = 4096
MAX_TOTAL_ARGUMENT_BYTES = 32 * 1024
SAFE_SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"

_SHELL_SYNTAX = frozenset("\n\r;&|><`$")
_GIT_ARGUMENTS = frozenset({
    ("status", "--short", "--branch"),
    ("diff",),
    ("diff", "--check"),
    ("diff", "--cached"),
    ("diff", "--cached", "--check"),
    ("branch", "--show-current"),
})
_PYTEST_FLAGS = frozenset({
    "-q",
    "-s",
    "-x",
    "--collect-only",
    "--disable-warnings",
    "--strict-config",
    "--strict-markers",
})
_PYTEST_VALUE_OPTIONS = frozenset({"-k", "-m"})
_PYTEST_TB_VALUES = frozenset({"auto", "long", "short", "line", "native", "no"})


class CommandPolicyError(ValueError):
    """Stable command refusal without exposing local execution details."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ApprovedCommand:
    """Validated command with a policy-selected executable vector."""

    requested_argv: tuple[str, ...]
    execution_argv: tuple[str, ...]
    family: str


def _fixed_executable(name: str) -> str:
    executable = shutil.which(name, path=SAFE_SYSTEM_PATH)
    if executable is None:
        raise CommandPolicyError("command_unavailable", "Approved command is unavailable")
    return str(Path(executable).resolve(strict=True))


def _python_executable(workspace: Workspace) -> str:
    candidate = Path(sys.executable)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        raise CommandPolicyError("command_unavailable", "Approved Python is unavailable") from None
    if (
        not candidate.is_absolute()
        or not resolved.is_file()
        or not os.access(resolved, os.X_OK)
        or resolved.is_relative_to(workspace.root)
    ):
        raise CommandPolicyError("command_unavailable", "Approved Python is unavailable")
    return str(candidate)


def _validated_argv(argv: object) -> tuple[str, ...]:
    if not isinstance(argv, (list, tuple)) or not argv:
        raise CommandPolicyError("invalid_argv", "argv must be a non-empty list or tuple")
    if len(argv) > MAX_ARGUMENTS:
        raise CommandPolicyError("too_many_arguments", "Command has too many arguments")

    validated: list[str] = []
    total_bytes = 0
    for item in argv:
        if not isinstance(item, str) or not item or "\x00" in item:
            raise CommandPolicyError("invalid_argument", "Command arguments must be non-empty text")
        if any(unicodedata.category(character).startswith("C") for character in item):
            raise CommandPolicyError("invalid_argument", "Control characters are not allowed")
        try:
            encoded_length = len(item.encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            raise CommandPolicyError("invalid_argument", "Command argument encoding is invalid") from None
        if encoded_length > MAX_ARGUMENT_BYTES:
            raise CommandPolicyError("argument_too_long", "A command argument is too long")
        total_bytes += encoded_length
        if total_bytes > MAX_TOTAL_ARGUMENT_BYTES:
            raise CommandPolicyError("arguments_too_large", "Command arguments exceed the size limit")
        if any(character in item for character in _SHELL_SYNTAX):
            raise CommandPolicyError("shell_syntax", "Shell syntax is not allowed")
        validated.append(item)
    return tuple(validated)


def _workspace_path(value: str, workspace: Workspace, *, python_only: bool = False) -> str:
    if value.startswith("@"):
        raise CommandPolicyError("argument_file", "Argument files are not allowed")
    try:
        resolved = workspace.resolve_path(value)
    except WorkspacePathError:
        raise CommandPolicyError("path_not_allowed", "Command path is outside the workspace or missing") from None
    if python_only and (not resolved.is_file() or resolved.suffix.casefold() != ".py"):
        raise CommandPolicyError("path_not_allowed", "py_compile accepts workspace Python files only")
    return str(resolved)


def _pytest_target(value: str, workspace: Workspace) -> str:
    path_text, separator, selector = value.partition("::")
    if not path_text or (separator and not selector):
        raise CommandPolicyError("invalid_pytest_target", "Pytest target is invalid")
    resolved = _workspace_path(path_text, workspace)
    return f"{resolved}::{selector}" if separator else resolved


def _positive_integer(value: str, *, maximum: int) -> bool:
    try:
        number = int(value)
    except ValueError:
        return False
    return str(number) == value and 1 <= number <= maximum


def _pytest_arguments(arguments: tuple[str, ...], workspace: Workspace) -> tuple[str, ...]:
    approved: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in _PYTEST_FLAGS:
            approved.append(argument)
        elif argument in _PYTEST_VALUE_OPTIONS:
            index += 1
            if index >= len(arguments) or not arguments[index]:
                raise CommandPolicyError("invalid_pytest_option", "Pytest option value is missing")
            approved.extend((argument, arguments[index]))
        elif argument == "--ignore":
            index += 1
            if index >= len(arguments):
                raise CommandPolicyError("invalid_pytest_option", "Pytest ignore path is missing")
            approved.extend((argument, _workspace_path(arguments[index], workspace)))
        elif argument.startswith("--ignore="):
            path = argument.removeprefix("--ignore=")
            approved.append(f"--ignore={_workspace_path(path, workspace)}")
        elif argument.startswith("--maxfail="):
            value = argument.removeprefix("--maxfail=")
            if not _positive_integer(value, maximum=100):
                raise CommandPolicyError("invalid_pytest_option", "Pytest maxfail value is invalid")
            approved.append(argument)
        elif argument.startswith("--tb="):
            if argument.removeprefix("--tb=") not in _PYTEST_TB_VALUES:
                raise CommandPolicyError("invalid_pytest_option", "Pytest traceback mode is invalid")
            approved.append(argument)
        elif argument.startswith("-"):
            raise CommandPolicyError("disallowed_option", "Pytest option is not allowed")
        else:
            approved.append(_pytest_target(argument, workspace))
        index += 1
    return tuple(approved)


def _compileall_arguments(arguments: tuple[str, ...], workspace: Workspace) -> tuple[str, ...]:
    approved: list[str] = []
    paths = 0
    for argument in arguments:
        if argument == "-q":
            approved.append(argument)
        elif argument.startswith("-"):
            raise CommandPolicyError("disallowed_option", "compileall option is not allowed")
        else:
            approved.append(_workspace_path(argument, workspace))
            paths += 1
    if paths == 0:
        raise CommandPolicyError("path_required", "compileall requires a workspace path")
    return tuple(approved)


def _py_compile_arguments(arguments: tuple[str, ...], workspace: Workspace) -> tuple[str, ...]:
    if not arguments:
        raise CommandPolicyError("path_required", "py_compile requires a workspace Python file")
    if any(argument.startswith("-") for argument in arguments):
        raise CommandPolicyError("disallowed_option", "py_compile options are not allowed")
    return tuple(_workspace_path(argument, workspace, python_only=True) for argument in arguments)


def validate_command(argv: object, workspace: Workspace) -> ApprovedCommand:
    """Validate an argv-only request against fixed command grammars."""

    requested = _validated_argv(argv)
    executable, arguments = requested[0], requested[1:]

    if executable == "pwd" and not arguments:
        return ApprovedCommand(requested, (_fixed_executable("pwd"),), "pwd")

    if executable == "git":
        if arguments not in _GIT_ARGUMENTS:
            raise CommandPolicyError("git_operation_not_allowed", "Git operation is not allowed")
        safe_git_prefix = (
            _fixed_executable("git"),
            "--no-pager",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "diff.external=",
        )
        if arguments[0] == "diff":
            arguments = (
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                *arguments[1:],
            )
        return ApprovedCommand(
            requested,
            (*safe_git_prefix, *arguments),
            "git",
        )

    module: str | None = None
    module_arguments: tuple[str, ...] = ()
    if executable in {"python", "python3"}:
        if len(arguments) < 2 or arguments[0] != "-m":
            raise CommandPolicyError("python_form_not_allowed", "Only approved Python modules may run")
        module = arguments[1]
        module_arguments = arguments[2:]
    elif executable == "pytest":
        module = "pytest"
        module_arguments = arguments
    else:
        raise CommandPolicyError("executable_not_allowed", "Executable is not allowed")

    if module == "pytest":
        approved_arguments = _pytest_arguments(module_arguments, workspace)
        approved_arguments = (
            "-c",
            "/dev/null",
            f"--rootdir={workspace.root}",
            f"--confcutdir={workspace.root}",
            *approved_arguments,
        )
    elif module == "compileall":
        approved_arguments = _compileall_arguments(module_arguments, workspace)
        approved_arguments = ("-e", str(workspace.root), *approved_arguments)
    elif module == "py_compile":
        approved_arguments = _py_compile_arguments(module_arguments, workspace)
    else:
        raise CommandPolicyError("python_module_not_allowed", "Python module is not allowed")

    return ApprovedCommand(
        requested,
        (_python_executable(workspace), "-m", module, *approved_arguments),
        module,
    )
