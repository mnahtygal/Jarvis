from pathlib import Path
import os

import pytest


@pytest.fixture(autouse=True)
def use_repository_candidate_launcher_for_tests(monkeypatch):
    """Exercise the reviewed build before its root-owned system installation."""

    launcher = (
        Path(__file__).resolve().parents[1]
        / "packaging/apparmor/jarvis-candidate-sandbox"
    )
    if os.environ.get("JARVIS_SYSTEM_ISOLATION_VERIFY") != "1" and launcher.is_file():
        monkeypatch.setattr(
            "core.developer_agent.candidate_verification._validate_candidate_launcher",
            lambda: launcher,
        )
