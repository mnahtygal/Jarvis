# skills/brain_status_skill.py

"""
Jarvis brain status skill.

Provides a quick in-Jarvis status report for the brain layer:
- runtime/model endpoint
- PostgreSQL
- exact memory
- semantic memory
- local embedding model
- last topic
- recent history
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import requests

from core.db import get_connection
from core.memory import get_all_memories
from core.session import get_last_topic, get_recent_history


LLAMA_MODELS_URL = os.getenv(
    "LLAMA_MODELS_URL",
    "http://127.0.0.1:8080/v1/models",
)

EXPECTED_MODEL = os.getenv(
    "LLAMA_CPP_MODEL",
    "Qwen3-30B-A3B-Q4_K_M.gguf",
)

LOCAL_EMBEDDING_PATH = Path(
    os.getenv(
        "JARVIS_EMBEDDING_MODEL",
        str(Path.home() / "jarvis" / "models" / "embeddings" / "all-MiniLM-L6-v2"),
    )
)


def _check_postgres() -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()

        return True, "online"
    except Exception as error:
        return False, f"offline ({error})"


def _count_semantic_memories() -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM semantic_memories;")
                count = cur.fetchone()[0]

        return True, f"online, {count} rows"
    except Exception as error:
        return False, f"offline ({error})"


def _check_llm_endpoint() -> Tuple[bool, str]:
    try:
        response = requests.get(LLAMA_MODELS_URL, timeout=5)
        response.raise_for_status()

        data = response.json()
        models = data.get("data", [])
        model_names = [model.get("id", "unknown") for model in models]

        if EXPECTED_MODEL in model_names:
            return True, f"online, model={EXPECTED_MODEL}"

        if model_names:
            return True, f"online, model(s)={', '.join(model_names)}"

        return False, "online but no model listed"

    except Exception as error:
        return False, f"offline ({error})"


def _check_embedding_model() -> Tuple[bool, str]:
    if not LOCAL_EMBEDDING_PATH.exists():
        return False, f"missing at {LOCAL_EMBEDDING_PATH}"

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
        return False, f"incomplete, missing: {', '.join(missing)}"

    return True, "online/offline-only local model present"


def get_brain_status_response() -> str:
    postgres_ok, postgres_detail = _check_postgres()
    semantic_ok, semantic_detail = _count_semantic_memories()
    llm_ok, llm_detail = _check_llm_endpoint()
    embedding_ok, embedding_detail = _check_embedding_model()

    memories = get_all_memories()
    exact_count = len(memories)

    recent_history = get_recent_history(limit=10)
    history_count = len(recent_history)

    last_topic = get_last_topic() or "None"

    overall_ready = all(
        [
            postgres_ok,
            semantic_ok,
            llm_ok,
            embedding_ok,
            exact_count >= 0,
        ]
    )

    status = "READY" if overall_ready else "NEEDS ATTENTION"

    lines = [
        "Jarvis Brain Status:",
        f"- Overall: {status}",
        "- Runtime: Thor / Qwen3 30B / llama.cpp",
        f"- PostgreSQL: {postgres_detail}",
        f"- Exact memory: online, {exact_count} facts",
        f"- Semantic memory: {semantic_detail}",
        f"- Last topic: {last_topic}",
        f"- Recent history rows checked: {history_count}",
        f"- LLM endpoint: {llm_detail}",
        f"- Local embeddings: {embedding_detail}",
    ]

    return "\n".join(lines)
