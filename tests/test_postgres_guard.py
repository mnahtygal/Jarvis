import os
from pathlib import Path
import subprocess
import sys
from textwrap import dedent


def test_postgres_guard_covers_collection_aliases_and_fixture_lifecycle(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "conftest.py").write_text(dedent("""
        import pytest
        from __main__ import old_connect

        with pytest.raises(AssertionError, match="PostgreSQL connections are blocked"):
            old_connect()
    """), encoding="utf-8")
    (tmp_path / "test_probe.py").write_text(dedent("""
        from unittest.mock import Mock

        import psycopg2
        import pytest
        from psycopg2 import connect as collection_alias
        from psycopg2._psycopg import _connect as native_alias

        def expect_blocked(connect):
            with pytest.raises(AssertionError, match="PostgreSQL connections are blocked"):
                connect()

        expect_blocked(collection_alias)
        expect_blocked(native_alias)

        @pytest.fixture(scope="session", autouse=True)
        def session_probe():
            expect_blocked(collection_alias)
            yield
            expect_blocked(collection_alias)

        def test_call(monkeypatch):
            expect_blocked(psycopg2.connect)
            with monkeypatch.context() as patch:
                fake = Mock(return_value="fake connection")
                patch.setattr(psycopg2, "connect", fake)
                assert psycopg2.connect() == "fake connection"
                fake.assert_called_once_with()
            expect_blocked(psycopg2.connect)
    """), encoding="utf-8")
    # The sentinel makes this probe safe even if the pytest plugin fails to load.
    bootstrap = dedent("""
        import sys
        import psycopg2
        import pytest

        old_connect = psycopg2.connect

        def sentinel(*args, **kwargs):
            raise AssertionError("pytest guard did not intercept the probe")

        psycopg2._connect = sentinel
        psycopg2._psycopg._connect = sentinel
        sys.exit(pytest.main(sys.argv[1:]))
    """)
    env = {**os.environ, "PYTEST_ADDOPTS": "", "PYTEST_PLUGINS": "",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = subprocess.run(
        [sys.executable, "-c", bootstrap, "-c", str(root / "pytest.ini"),
         "-q", str(tmp_path / "test_probe.py")],
        cwd=root, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "7 (startup/session=1, collection/import=2, setup=1, call=2, teardown=1)"
        in result.stdout
    )
