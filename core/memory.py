# core/memory.py

from psycopg2.extras import RealDictCursor

from core.db import get_connection


def remember(memory_key: str, memory_value: str) -> str:
    memory_key = memory_key.strip().lower()
    memory_value = memory_value.strip()

    if not memory_key or not memory_value:
        return "I need both a memory name and value to remember that, Marty."

    old_value = recall(memory_key)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memories (memory_key, memory_value)
                VALUES (%s, %s)
                ON CONFLICT (memory_key)
                DO UPDATE SET
                    memory_value = EXCLUDED.memory_value,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING memory_value;
                """,
                (memory_key, memory_value),
            )

            cur.execute(
                """
                INSERT INTO memory_history
                    (action_type, memory_key, old_value, new_value, event_timestamp)
                VALUES
                    (%s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                ("remember", memory_key, old_value or None, memory_value),
            )

    return f"Got it, Marty. I'll remember that {memory_key} is {memory_value}."


def recall(memory_key: str) -> str:
    memory_key = memory_key.strip().lower()

    if not memory_key:
        return ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT memory_value
                FROM memories
                WHERE memory_key = %s;
                """,
                (memory_key,),
            )
            row = cur.fetchone()

    if row:
        return row["memory_value"]

    return ""


def update_memory(memory_key: str, memory_value: str) -> str:
    memory_key = memory_key.strip().lower()
    memory_value = memory_value.strip()

    if not memory_key or not memory_value:
        return "I need both a memory name and value to update that, Marty."

    old_value = recall(memory_key)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memories (memory_key, memory_value)
                VALUES (%s, %s)
                ON CONFLICT (memory_key)
                DO UPDATE SET
                    memory_value = EXCLUDED.memory_value,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (memory_key, memory_value),
            )

            cur.execute(
                """
                INSERT INTO memory_history
                    (action_type, memory_key, old_value, new_value, event_timestamp)
                VALUES
                    (%s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                ("update", memory_key, old_value or None, memory_value),
            )

    return f"Updated, Marty. {memory_key} is now {memory_value}."


def forget(memory_key: str) -> str:
    memory_key = memory_key.strip().lower()

    if not memory_key:
        return "Tell me what memory to forget, Marty."

    old_value = recall(memory_key)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM memories
                WHERE memory_key = %s;
                """,
                (memory_key,),
            )

            cur.execute(
                """
                INSERT INTO memory_history
                    (action_type, memory_key, old_value, new_value, event_timestamp)
                VALUES
                    (%s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                ("forget", memory_key, old_value or None, None),
            )

    if old_value:
        return f"Forgot that {memory_key}, Marty."

    return f"I didn't have anything stored for {memory_key}, Marty."


def get_all_memories() -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT memory_key, memory_value
                FROM memories
                WHERE memory_key IS NOT NULL
                  AND memory_value IS NOT NULL
                  AND btrim(memory_key) <> ''
                  AND btrim(memory_value) <> ''
                ORDER BY memory_key;
                """
            )
            rows = cur.fetchall()

    return {row["memory_key"]: row["memory_value"] for row in rows}


def build_memory_context() -> str:
    memories = get_all_memories()

    if not memories:
        return ""

    lines = ["Known facts about Marty:"]
    for key, value in memories.items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def get_memory_history(limit: int = 20) -> list:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT action_type, memory_key, old_value, new_value, event_timestamp
                FROM memory_history
                ORDER BY event_timestamp DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return rows
