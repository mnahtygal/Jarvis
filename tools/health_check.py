#!/usr/bin/env python3

# tools/health_check.py

import sys
from pathlib import Path
from typing import Callable, Tuple

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_header():
    print("")
    print("===================================")
    print(" Jarvis Health Check")
    print("===================================")
    print("")


def pass_line(name: str, detail: str = ""):
    if detail:
        print(f"[PASS] {name} - {detail}")
    else:
        print(f"[PASS] {name}")


def warn_line(name: str, detail: str = ""):
    if detail:
        print(f"[WARN] {name} - {detail}")
    else:
        print(f"[WARN] {name}")


def fail_line(name: str, detail: str = ""):
    if detail:
        print(f"[FAIL] {name} - {detail}")
    else:
        print(f"[FAIL] {name}")


def run_check(name: str, check_func: Callable[[], Tuple[bool, str, bool]]) -> bool:
    """
    Run one health check.

    Returns True if the check passed or only warned.
    Returns False if the check failed hard.

    check_func returns:
        passed: bool
        detail: str
        warning_only: bool
    """

    try:
        passed, detail, warning_only = check_func()

        if passed:
            pass_line(name, detail)
            return True

        if warning_only:
            warn_line(name, detail)
            return True

        fail_line(name, detail)
        return False

    except Exception as error:
        fail_line(name, str(error))
        return False


def check_imports() -> Tuple[bool, str, bool]:
    from core.db import get_connection
    from core.memory import get_all_memories
    from core.session import get_recent_history, get_last_topic
    from core.context import build_context_summary
    from skills.llm_skill import ask_local_llm

    _ = get_connection
    _ = get_all_memories
    _ = get_recent_history
    _ = get_last_topic
    _ = build_context_summary
    _ = ask_local_llm

    return True, "core modules imported", False


def check_postgres() -> Tuple[bool, str, bool]:
    from core.db import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]

    short_version = version.split(",")[0]
    return True, short_version, False


def check_session_state() -> Tuple[bool, str, bool]:
    """
    Validate persistent session state.

    This checks:
    - session_state table exists
    - default session row can be read or created by current code
    - last_topic can be retrieved through core.session.get_last_topic()
    """

    from core.db import get_connection
    from core.session import get_last_topic

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'session_state'
                );
                """
            )

            table_exists = cur.fetchone()[0]

            if not table_exists:
                return False, "session_state table does not exist", False

            cur.execute(
                """
                SELECT session_id, last_topic, updated_at
                FROM session_state
                WHERE session_id = %s;
                """,
                ("default",),
            )

            row = cur.fetchone()

    last_topic = get_last_topic()

    if not row:
        return False, "session_state table exists but default row is missing", True

    if not last_topic:
        return False, "session_state is readable but last_topic is empty", True

    return True, f"last_topic={last_topic}", False


def check_memories() -> Tuple[bool, str, bool]:
    from core.memory import get_all_memories

    memories = get_all_memories()
    count = len(memories)

    if count == 0:
        return False, "no long-term memories found", True

    return True, f"{count} memories found", False


def check_conversation_history() -> Tuple[bool, str, bool]:
    from core.session import get_recent_history

    history = get_recent_history(limit=5)
    count = len(history)

    if count == 0:
        return False, "no recent conversation history found", True

    return True, f"{count} recent rows found", False


def check_context_builder() -> Tuple[bool, str, bool]:
    from core.context import build_context_summary

    summary = build_context_summary(history_limit=3)

    if not summary.strip():
        return False, "context summary was empty", False

    required_sections = [
        "Last topic:",
        "Long-term memory:",
        "Recent conversation:",
    ]

    missing = [section for section in required_sections if section not in summary]

    if missing:
        return False, f"missing sections: {', '.join(missing)}", False

    return True, "context summary built", False



def check_semantic_memory() -> Tuple[bool, str, bool]:
    """
    Validate pgvector semantic memory foundation.

    This checks:
    - vector extension is installed/enabled
    - semantic_memories table exists
    - semantic_memories row count can be read
    """

    from core.db import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'vector'
                );
                """
            )
            vector_enabled = cur.fetchone()[0]

            if not vector_enabled:
                return False, "vector extension is not enabled", False

            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'semantic_memories'
                );
                """
            )
            table_exists = cur.fetchone()[0]

            if not table_exists:
                return False, "semantic_memories table does not exist", False

            cur.execute("SELECT COUNT(*) FROM semantic_memories;")
            row_count = cur.fetchone()[0]

    return True, f"vector enabled, semantic_memories rows={row_count}", False

def check_llama_cpp() -> Tuple[bool, str, bool]:
    url = "http://127.0.0.1:8080/v1/models"

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    data = response.json()
    model_count = len(data.get("data", []))

    if model_count == 0:
        return False, "server reachable but no models returned", True

    return True, f"reachable on 127.0.0.1:8080, models={model_count}", False


def check_ollama() -> Tuple[bool, str, bool]:
    url = "http://localhost:11434/api/tags"

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    data = response.json()
    models = data.get("models", [])
    model_names = [model.get("name", "unknown") for model in models]

    if not model_names:
        return False, "Ollama reachable but no models listed", True

    preview = ", ".join(model_names[:3])
    return True, f"reachable, models: {preview}", False


def print_summary(hard_failures: int):
    print("")
    print("===================================")

    if hard_failures == 0:
        print(" Jarvis health check complete: READY")
    else:
        print(f" Jarvis health check complete: {hard_failures} hard failure(s)")

    print("===================================")
    print("")


def main() -> int:
    print_header()

    checks = [
        ("Python imports", check_imports),
        ("PostgreSQL connection", check_postgres),
        ("Session state", check_session_state),
        ("Long-term memories", check_memories),
        ("Conversation history", check_conversation_history),
        ("Context builder", check_context_builder),
        ("Semantic memory", check_semantic_memory),
        ("llama.cpp server", check_llama_cpp),
        ("Ollama server", check_ollama),
    ]

    hard_failures = 0

    for name, check_func in checks:
        ok = run_check(name, check_func)

        if not ok:
            hard_failures += 1

    print_summary(hard_failures)

    return 0 if hard_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
