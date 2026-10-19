import hashlib
import os
from pathlib import Path
import socket

import pytest

from core.developer_agent.candidate_verification import (
    CandidateIsolationError,
    CandidateVerification,
    _sandbox_argv,
    capture_session_baseline,
    promote_sealed_candidate,
    validate_session_baseline,
    verify_disposable_candidate,
)
from core.developer_agent.workspace import Workspace


PACKAGED_CANDIDATE_LAUNCHER = (
    Path(__file__).resolve().parents[1]
    / "packaging/apparmor/jarvis-candidate-sandbox"
)


def _fixture(tmp_path: Path) -> tuple[Workspace, Path, Path]:
    source = tmp_path / "calculator.py"
    test = tmp_path / "test_calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    test.write_text(
        "from calculator import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    return Workspace(tmp_path), source, test


def _repair() -> dict[str, object]:
    return {
        "tool": "developer.patch_file",
        "arguments": {
            "path": "calculator.py",
            "old_text": "return a - b",
            "new_text": "return a + b",
            "expected_matches": 1,
        },
    }


def _direct_candidate_path(tmp_path: Path, label: str) -> Path:
    identity = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:16]
    return Path("/tmp") / f"jarvis-candidate-{identity}-{label}"


def test_isolated_candidate_passes_and_promotes_exact_sealed_bytes(tmp_path):
    workspace, source, test = _fixture(tmp_path)
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )

    initial = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
    )
    candidate = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
        repair=_repair(),
        seal_path="calculator.py",
    )

    assert initial.verification is not None
    assert initial.verification.success is False
    assert candidate.status == "candidate_verification_passed"
    assert candidate.verification is not None and candidate.verification.success
    assert candidate.sealed_candidate is not None
    assert candidate.sealed_candidate.content == (
        b"def add(a, b):\n    return a + b\n"
    )
    assert candidate.sealed_candidate.sha256 == hashlib.sha256(
        candidate.sealed_candidate.content
    ).hexdigest()
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "__pycache__").exists()

    error = promote_sealed_candidate(
        workspace=workspace,
        baseline=baseline,
        proposal_repair=_repair(),
        sealed=candidate.sealed_candidate,
    )

    assert error is None
    assert source.read_bytes() == candidate.sealed_candidate.content
    assert test.read_bytes() == test_before


def test_failed_candidate_is_cleaned_and_original_is_unchanged(tmp_path, monkeypatch):
    workspace, source, test = _fixture(tmp_path)
    source_before = source.read_bytes()
    test_before = test.read_bytes()
    candidate_root = _direct_candidate_path(tmp_path, "failed")

    def make_candidate(*, prefix):
        assert prefix == "jarvis-candidate-"
        candidate_root.mkdir(mode=0o700)
        return str(candidate_root)

    monkeypatch.setattr(
        "core.developer_agent.candidate_verification.tempfile.mkdtemp",
        make_candidate,
    )
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )
    wrong = {
        "tool": "developer.patch_file",
        "arguments": {
            "path": "calculator.py",
            "old_text": "return a - b",
            "new_text": "return a * b",
            "expected_matches": 1,
        },
    }

    result = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
        repair=wrong,
        seal_path="calculator.py",
    )

    assert result.status == "candidate_verification_failed"
    assert result.sealed_candidate is None
    assert result.cleanup_succeeded is True
    assert not candidate_root.exists()
    assert source.read_bytes() == source_before
    assert test.read_bytes() == test_before


def test_candidate_tree_is_read_only_and_home_is_not_exposed(tmp_path):
    workspace = Workspace(tmp_path)
    source = tmp_path / "example.py"
    test = tmp_path / "test_example.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test.write_text(
        "from pathlib import Path\n\n"
        "def test_isolation():\n"
        "    assert not Path('/home').exists()\n"
        "    assert not Path('/root').exists()\n"
        "    assert not Path('/etc').exists()\n"
        "    assert not Path('/usr/bin/git').exists()\n"
        "    assert not Path('/usr/lib/git-core').exists()\n"
        "    assert not Path('/usr/lib/chatgpt').exists()\n"
        "    for path in (Path('example.py'), Path('test_example.py')):\n"
        "        try:\n"
        "            path.write_text('changed', encoding='utf-8')\n"
        "        except OSError:\n"
        "            pass\n"
        "        else:\n"
        "            raise AssertionError('candidate tree was writable')\n"
        "    assert not Path('.pytest_cache').exists()\n",
        encoding="utf-8",
    )
    baseline = capture_session_baseline(
        workspace,
        ("example.py", "test_example.py"),
    )

    result = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_example.py"),
    )

    assert result.status == "candidate_verification_passed"
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert "candidate tree was writable" not in result.verification.output


def test_candidate_network_namespace_cannot_reach_host_lan_or_external(tmp_path):
    workspace, _, test = _fixture(tmp_path)
    host_netns_identity = os.readlink("/proc/self/ns/net")
    route_probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        route_probe.connect(("198.51.100.1", 9))
        lan_address = route_probe.getsockname()[0]
    finally:
        route_probe.close()
    assert not lan_address.startswith("127.")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", 0))
    listener.listen(1)
    listener.settimeout(0.1)
    port = listener.getsockname()[1]
    test.write_text(
        "import os\n"
        "import socket\n\n"
        "def connection_is_blocked(host, port):\n"
        "    try:\n"
        "        with socket.create_connection((host, port), timeout=0.25):\n"
        "            return False\n"
        "    except OSError:\n"
        "        return True\n\n"
        "def test_network_isolation():\n"
        f"    assert os.readlink('/proc/self/ns/net') != {host_netns_identity!r}\n"
        f"    assert connection_is_blocked('127.0.0.1', {port})\n"
        f"    assert connection_is_blocked('{lan_address}', {port})\n"
        "    assert connection_is_blocked('1.1.1.1', 53)\n",
        encoding="utf-8",
    )
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )

    try:
        result = verify_disposable_candidate(
            workspace=workspace,
            baseline=baseline,
            verification_argv=("pytest", "-q", "test_calculator.py"),
        )
        with pytest.raises((TimeoutError, socket.timeout)):
            listener.accept()
    finally:
        listener.close()

    assert result.status == "candidate_verification_passed"
    assert result.verification is not None and result.verification.success


@pytest.mark.parametrize("changed_path", ["calculator.py", "test_calculator.py"])
def test_original_identity_change_blocks_promotion(tmp_path, changed_path):
    workspace, source, test = _fixture(tmp_path)
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )
    candidate = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
        repair=_repair(),
        seal_path="calculator.py",
    )
    assert candidate.sealed_candidate is not None
    target = source if changed_path == "calculator.py" else test
    target.write_bytes(target.read_bytes() + b"# concurrent change\n")

    assert validate_session_baseline(workspace, baseline) == "approved_file_changed"
    assert promote_sealed_candidate(
        workspace=workspace,
        baseline=baseline,
        proposal_repair=_repair(),
        sealed=candidate.sealed_candidate,
    ) == "approved_file_changed"


def test_candidate_seal_mismatch_blocks_promotion(tmp_path):
    workspace, source, _ = _fixture(tmp_path)
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )
    candidate = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
        repair=_repair(),
        seal_path="calculator.py",
    )
    sealed = candidate.sealed_candidate
    assert sealed is not None
    tampered = type(sealed)(
        sealed.path,
        sealed.content + b"# changed\n",
        sealed.sha256,
        sealed.size,
    )

    assert promote_sealed_candidate(
        workspace=workspace,
        baseline=baseline,
        proposal_repair=_repair(),
        sealed=tampered,
    ) == "candidate_seal_mismatch"
    assert source.read_text(encoding="utf-8").endswith("return a - b\n")


def test_cleanup_failure_never_returns_a_promotable_seal(tmp_path, monkeypatch):
    workspace, source, _ = _fixture(tmp_path)
    baseline = capture_session_baseline(
        workspace,
        ("calculator.py", "test_calculator.py"),
    )
    candidate_root = _direct_candidate_path(tmp_path, "cleanup")

    def make_candidate(*, prefix):
        assert prefix == "jarvis-candidate-"
        candidate_root.mkdir(mode=0o700)
        return str(candidate_root)

    monkeypatch.setattr(
        "core.developer_agent.candidate_verification.tempfile.mkdtemp",
        make_candidate,
    )
    monkeypatch.setattr(
        "core.developer_agent.candidate_verification._cleanup_candidate",
        lambda path: False,
    )

    result = verify_disposable_candidate(
        workspace=workspace,
        baseline=baseline,
        verification_argv=("pytest", "-q", "test_calculator.py"),
        repair=_repair(),
        seal_path="calculator.py",
    )

    assert result.status == "candidate_cleanup_failed"
    assert result.sealed_candidate is None
    assert result.cleanup_succeeded is False
    assert source.read_text(encoding="utf-8").endswith("return a - b\n")


def test_candidate_launcher_receives_only_fd_and_approved_pytest_arguments(tmp_path):
    workspace, _, _ = _fixture(tmp_path)
    candidate_root = tmp_path.parent / "candidate-for-argv"
    candidate_root.mkdir()
    descriptor = os.open(candidate_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        argv = _sandbox_argv(
            descriptor,
            ("pytest", "-q", "test_calculator.py"),
            workspace,
        )
    finally:
        os.close(descriptor)

    assert Path(argv[0]).name == "jarvis-candidate-sandbox"
    assert argv[1:] == (
        "--candidate-fd",
        str(descriptor),
        "-q",
        "test_calculator.py",
    )
    assert str(candidate_root) not in argv
    assert str(workspace.root) not in argv


def test_missing_candidate_launcher_fails_closed(tmp_path, monkeypatch):
    workspace, _, _ = _fixture(tmp_path)
    candidate_root = tmp_path.parent / "candidate-for-missing-unshare"
    candidate_root.mkdir()
    monkeypatch.setattr(
        "core.developer_agent.candidate_verification._validate_candidate_launcher",
        lambda: (_ for _ in ()).throw(
            CandidateIsolationError("candidate_isolation_unavailable")
        ),
    )
    descriptor = os.open(candidate_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(CandidateIsolationError) as caught:
            _sandbox_argv(
                descriptor,
                ("pytest", "-q", "test_calculator.py"),
                workspace,
            )
    finally:
        os.close(descriptor)

    assert caught.value.code == "candidate_isolation_unavailable"
