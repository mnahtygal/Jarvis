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


SOURCE_TYPE_BOOSTS = {
    # Seed memories are curated/high-trust baseline facts.
    "seed": 0.15,

    # Project/runtime facts are high-value Jarvis identity and roadmap memories.
    "project": 0.10,
    "project_note": 0.10,
    "runtime": 0.10,

    # User notes are useful but can be noisy/freeform.
    "user_note": 0.00,
    "manual": 0.00,
}


CATEGORY_BOOSTS = {
    # These categories are useful for reasoning and should get a small lift.
    "preference": 0.08,
    "project": 0.08,
    "runtime": 0.08,
    "hardware": 0.06,
    "cruise": 0.06,
    "work": 0.04,
    "personal": 0.04,

    # Test memories should be de-prioritized so they do not pollute answers.
    "test": -0.05,

    # Unknown is neutral.
    "unknown": 0.00,
}


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


def infer_memory_category(content: str, source_type: str = "") -> str:
    """
    Infer a simple semantic memory category.

    This is intentionally conservative and does not require a database schema change.
    Categories are stored in metadata when new memories are added, but can also be
    inferred at search time for older rows.
    """
    text = f"{source_type} {content}".lower()

    # Test/dev notes should be easy to de-prioritize.
    if any(
        phrase in text
        for phrase in [
            "test",
            "colon works",
            "save colon works",
            "note colon works",
            "duplicate detection",
        ]
    ):
        return "test"

    # Runtime/hardware facts.
    if any(
        word in text
        for word in [
            "thor",
            "cuda",
            "llama.cpp",
            "qwen",
            "hardware",
            "gpu",
            "jetson",
            "nvidia",
        ]
    ):
        return "hardware"

    # Jarvis project direction/capability facts.
    if any(
        phrase in text
        for phrase in [
            "jarvis",
            "local ai assistant",
            "local-first",
            "voice",
            "vision",
            "semantic memory",
            "pgvector",
            "conversation history",
            "manufacturing prototype",
        ]
    ):
        return "project"

    # Cruise/personal travel facts.
    if any(
        phrase in text
        for phrase in [
            "cruise",
            "holland america",
            "eurodam",
            "ship",
            "kelly",
            "princess",
            "norwegian",
        ]
    ):
        return "cruise"

    # Preferences / technical preferences.
    if any(
        phrase in text
        for phrase in [
            "sql server",
            "databricks",
            "database",
            "reporting",
            "prefer",
            "preference",
        ]
    ):
        return "preference"

    # Work/manufacturing context.
    if any(
        phrase in text
        for phrase in [
            "gm",
            "work",
            "manufacturing",
            "vlive",
            "reporting workload",
            "indexed relational",
        ]
    ):
        return "work"

    # Personal profile facts.
    if any(
        phrase in text
        for phrase in [
            "wife",
            "favorite color",
            "color",
            "taco",
            "drink",
        ]
    ):
        return "personal"

    return "unknown"


def infer_memory_tags(content: str, source_type: str = "") -> List[str]:
    """
    Infer simple tags for semantic memory metadata.

    Tags are intentionally lowercase/simple so they stay easy to inspect.
    """
    text = f"{source_type} {content}".lower()
    tags: List[str] = []

    tag_rules = {
        "jarvis": ["jarvis"],
        "thor": ["thor"],
        "nvidia": ["nvidia"],
        "cuda": ["cuda"],
        "qwen": ["qwen"],
        "llama.cpp": ["llama.cpp"],
        "postgresql": ["postgresql"],
        "postgres": ["postgresql"],
        "pgvector": ["pgvector"],
        "semantic memory": ["semantic-memory"],
        "conversation history": ["conversation-history"],
        "voice": ["voice"],
        "vision": ["vision"],
        "camera": ["camera"],
        "manufacturing": ["manufacturing"],
        "prototype": ["prototype"],
        "sql server": ["sql-server"],
        "databricks": ["databricks"],
        "database": ["database"],
        "reporting": ["reporting"],
        "cruise": ["cruise"],
        "holland america": ["holland-america"],
        "eurodam": ["eurodam"],
        "kelly": ["kelly"],
        "gm": ["gm"],
        "vlive": ["vlive"],
        "test": ["test"],
    }

    for phrase, phrase_tags in tag_rules.items():
        if phrase in text:
            for tag in phrase_tags:
                if tag not in tags:
                    tags.append(tag)

    return tags


def get_source_boost(source_type: str) -> float:
    """
    Return the trust/quality boost for a semantic memory source type.
    """
    return float(SOURCE_TYPE_BOOSTS.get((source_type or "").strip(), 0.0))


def get_category_boost(category: str) -> float:
    """
    Return the ranking boost/penalty for a memory category.
    """
    return float(CATEGORY_BOOSTS.get((category or "unknown").strip(), 0.0))


def normalize_metadata(
    content: str,
    source_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ensure semantic memory metadata has a category and tags list.

    Existing caller-provided metadata wins, but missing fields are inferred.
    """
    metadata_dict: Dict[str, Any] = dict(metadata or {})

    if "category" not in metadata_dict or not metadata_dict.get("category"):
        metadata_dict["category"] = infer_memory_category(content, source_type)

    if "tags" not in metadata_dict or metadata_dict.get("tags") is None:
        metadata_dict["tags"] = infer_memory_tags(content, source_type)

    if not isinstance(metadata_dict.get("tags"), list):
        metadata_dict["tags"] = [str(metadata_dict["tags"])]

    return metadata_dict


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

    metadata_dict = normalize_metadata(
        content=cleaned,
        source_type=source_type,
        metadata=metadata,
    )
    metadata_json = json.dumps(metadata_dict)

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

    Uses pgvector cosine distance because embeddings are normalized.

    Returns:
    - similarity: raw vector similarity
    - source_boost: source trust boost
    - category_boost: category relevance/trust boost
    - weighted_similarity: similarity + source_boost + category_boost

    Results are returned in weighted_similarity order.
    """
    cleaned = (query or "").strip()

    if not cleaned:
        return []

    ensure_semantic_memory_schema()

    query_embedding = get_embedding(cleaned)
    query_vector = vector_to_pgvector(query_embedding)

    # Pull more than final limit so weighting has room to reorder.
    search_limit = max(limit * 3, limit, 10)

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
        query_params = [query_vector, source_type, query_vector, search_limit]
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
        query_params = [query_vector, query_vector, search_limit]

    results: List[Dict[str, Any]] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, query_params)

            for row in cur.fetchall():
                memory_id = row[0]
                row_source_type = row[1]
                source_id = row[2]
                content = row[3]
                metadata = row[4] or {}
                distance = float(row[5])
                created_at = row[6]

                similarity = 1.0 - distance
                source_boost = get_source_boost(row_source_type)

                category = metadata.get("category") or infer_memory_category(
                    content,
                    row_source_type,
                )
                tags = metadata.get("tags") or infer_memory_tags(
                    content,
                    row_source_type,
                )

                if not isinstance(tags, list):
                    tags = [str(tags)]

                category_boost = get_category_boost(category)
                weighted_similarity = similarity + source_boost + category_boost

                results.append(
                    {
                        "id": memory_id,
                        "source_type": row_source_type,
                        "source_id": source_id,
                        "content": content,
                        "metadata": metadata,
                        "category": category,
                        "tags": tags,
                        "distance": distance,
                        "similarity": similarity,
                        "source_boost": source_boost,
                        "category_boost": category_boost,
                        "weighted_similarity": weighted_similarity,
                        "created_at": created_at,
                    }
                )

    results.sort(
        key=lambda item: item.get(
            "weighted_similarity",
            item.get("similarity", 0.0),
        ),
        reverse=True,
    )

    return results[:limit]


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
        similarity = float(item.get("similarity", 0.0))
        weighted_similarity = float(item.get("weighted_similarity", similarity))
        source_boost = float(item.get("source_boost", 0.0))
        category_boost = float(item.get("category_boost", 0.0))

        content = item.get("content", "").strip()
        source_type = item.get("source_type", "unknown")
        category = item.get("category", "unknown")
        tags = item.get("tags", [])
        memory_id = item.get("id", "?")

        if not isinstance(tags, list):
            tags = [str(tags)]

        tags_text = ",".join(tags) if tags else "none"

        lines.append(
            f"- #{memory_id} [{source_type}/{category}] "
            f"similarity={similarity:.3f} "
            f"source_boost={source_boost:.2f} "
            f"category_boost={category_boost:.2f} "
            f"weighted={weighted_similarity:.3f} "
            f"tags={tags_text}: {content}"
        )

    return "\n".join(lines)
