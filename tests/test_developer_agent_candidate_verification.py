import hashlib
from pathlib import Path

import pytest

from core.developer_agent.candidate_verification import (
    CandidateVerification,
    SANDBOX_SITE_PACKAGES,
    _runtime_venv,
    _runtime_site_packages,
    _sandbox_argv,
    _system_runtime_roots,
    capture_session_baseline,
    promote_sealed_candidate,
    validate_session_baseline,
    verify_disposable_candidate,
)
from core.developer_agent.workspace import Workspace


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
    candidate_root = tmp_path / "disposable"

    def make_candidate(*, prefix):
        assert prefix == "jarvis-candidate-"
        candidate_root.mkdir()
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
    candidate_root = tmp_path / "cleanup-failure-candidate"

    def make_candidate(*, prefix):
        assert prefix == "jarvis-candidate-"
        candidate_root.mkdir()
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


def test_bubblewrap_invocation_exposes_only_fixed_runtime_and_candidate(tmp_path):
    workspace, _, _ = _fixture(tmp_path)
    candidate_root = tmp_path.parent / "candidate-for-argv"
    candidate_root.mkdir()
    argv = _sandbox_argv(
        candidate_root,
        ("pytest", "-q", "test_calculator.py"),
        workspace,
    )

    assert argv[0] == "/usr/bin/bwrap"
    assert "--unshare-net" in argv
    assert "--unshare-pid" in argv
    assert "--unshare-user" in argv
    assert "--unshare-user-try" not in argv
    assert "--cap-drop" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "--clearenv" in argv
    assert "--bind" not in argv
    assert "/usr/bin/git" not in argv
    shared_libraries, standard_library, loader_name = _system_runtime_roots()
    triples = tuple(zip(argv, argv[1:], argv[2:]))
    assert ("--ro-bind", str(shared_libraries), str(shared_libraries)) not in triples
    assert ("--ro-bind", str(standard_library), str(standard_library)) in triples
    assert ("--ro-bind", "/usr/lib", "/usr/lib") not in triples
    assert any(
        flag == "--ro-bind"
        and Path(destination).parent == shared_libraries
        and Path(source).parent == shared_libraries
        for flag, source, destination in triples
    )
    assert (
        "--symlink",
        f"{shared_libraries.name}/{loader_name}",
        f"/usr/lib/{loader_name}",
    ) in triples
    site_packages = _runtime_site_packages(_runtime_venv())
    runtime_index = argv.index(str(site_packages))
    assert argv[runtime_index - 1] == "--ro-bind"
    assert argv[runtime_index + 1] == str(SANDBOX_SITE_PACKAGES)
    assert str(_runtime_venv()) not in argv
    candidate_index = argv.index(str(candidate_root))
    assert argv[candidate_index - 1] == "--ro-bind"
    assert argv[candidate_index + 1] == "/workspace"
    assert str(workspace.root) not in argv
    assert "/home" not in argv
    assert "--unshare-net" in argv
    assert ("-p", "no:cacheprovider") in tuple(
        zip(argv, argv[1:])
    )
