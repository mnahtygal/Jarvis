# core/session.py

import uuid
from typing import List, Dict

from psycopg2.extras import RealDictCursor

from core.db import get_connection


SESSION_ID = "default"

conversation = {
    "last_topic": None,
    "history": [],
}


def _save_message(role: str, message: str):
    message = message.strip()

    if not message:
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_history
                    (session_id, role, message)
                VALUES
                    (%s, %s, %s);
                """,
                (SESSION_ID, role, message),
            )


def _remember_in_ram(role: str, message: str):
    message = message.strip()

    if not message:
        return

    conversation["history"].append(
        {
            "role": role,
            "content": message,
        }
    )

    conversation["history"] = conversation["history"][-8:]


def remember_user_message(message: str):
    _remember_in_ram("user", message)
    _save_message("user", message)


def remember_assistant_message(message: str):
    _remember_in_ram("assistant", message)
    _save_message("assistant", message)


def set_last_topic(topic: str):
    topic = topic.strip() if topic else ""

    if not topic:
        return

    conversation["last_topic"] = topic

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session_state
                    (session_id, last_topic, updated_at)
                VALUES
                    (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    last_topic = EXCLUDED.last_topic,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (SESSION_ID, topic),
            )


def get_last_topic():
    if conversation.get("last_topic"):
        return conversation["last_topic"]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT last_topic
                FROM session_state
                WHERE session_id = %s;
                """,
                (SESSION_ID,),
            )
            row = cur.fetchone()

    if row and row.get("last_topic"):
        conversation["last_topic"] = row["last_topic"]
        return row["last_topic"]

    return None


def get_recent_history(limit: int = 8) -> List[Dict[str, str]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role, message, created_at
                FROM conversation_history
                WHERE session_id = %s
                  AND message IS NOT NULL
                  AND btrim(message) <> ''
                ORDER BY created_at DESC, id DESC
                LIMIT %s;
                """,
                (SESSION_ID, limit),
            )
            rows = cur.fetchall()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["message"],
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def get_context() -> str:
    last_topic = get_last_topic() or "None"
    recent_history = get_recent_history(limit=8)

    history_text = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in recent_history
    )

    return f"""
Last topic: {last_topic}

Recent conversation:
{history_text}
""".strip()


def clear_session_history():
    conversation["history"] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM conversation_history
                WHERE session_id = %s;
                """,
                (SESSION_ID,),
            )


def clear_last_topic():
    conversation["last_topic"] = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE session_state
                SET last_topic = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s;
                """,
                (SESSION_ID,),
            )


def new_session() -> str:
    global SESSION_ID

    SESSION_ID = str(uuid.uuid4())
    conversation["last_topic"] = None
    conversation["history"] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session_state
                    (session_id, last_topic, updated_at)
                VALUES
                    (%s, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (session_id)
                DO UPDATE SET
                    last_topic = NULL,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (SESSION_ID,),
            )

    return SESSION_ID
