#!/usr/bin/env python3

"""
Jarvis Thor Health Check

Checks the local Jarvis runtime on NVIDIA Jetson AGX Thor:

- Python imports
- PostgreSQL connection
- PostgreSQL tables
- pgvector extension
- exact long-term memory
- semantic memory
- local/offline embedding model
- semantic search
- conversation history
- session state
- context builder
- llama.cpp model server
- Qwen3 model response
- CUDA / NVIDIA GPU visibility
- GGUF model files
- Git repo state

Exit code:
    0 = ready / no hard failures
    1 = one or more hard failures
"""

import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Force local/offline embedding behavior during health checks.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


LLAMA_MODELS_URL = os.getenv(
    "LLAMA_MODELS_URL",
    "http://127.0.0.1:8080/v1/models",
)

LLAMA_CHAT_URL = os.getenv(
    "LLAMA_CHAT_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)

LLAMA_MODEL_NAME = os.getenv(
    "LLAMA_CPP_MODEL",
    "Qwen3-30B-A3B-Q4_K_M.gguf",
)

MODEL_ROOT = Path(os.getenv("JARVIS_MODEL_ROOT", str(Path.home() / "models")))

LOCAL_EMBEDDING_PATH = Path(
    os.getenv(
        "JARVIS_EMBEDDING_MODEL",
        str(PROJECT_ROOT / "models" / "embeddings" / "all-MiniLM-L6-v2"),
    )
)


HealthResult = Tuple[bool, str, bool]
HealthCheck = Callable[[], HealthResult]


def print_header() -> None:
    print("")
    print("===================================")
    print(" Jarvis Thor Health Check")
    print("===================================")
    print("")


def pass_line(name: str, detail: str = "") -> None:
    if detail:
        print(f"[PASS] {name} - {detail}")
    else:
        print(f"[PASS] {name}")


def warn_line(name: str, detail: str = "") -> None:
    if detail:
        print(f"[WARN] {name} - {detail}")
    else:
        print(f"[WARN] {name}")


def fail_line(name: str, detail: str = "") -> None:
    if detail:
        print(f"[FAIL] {name} - {detail}")
    else:
        print(f"[FAIL] {name}")


def run_command(command: List[str], timeout: int = 10) -> Tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except FileNotFoundError as error:
        return 127, "", str(error)
    except subprocess.TimeoutExpired:
        return 124, "", f"command timed out after {timeout}s"


def run_check(name: str, check_func: HealthCheck) -> bool:
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


def check_system_identity() -> HealthResult:
    hostname = socket.gethostname()
    machine = platform.machine()
    system = platform.system()
    release = platform.release()

    detail = f"{hostname} | {system} {release} | {machine}"

    if hostname != "y-thor":
        return False, f"{detail} | expected hostname y-thor", True

    return True, detail, False


def check_python_imports() -> HealthResult:
    from core.db import get_connection
    from core.memory import get_all_memories
    from core.session import get_recent_history, get_last_topic
    from core.context import build_context_summary
    from core.semantic_memory import (
        count_semantic_memories,
        get_embedding_model,
        search_semantic_memories,
    )
    from skills.llm_skill import ask_local_llm
    from skills.llama_cpp_skill import get_llama_cpp_response
    from skills.brain_status_skill import get_brain_status_response
    from skills.semantic_memory_skill import get_semantic_memory_status_response

    _ = get_connection
    _ = get_all_memories
    _ = get_recent_history
    _ = get_last_topic
    _ = build_context_summary
    _ = count_semantic_memories
    _ = get_embedding_model
    _ = search_semantic_memories
    _ = ask_local_llm
    _ = get_llama_cpp_response
    _ = get_brain_status_response
    _ = get_semantic_memory_status_response

    return True, "core and skill modules imported", False


def check_cuda_nvcc() -> HealthResult:
    code, stdout, stderr = run_command(["nvcc", "--version"], timeout=10)

    if code != 0:
        return False, stderr or "nvcc not found", False

    last_line = stdout.splitlines()[-1] if stdout else "nvcc found"
    return True, last_line, False


def check_nvidia_smi() -> HealthResult:
    code, stdout, stderr = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total,memory.used,persistence_mode",
            "--format=csv,noheader",
        ],
        timeout=10,
    )

    if code != 0:
        return False, stderr or "nvidia-smi failed", False

    line = stdout.splitlines()[0] if stdout else "GPU detected"

    if "NVIDIA Thor" not in line:
        return False, line, True

    return True, line, False


def check_postgres_service() -> HealthResult:
    code, stdout, stderr = run_command(["systemctl", "is-active", "postgresql"], timeout=10)

    if code != 0:
        return False, stderr or stdout or "postgresql service not active", False

    return True, stdout, False


def check_llama_service() -> HealthResult:
    code, stdout, stderr = run_command(
        ["systemctl", "is-active", "jarvis-llama.service"],
        timeout=10,
    )

    if code != 0:
        return False, stderr or stdout or "jarvis-llama.service not active", False

    return True, stdout, False


def check_postgres_connection() -> HealthResult:
    from core.db import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]

    short_version = version.split(",")[0]
    return True, short_version, False


def check_postgres_tables() -> HealthResult:
    from core.db import get_connection

    required_tables = {
        "conversation_history",
        "memories",
        "memory_history",
        "semantic_memories",
        "session_state",
    }

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
                """
            )
            found_tables = {row[0] for row in cur.fetchall()}

    missing = sorted(required_tables - found_tables)

    if missing:
        return False, f"missing tables: {', '.join(missing)}", False

    return True, f"tables found: {', '.join(sorted(required_tables))}", False


def check_pgvector_extension() -> HealthResult:
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

    return True, "vector extension enabled", False


def check_session_state() -> HealthResult:
    from core.db import get_connection
    from core.session import get_last_topic

    with get_connection() as conn:
        with conn.cursor() as cur:
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


def check_exact_long_term_memories() -> HealthResult:
    from core.memory import get_all_memories

    memories = get_all_memories()
    count = len(memories)

    if count == 0:
        return False, "no exact long-term memories found", True

    return True, f"{count} exact memories found", False


def check_conversation_history() -> HealthResult:
    from core.session import get_recent_history

    history = get_recent_history(limit=5)
    count = len(history)

    if count == 0:
        return False, "no recent conversation history found", True

    return True, f"{count} recent rows found", False


def check_context_builder() -> HealthResult:
    from core.context import build_context_summary

    summary = build_context_summary(
        history_limit=3,
        user_text="How many people did Marty say were laid off at General Motors?",
    )

    if not summary.strip():
        return False, "context summary was empty", False

    required_sections = [
        "Last topic:",
        "Exact long-term memory:",
        "Semantic memory:",
        "Recent conversation:",
    ]

    missing = [section for section in required_sections if section not in summary]

    if missing:
        return False, f"missing sections: {', '.join(missing)}", False

    if "over 600 IT professionals" not in summary:
        return False, "context built but expected GM layoff semantic memory was not retrieved", True

    return True, "context summary built with semantic memory", False


def check_semantic_memory_table() -> HealthResult:
    from core.semantic_memory import count_semantic_memories

    row_count = count_semantic_memories()

    if row_count == 0:
        return False, "semantic_memories has zero rows", True

    return True, f"semantic_memories rows={row_count}", False


def check_local_embedding_files() -> HealthResult:
    if not LOCAL_EMBEDDING_PATH.exists():
        return False, f"missing local embedding path: {LOCAL_EMBEDDING_PATH}", False

    required_files = [
        "config.json",
        "modules.json",
        "model.safetensors",
        "tokenizer.json",
        "vocab.txt",
        "1_Pooling/config.json",
    ]

    missing = [
        item
        for item in required_files
        if not (LOCAL_EMBEDDING_PATH / item).exists()
    ]

    if missing:
        return False, f"missing embedding files: {', '.join(missing)}", False

    return True, f"local embedding files present at {LOCAL_EMBEDDING_PATH}", False


def check_local_embedding_model_loads() -> HealthResult:
    from core.semantic_memory import get_embedding_model

    model = get_embedding_model()
    model_name = str(model)

    return True, f"local/offline embedding model loads: {model_name[:120]}", False


def check_semantic_search_expected_memory() -> HealthResult:
    from core.semantic_memory import search_semantic_memories

    results = search_semantic_memories(
        "General Motors layoffs",
        limit=3,
    )

    if not results:
        return False, "semantic search returned no results", False

    top = results[0]
    content = top.get("content", "")
    similarity = float(top.get("similarity", 0.0))

    if "over 600 IT professionals" not in content:
        return False, f"top result did not match expected memory: {content}", True

    return True, f"expected GM memory found, similarity={similarity:.3f}", False


def check_llama_models_endpoint() -> HealthResult:
    response = requests.get(LLAMA_MODELS_URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    models = data.get("data", [])
    model_names = [model.get("id", "unknown") for model in models]

    if not model_names:
        return False, "server reachable but no models returned", True

    if LLAMA_MODEL_NAME not in model_names:
        return False, f"model list={', '.join(model_names)}", True

    return True, f"model online: {LLAMA_MODEL_NAME}", False


def check_llama_chat_completion() -> HealthResult:
    payload: Dict[str, object] = {
        "model": LLAMA_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are Jarvis. Answer briefly.",
            },
            {
                "role": "user",
                "content": "Say READY in one word.",
            },
        ],
        "max_tokens": 80,
        "temperature": 0.0,
        "stream": False,
    }

    response = requests.post(LLAMA_CHAT_URL, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content", "")

    if not content.strip():
        return False, "chat completion returned empty content", False

    cleaned = content.replace("<think>", "").replace("</think>", "").strip()
    short = " ".join(cleaned.split())[:120]

    return True, f"response={short}", False


def check_model_files() -> HealthResult:
    if not MODEL_ROOT.exists():
        return False, f"model root does not exist: {MODEL_ROOT}", False

    ggufs = sorted(MODEL_ROOT.rglob("*.gguf"))

    if not ggufs:
        return False, f"no GGUF files found under {MODEL_ROOT}", False

    names = [str(path.relative_to(MODEL_ROOT)) for path in ggufs]
    preview = ", ".join(names[:5])

    return True, f"{len(ggufs)} GGUF file(s): {preview}", False


def check_git_status() -> HealthResult:
    code, stdout, stderr = run_command(
        ["git", "-C", str(PROJECT_ROOT), "status", "--short"],
        timeout=10,
    )

    if code != 0:
        return False, stderr or "git status failed", True

    if stdout.strip():
        return False, f"working tree has changes: {stdout.replace(chr(10), '; ')}", True

    return True, "working tree clean", False


def check_git_remote() -> HealthResult:
    code, stdout, stderr = run_command(
        ["git", "-C", str(PROJECT_ROOT), "remote", "-v"],
        timeout=10,
    )

    if code != 0:
        return False, stderr or "git remote failed", True

    if "git@github.com:mnahtygal/Jarvis.git" not in stdout:
        return False, "origin is not SSH Jarvis remote", True

    return True, "origin uses GitHub SSH remote", False


def check_ollama_optional() -> HealthResult:
    url = "http://localhost:11434/api/tags"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except Exception as error:
        return False, f"optional fallback unavailable: {error}", True

    data = response.json()
    models = data.get("models", [])
    model_names = [model.get("name", "unknown") for model in models]

    if not model_names:
        return False, "Ollama reachable but no models listed", True

    preview = ", ".join(model_names[:3])
    return True, f"reachable, models: {preview}", False


def print_summary(hard_failures: int) -> None:
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

    checks: List[Tuple[str, HealthCheck]] = [
        ("System identity", check_system_identity),
        ("Python imports", check_python_imports),
        ("CUDA nvcc", check_cuda_nvcc),
        ("NVIDIA GPU", check_nvidia_smi),
        ("PostgreSQL service", check_postgres_service),
        ("Jarvis llama service", check_llama_service),
        ("PostgreSQL connection", check_postgres_connection),
        ("PostgreSQL tables", check_postgres_tables),
        ("pgvector extension", check_pgvector_extension),
        ("Session state", check_session_state),
        ("Exact long-term memories", check_exact_long_term_memories),
        ("Conversation history", check_conversation_history),
        ("Semantic memory table", check_semantic_memory_table),
        ("Local embedding files", check_local_embedding_files),
        ("Local embedding model", check_local_embedding_model_loads),
        ("Semantic search expected memory", check_semantic_search_expected_memory),
        ("Context builder", check_context_builder),
        ("llama.cpp models endpoint", check_llama_models_endpoint),
        ("llama.cpp chat completion", check_llama_chat_completion),
        ("Model files", check_model_files),
        ("Git remote", check_git_remote),
        ("Git status", check_git_status),
        ("Ollama server", check_ollama_optional),
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
