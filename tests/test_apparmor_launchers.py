import os
from pathlib import Path
import subprocess
import tempfile

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = REPOSITORY_ROOT / "packaging/apparmor"
API_ENTRY = PACKAGING_ROOT / "jarvis-api-entry"
CANDIDATE_SANDBOX = PACKAGING_ROOT / "jarvis-candidate-sandbox"
APPARMOR_PROFILE = PACKAGING_ROOT / "usr.libexec.jarvis-api-entry"


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


def test_api_launcher_uses_only_fixed_repository_pythonpath():
    source = (PACKAGING_ROOT / "src/jarvis-api-entry.c").read_text(encoding="utf-8")
    assert '#define REPOSITORY_PYTHONPATH REPOSITORY_ROOT' in source
    assert 'setenv("PYTHONPATH", REPOSITORY_PYTHONPATH, 1)' in source
    assert 'PYTHON_PATH, "-I"' not in source
    assert "clearenv()" in source


def test_apparmor_userns_gate_uses_enforced_transition_domains():
    profile = APPARMOR_PROFILE.read_text(encoding="utf-8")

    assert "flags=(default_allow)" not in profile
    assert profile.count("allow all,") == 3
    assert profile.count("audit deny change_profile,") == 3
    assert profile.count("audit deny userns create,") == 2
    assert profile.count("userns create,") == 3
    assert "network inet stream," in profile
    assert "network inet dgram," in profile
    assert "unix (create) type=stream," in profile
    assert (
        "/usr/libexec/jarvis-candidate-sandbox Cx -> candidate_userns," in profile
    )
    assert "/usr/bin/unshare ix," in profile
    assert (
        "/usr/bin/bwrap Px -> "
        "jarvis-api-entry//candidate_userns//candidate_runtime," in profile
    )
    assert (
        "profile candidate_runtime "
        "flags=(attach_disconnected.path=/run/jarvis-candidate-runtime/)" in profile
    )
    assert "      mount options=(rw silent rslave) -> /," in profile
    assert "      mount fstype=tmpfs options=(rw nosuid nodev)," in profile
    assert "      mount options=(rw rbind)," in profile
    assert "      mount fstype=proc options=(rw nosuid nodev noexec)," in profile
    assert "      mount fstype=devpts options=(rw nosuid noexec)," in profile
    assert "      mount options=(remount ro bind)," in profile
    assert "      mount options=(rw rprivate)," in profile
    assert "\n      mount,\n" not in profile
    assert "      umount," in profile
    assert "      pivot_root oldroot=/tmp/oldroot/ /tmp/," in profile


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
