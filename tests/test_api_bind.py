"""Regression coverage for the local-only Flask API listener."""

from pathlib import Path
from unittest.mock import Mock

import api


def test_api_server_binds_only_to_ipv4_loopback(monkeypatch):
    run = Mock()
    monkeypatch.setattr(api.app, "run", run)

    api._run_api_server()

    assert api.API_BIND_HOST == "127.0.0.1"
    assert api.API_PORT == 5000
    run.assert_called_once_with(host="127.0.0.1", port=5000)


def test_startup_and_status_scripts_probe_the_loopback_api():
    root = Path(__file__).parents[1]
    for relative_path in (
        "core/boot/boot-v3.sh",
        "scripts/start-jarvis.sh",
        "scripts/jarvis-health.sh",
        "scripts/jarvis-status.sh",
    ):
        source = (root / relative_path).read_text(encoding="utf-8")
        assert "http://127.0.0.1:5000" in source


def test_api_source_contains_no_wildcard_flask_listener():
    source = Path(api.__file__).read_text(encoding="utf-8")
    assert 'app.run(host="0.0.0.0"' not in source
