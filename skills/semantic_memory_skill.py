# skills/semantic_memory_skill.py

"""
Jarvis semantic memory skill.

Provides direct commands for inspecting and searching pgvector semantic memory:

- semantic memory status
- show semantic memories
- semantic search: <query>
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.db import get_connection
from core.semantic_memory import (
    count_semantic_memories,
    format_semantic_results,
    get_embedding_model,
    search_semantic_memories,
)


LOCAL_EMBEDDING_PATH = (
    Path.home() / "jarvis" / "models" / "embeddings" / "all-MiniLM-L6-v2"
)


def _format_created_at(value: Any) -> str:
    if value is None:
        return "unknown"

    return str(value).split(".")[0]


def get_semantic_memory_status_response() -> str:
    """
    Return a quick status report for semantic memory.
    """
    try:
        count = count_semantic_memories()
    except Exception as error:
        return f"Semantic memory status: OFFLINE\n- Error: {error}"

    embedding_status = "missing"

    if LOCAL_EMBEDDING_PATH.exists():
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
            embedding_status = f"incomplete, missing: {', '.join(missing)}"
        else:
            embedding_status = "local/offline model present"

    try:
        _ = get_embedding_model()
        model_load_status = "loads successfully"
    except Exception as error:
        model_load_status = f"load failed: {error}"

    return "\n".join(
        [
            "Semantic Memory Status:",
            f"- PostgreSQL/pgvector table: online",
            f"- Semantic memory rows: {count}",
            f"- Embedding path: {LOCAL_EMBEDDING_PATH}",
            f"- Embedding files: {embedding_status}",
            f"- Embedding model: {model_load_status}",
            "- External tokens/APIs: not required",
        ]
    )


def get_recent_semantic_memories_response(limit: int = 10) -> str:
    """
    Return the most recent semantic memories.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        source_type,
                        source_id,
                        content,
                        metadata,
                        created_at
                    FROM semantic_memories
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

    except Exception as error:
        return f"I couldn't read semantic memory, Marty. Error: {error}"

    if not rows:
        return "No semantic memories saved yet, Marty."

    lines = ["Recent Semantic Memories:"]

    for row in rows:
        memory_id = row[0]
        source_type = row[1]
        source_id = row[2] or "none"
        content = row[3]
        created_at = _format_created_at(row[5])

        lines.append(
            f"- #{memory_id} [{source_type}] source_id={source_id} created={created_at}: {content}"
        )

    return "\n".join(lines)


def get_semantic_search_response(query: str, limit: int = 5) -> str:
    """
    Run a semantic search and return formatted results.
    """
    cleaned = (query or "").strip()

    if not cleaned:
        return "Give me something to search for, Marty. Example: semantic search: Thor migration"

    try:
        results: List[Dict[str, Any]] = search_semantic_memories(cleaned, limit=limit)
    except Exception as error:
        return f"Semantic search failed, Marty. Error: {error}"

    if not results:
        return f"No semantic memories matched: {cleaned}"

    return "\n".join(
        [
            f"Semantic Search Results for: {cleaned}",
            format_semantic_results(results),
        ]
    )
