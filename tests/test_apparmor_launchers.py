import os
from pathlib import Path
import subprocess
import tempfile

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = REPOSITORY_ROOT / "packaging/apparmor"
API_ENTRY = PACKAGING_ROOT / "jarvis-api-entry"
CANDIDATE_SANDBOX = PACKAGING_ROOT / "jarvis-candidate-sandbox"


def _run(argv: list[str], *, pass_fds: tuple[int, ...] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd="/",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
        pass_fds=pass_fds,
    )


def _candidate_directory() -> tuple[Path, int]:
    root = Path(tempfile.mkdtemp(prefix="jarvis-candidate-"))
    root.chmod(0o700)
    (root / "test_safe.py").write_text("def test_safe():\n    assert True\n", encoding="utf-8")
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    return root, descriptor


def test_launchers_are_native_elf_executables():
    assert API_ENTRY.read_bytes()[:4] == b"\x7fELF"
    assert CANDIDATE_SANDBOX.read_bytes()[:4] == b"\x7fELF"


@pytest.mark.parametrize("argument", ["--shell", "--help", "anything"])
def test_api_launcher_rejects_unknown_arguments(argument):
    result = _run([str(API_ENTRY), argument])
    assert result.returncode == 64
    assert "unsupported argument" in result.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ["--command", "/bin/sh"],
        ["/bin/sh"],
        ["--ro-bind", "/etc", "/etc"],
        ["--mount", "/home"],
        ["--setenv", "LD_PRELOAD", "/tmp/evil.so"],
        ["sh"],
    ],
    ids=[
        "arbitrary-command",
        "arbitrary-executable",
        "arbitrary-ro-bind",
        "arbitrary-mount",
        "arbitrary-environment",
        "general-namespace-shell",
    ],
)
def test_candidate_launcher_rejects_non_pytest_control_fields(arguments):
    root, descriptor = _candidate_directory()
    try:
        result = _run(
            [str(CANDIDATE_SANDBOX), "--candidate-fd", str(descriptor), *arguments],
            pass_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)
        for child in root.iterdir():
            child.unlink()
        root.rmdir()
    assert result.returncode == 64
    assert "unsupported pytest argument" in result.stderr


def test_candidate_launcher_rejects_unsafe_candidate_directory_identity(tmp_path):
    unsafe = tmp_path / "not-a-candidate"
    unsafe.mkdir(mode=0o700)
    descriptor = os.open(unsafe, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        result = _run(
            [str(CANDIDATE_SANDBOX), "--candidate-fd", str(descriptor), "-q"],
            pass_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)
    assert result.returncode == 65
    assert "unsafe candidate directory identity" in result.stderr


def test_candidate_launcher_rejects_arbitrary_absolute_test_path():
    root, descriptor = _candidate_directory()
    try:
        result = _run(
            [str(CANDIDATE_SANDBOX), "--candidate-fd", str(descriptor), "/etc/passwd"],
            pass_fds=(descriptor,),
        )
    finally:
        os.close(descriptor)
        for child in root.iterdir():
            child.unlink()
        root.rmdir()
    assert result.returncode == 64
    assert "unsupported pytest argument" in result.stderr
