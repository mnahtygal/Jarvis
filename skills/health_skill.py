# skills/health_skill.py

from typing import Dict, List, Tuple

import requests

from core.db import get_connection
from core.memory import get_all_memories
from core.session import get_recent_history, get_last_topic
from core.context import build_context_summary


CheckResult = Tuple[bool, str]


def _check_postgres() -> CheckResult:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]

        short_version = version.split(",")[0]
        return True, short_version

    except Exception as error:
        return False, str(error)


def _check_session_state() -> CheckResult:
    try:
        last_topic = get_last_topic()

        if not last_topic:
            return False, "session_state readable, but last_topic is empty"

        return True, f"last_topic={last_topic}"

    except Exception as error:
        return False, str(error)


def _check_memories() -> CheckResult:
    try:
        memories = get_all_memories()
        count = len(memories)

        if count == 0:
            return False, "no long-term memories found"

        return True, f"{count} memories found"

    except Exception as error:
        return False, str(error)


def _check_conversation_history() -> CheckResult:
    try:
        history = get_recent_history(limit=5)
        count = len(history)

        if count == 0:
            return False, "no recent conversation history found"

        return True, f"{count} recent rows found"

    except Exception as error:
        return False, str(error)


def _check_context_builder() -> CheckResult:
    try:
        summary = build_context_summary(history_limit=3)

        if not summary.strip():
            return False, "context summary was empty"

        required_sections = [
            "Last topic:",
            "Long-term memory:",
            "Recent conversation:",
        ]

        missing = [section for section in required_sections if section not in summary]

        if missing:
            return False, f"missing sections: {', '.join(missing)}"

        return True, "context summary built"

    except Exception as error:
        return False, str(error)



def _check_semantic_memory() -> CheckResult:
    try:
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
                    return False, "vector extension is not enabled"

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
                    return False, "semantic_memories table does not exist"

                cur.execute("SELECT COUNT(*) FROM semantic_memories;")
                row_count = cur.fetchone()[0]

        return True, f"vector enabled, semantic_memories rows={row_count}"

    except Exception as error:
        return False, str(error)

def _check_llama_cpp() -> CheckResult:
    try:
        response = requests.get(
            "http://127.0.0.1:8080/v1/models",
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()
        model_count = len(data.get("data", []))

        if model_count == 0:
            return False, "reachable but no models returned"

        return True, f"reachable, models={model_count}"

    except Exception as error:
        return False, str(error)


def _check_ollama() -> CheckResult:
    try:
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()
        models = data.get("models", [])
        model_names = [model.get("name", "unknown") for model in models]

        if not model_names:
            return False, "reachable but no models listed"

        preview = ", ".join(model_names[:3])
        return True, f"reachable, models: {preview}"

    except Exception as error:
        return False, str(error)


def get_health_report() -> dict:
    checks = {
        "PostgreSQL": _check_postgres(),
        "Session state": _check_session_state(),
        "Long-term memories": _check_memories(),
        "Conversation history": _check_conversation_history(),
        "Context builder": _check_context_builder(),
        "Semantic memory": _check_semantic_memory(),
        "llama.cpp": _check_llama_cpp(),
        "Ollama": _check_ollama(),
    }

    hard_failures = []

    for name, result in checks.items():
        passed, detail = result

        if not passed:
            hard_failures.append((name, detail))

    return {
        "ready": len(hard_failures) == 0,
        "checks": checks,
        "hard_failures": hard_failures,
    }


def get_health_response() -> str:
    report = get_health_report()

    if report["ready"]:
        lines = [
            "Jarvis health check: READY, Marty.",
            "",
            "Systems:",
        ]
    else:
        lines = [
            "Jarvis health check: needs attention, Marty.",
            "",
            "Systems:",
        ]

    for name, result in report["checks"].items():
        passed, detail = result
        status = "PASS" if passed else "FAIL"
        lines.append(f"- {status}: {name} - {detail}")

    return "\n".join(lines)
