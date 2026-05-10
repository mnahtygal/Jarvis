#!/usr/bin/env python3

# tools/create_session_state_table.py

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db import get_connection


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    last_topic TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                INSERT INTO session_state (session_id, last_topic)
                VALUES (%s, %s)
                ON CONFLICT (session_id)
                DO NOTHING;
                """,
                ("default", None),
            )

    print("session_state table is ready.")


if __name__ == "__main__":
    main()
