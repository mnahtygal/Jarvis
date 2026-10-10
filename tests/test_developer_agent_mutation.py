import importlib
import stat
from pathlib import Path

import pytest

from core.developer_agent import Workspace, execute_tool
from core.developer_agent.mutation import MAX_FILE_BYTES
from core.developer_agent.tools.patch_file import patch_file
from core.developer_agent.tools.write_file import write_file


PROTECTED_AUDIO_TESTERS = (
    "audio_pipeline_tester.py",
    "audio_pipeline_tester_jarvis.py",
    "audio_pipeline_tester_jarvis_v2.py",
)


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_write_new_text_file(tmp_path):
    result = write_file("notes.txt", "hello\n", workspace=_workspace(tmp_path))

    assert result.success is True
    assert (tmp_path / "notes.txt").read_bytes() == b"hello\n"
    assert result.metadata == {
        "path": "notes.txt",
        "created": True,
        "overwritten": False,
        "bytes_written": 6,
    }


def test_existing_file_requires_explicit_overwrite(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("original", encoding="utf-8")
    target.chmod(0o640)
    original_mode = stat.S_IMODE(target.stat().st_mode)

    refused = write_file("notes.txt", "changed", workspace=_workspace(tmp_path))
    replaced = write_file(
        "notes.txt",
        "changed",
        overwrite=True,
        workspace=_workspace(tmp_path),
    )

    assert refused.success is False
    assert refused.error_code == "target_exists"
    assert replaced.success is True
    assert replaced.metadata["overwritten"] is True
    assert target.read_text(encoding="utf-8") == "changed"
    assert stat.S_IMODE(target.stat().st_mode) == original_mode


def test_parent_directory_creation_must_be_explicit(tmp_path):
    workspace = _workspace(tmp_path)

    refused = write_file("nested/path/notes.txt", "hello", workspace=workspace)
    created = write_file(
        "nested/path/notes.txt",
        "hello",
        create_parent_dirs=True,
        workspace=workspace,
    )

    assert refused.success is False
    assert refused.error_code == "parent_missing"
    assert created.success is True
    assert (tmp_path / "nested/path/notes.txt").read_text(encoding="utf-8") == "hello"


@pytest.mark.parametrize("operation", ["traversal", "absolute", "symlink"])
def test_write_rejects_workspace_escape(tmp_path, operation):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    if operation == "traversal":
        path = "../outside.txt"
    elif operation == "absolute":
        path = str(outside)
    else:
        (root / "escape").symlink_to(outside)
        path = "escape"

    result = write_file(path, "changed", overwrite=True, workspace=_workspace(root))

    assert result.success is False
    assert result.error_code == "outside_workspace"
    assert outside.read_text(encoding="utf-8") == "outside"


@pytest.mark.parametrize("path", [".env", ".env.local", "keys/server.pem", "secrets/data.txt"])
def test_write_rejects_sensitive_targets(tmp_path, path):
    result = write_file(
        path,
        "private",
        create_parent_dirs=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "sensitive_file"


def test_write_rejects_git_metadata_but_allows_gitignore(tmp_path):
    (tmp_path / ".git").mkdir()
    workspace = _workspace(tmp_path)

    protected = write_file(".git/config", "unsafe", workspace=workspace)
    allowed = write_file(".gitignore", "*.tmp\n", workspace=workspace)

    assert protected.success is False
    assert protected.error_code == "repository_metadata"
    assert allowed.success is True


def test_sensitive_policy_ignores_workspace_ancestor_names(tmp_path):
    root = tmp_path / "credentials-workspace"
    root.mkdir()

    result = write_file("normal.txt", "allowed", workspace=_workspace(root))

    assert result.success is True
    assert (root / "normal.txt").read_text(encoding="utf-8") == "allowed"


@pytest.mark.parametrize("filename", PROTECTED_AUDIO_TESTERS)
def test_write_rejects_protected_audio_testers(tmp_path, filename):
    result = write_file(filename, "changed", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "protected_file"
    assert not (tmp_path / filename).exists()


def test_write_rejects_oversized_or_binary_semantics(tmp_path):
    workspace = _workspace(tmp_path)

    oversized = write_file("large.txt", "x" * (MAX_FILE_BYTES + 1), workspace=workspace)
    binary = write_file("binary.txt", "text\x00data", workspace=workspace)

    assert oversized.success is False
    assert oversized.error_code == "content_too_large"
    assert binary.success is False
    assert binary.error_code == "binary_content"
    assert not (tmp_path / "large.txt").exists()
    assert not (tmp_path / "binary.txt").exists()


def test_patch_exact_single_match(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("before = 1\nafter = before\n", encoding="utf-8")

    result = patch_file(
        "code.py",
        "before = 1",
        "before = 2",
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.metadata["matches_replaced"] == 1
    assert target.read_text(encoding="utf-8") == "before = 2\nafter = before\n"


@pytest.mark.parametrize(
    "content,old_text,actual_matches",
    [("alpha beta", "missing", 0), ("alpha alpha", "alpha", 2)],
)
def test_patch_match_mismatch_never_modifies_file(
    tmp_path,
    content,
    old_text,
    actual_matches,
):
    target = tmp_path / "notes.txt"
    original = content.encode("utf-8")
    target.write_bytes(original)

    result = patch_file("notes.txt", old_text, "changed", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "match_mismatch"
    assert result.metadata["actual_matches"] == actual_matches
    assert target.read_bytes() == original


def test_patch_replaces_exact_expected_match_count(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("old old old", encoding="utf-8")

    result = patch_file(
        "notes.txt",
        "old",
        "new",
        expected_matches=3,
        workspace=_workspace(tmp_path),
    )

    assert result.success is True
    assert result.metadata["matches_replaced"] == 3
    assert target.read_text(encoding="utf-8") == "new new new"


def test_patch_rejects_empty_old_text_without_modification(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_bytes(b"unchanged")

    result = patch_file("notes.txt", "", "new", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code == "invalid_text"
    assert target.read_bytes() == b"unchanged"


@pytest.mark.parametrize("path", [".env", ".git/config", *PROTECTED_AUDIO_TESTERS])
def test_patch_rejects_sensitive_and_protected_targets(tmp_path, path):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")
    original = target.read_bytes()

    result = patch_file(path, "old", "new", workspace=_workspace(tmp_path))

    assert result.success is False
    assert result.error_code in {"sensitive_file", "repository_metadata", "protected_file"}
    assert target.read_bytes() == original


@pytest.mark.parametrize("operation", ["traversal", "absolute"])
def test_patch_rejects_paths_outside_workspace(tmp_path, operation):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("old", encoding="utf-8")
    path = "../outside.txt" if operation == "traversal" else str(outside)

    result = patch_file(path, "old", "new", workspace=_workspace(root))

    assert result.success is False
    assert result.error_code == "outside_workspace"
    assert outside.read_text(encoding="utf-8") == "old"


def test_mutation_executor_is_fixed_and_rejects_extra_arguments(tmp_path):
    workspace = _workspace(tmp_path)

    written = execute_tool(
        "developer.write_file",
        {"path": "notes.txt", "content": "hello"},
        workspace=workspace,
    )
    rejected = execute_tool(
        "developer.patch_file",
        {"path": "notes.txt", "old_text": "hello", "new_text": "bye", "regex": True},
        workspace=workspace,
    )

    assert written.success is True
    assert rejected.success is False
    assert rejected.error_code == "invalid_arguments"
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello"


def test_raw_os_exception_details_are_not_returned(tmp_path, monkeypatch):
    target = tmp_path / "notes.txt"
    target.write_text("old", encoding="utf-8")
    mutation_module = importlib.import_module("core.developer_agent.mutation")
    monkeypatch.setattr(
        mutation_module.os,
        "replace",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("private OS detail")),
    )

    result = write_file(
        "notes.txt",
        "new",
        overwrite=True,
        workspace=_workspace(tmp_path),
    )

    assert result.success is False
    assert result.error_code == "write_failed"
    assert "private OS detail" not in result.output
    assert "private OS detail" not in repr(result)
    assert target.read_text(encoding="utf-8") == "old"
