# core/session.py

import uuid
from typing import List, Dict

import psycopg2
from psycopg2.extras import RealDictCursor


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "jarvis",
    "user": "mnahtygal",
    "password": "jarvis123",
}


SESSION_ID = "default"

conversation = {
    "last_topic": None,
    "history": [],
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


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
    if topic:
        conversation["last_topic"] = topic


def get_last_topic():
    return conversation.get("last_topic")


def get_recent_history(limit: int = 8) -> List[Dict[str, str]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role, message, created_at
                FROM conversation_history
                WHERE session_id = %s
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
    last_topic = conversation.get("last_topic") or "None"
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


def new_session() -> str:
    global SESSION_ID

    SESSION_ID = str(uuid.uuid4())
    conversation["last_topic"] = None
    conversation["history"] = []

    return SESSION_ID
