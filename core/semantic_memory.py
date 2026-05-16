# core/semantic_memory.py

"""
Semantic memory support for Jarvis using PostgreSQL + pgvector.

Jarvis local-only rule:
- Do not call external model APIs.
- Do not require Hugging Face tokens.
- Load the embedding model from a local folder by default.
- Run Hugging Face / Transformers libraries in offline mode.

Current table expectation:

    semantic_memories
    - id integer primary key
    - source_type text not null
    - source_id text
    - content text not null
    - metadata jsonb default '{}'
    - embedding vector(384)
    - created_at timestamp
    - updated_at timestamp

Current local embedding model path:

    ~/jarvis/models/embeddings/all-MiniLM-L6-v2

This model produces 384-dimensional vectors, matching the current table.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

# Force local/offline behavior before importing sentence-transformers.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from sentence_transformers import SentenceTransformer  # noqa: E402

from core.db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LOCAL_EMBEDDING_MODEL = str(
    PROJECT_ROOT / "models" / "embeddings" / "all-MiniLM-L6-v2"
)

DEFAULT_EMBEDDING_MODEL = os.getenv(
    "JARVIS_EMBEDDING_MODEL",
    DEFAULT_LOCAL_EMBEDDING_MODEL,
)

EMBEDDING_DIMENSIONS = int(os.getenv("JARVIS_EMBEDDING_DIMENSIONS", "384"))


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Load the local embedding model once and reuse it.

    This should not call Hugging Face Hub. The default model path is local.
    """
    model_path = Path(DEFAULT_EMBEDDING_MODEL).expanduser()

    if not model_path.exists():
        raise FileNotFoundError(
            "Local embedding model folder not found: "
            f"{model_path}. Copy the cached model into "
            "~/jarvis/models/embeddings/all-MiniLM-L6-v2 first."
        )

    return SentenceTransformer(str(model_path), local_files_only=True)


def get_embedding(text: str) -> List[float]:
    """
    Convert text into a 384-dimensional embedding vector.
    """
    cleaned = (text or "").strip()

    if not cleaned:
        raise ValueError("Cannot create embedding for empty text.")

    model = get_embedding_model()
    embedding = model.encode(cleaned, normalize_embeddings=True)

    vector = embedding.tolist()

    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding dimension mismatch. Expected {EMBEDDING_DIMENSIONS}, got {len(vector)}."
        )

    return vector


def vector_to_pgvector(vector: List[float]) -> str:
    """
    Convert a Python float list into pgvector text format.
    """
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def ensure_semantic_memory_schema() -> None:
    """
    Ensure pgvector extension and semantic_memories table exist.

    This is safe to run repeatedly.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id SERIAL PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    embedding VECTOR(384),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_source_type
                ON semantic_memories (source_type);
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_created_at
                ON semantic_memories (created_at);
                """
            )

        conn.commit()


def add_semantic_memory(
    content: str,
    source_type: str = "manual",
    source_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Store content as semantic memory and return the new row id.
    """
    cleaned = (content or "").strip()

    if not cleaned:
        raise ValueError("Cannot store empty semantic memory.")

    ensure_semantic_memory_schema()

    embedding = get_embedding(cleaned)
    embedding_text = vector_to_pgvector(embedding)
    metadata_json = json.dumps(metadata or {})

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO semantic_memories (
                    source_type,
                    source_id,
                    content,
                    metadata,
                    embedding,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s::vector, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id;
                """,
                (
                    source_type,
                    source_id,
                    cleaned,
                    metadata_json,
                    embedding_text,
                ),
            )

            memory_id = cur.fetchone()[0]

        conn.commit()

    return int(memory_id)


def search_semantic_memories(
    query: str,
    limit: int = 5,
    source_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search semantic memories by meaning.

    Uses cosine distance because embeddings are normalized.
    """
    cleaned = (query or "").strip()

    if not cleaned:
        return []

    ensure_semantic_memory_schema()

    query_embedding = get_embedding(cleaned)
    query_vector = vector_to_pgvector(query_embedding)

    if source_type:
        sql = """
            SELECT
                id,
                source_type,
                source_id,
                content,
                metadata,
                embedding <=> %s::vector AS distance,
                created_at
            FROM semantic_memories
            WHERE source_type = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        query_params = [query_vector, source_type, query_vector, limit]
    else:
        sql = """
            SELECT
                id,
                source_type,
                source_id,
                content,
                metadata,
                embedding <=> %s::vector AS distance,
                created_at
            FROM semantic_memories
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        query_params = [query_vector, query_vector, limit]

    results: List[Dict[str, Any]] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, query_params)

            for row in cur.fetchall():
                distance = float(row[5])
                similarity = 1.0 - distance

                results.append(
                    {
                        "id": row[0],
                        "source_type": row[1],
                        "source_id": row[2],
                        "content": row[3],
                        "metadata": row[4] or {},
                        "distance": distance,
                        "similarity": similarity,
                        "created_at": row[6],
                    }
                )

    return results


def count_semantic_memories() -> int:
    """
    Return number of semantic memory rows.
    """
    ensure_semantic_memory_schema()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM semantic_memories;")
            count = cur.fetchone()[0]

    return int(count)


def format_semantic_results(results: List[Dict[str, Any]]) -> str:
    """
    Format semantic search results for CLI/debugging/context injection.
    """
    if not results:
        return "No semantic memories found."

    lines = []

    for item in results:
        similarity = item.get("similarity", 0.0)
        content = item.get("content", "").strip()
        source_type = item.get("source_type", "unknown")
        memory_id = item.get("id", "?")

        lines.append(
            f"- #{memory_id} [{source_type}] similarity={similarity:.3f}: {content}"
        )

    return "\n".join(lines)
