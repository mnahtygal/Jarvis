"""Block Jarvis's PostgreSQL driver within the pytest process."""

from collections import Counter
from contextlib import contextmanager
from threading import Lock

import psycopg2
import pytest


_attempts = Counter()
_lock = Lock()
_phase = "startup/session"


def _blocked_connect(*args, **kwargs):
    with _lock:
        _attempts[_phase] += 1
    raise AssertionError("PostgreSQL connections are blocked during tests")


# Install as soon as pytest loads this plugin, before conftest and test imports.
# The Python connect wrapper resolves _connect at call time, so even an alias
# to that wrapper captured before plugin load reaches the blocker.
psycopg2.connect = _blocked_connect
psycopg2._connect = _blocked_connect
psycopg2._psycopg._connect = _blocked_connect


@contextmanager
def _during(phase):
    global _phase
    previous = _phase
    _phase = phase
    try:
        yield
    finally:
        _phase = previous


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection():
    with _during("collection/import"):
        return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_setup():
    with _during("setup"):
        return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_call():
    with _during("call"):
        return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown():
    with _during("teardown"):
        return (yield)


def pytest_terminal_summary(terminalreporter):
    with _lock:
        phases = ", ".join(
            f"{phase}={_attempts[phase]}"
            for phase in ("startup/session", "collection/import", "setup", "call", "teardown")
        )
        total = sum(_attempts.values())
    terminalreporter.write_line(f"Blocked PostgreSQL connection attempts: {total} ({phases})")
