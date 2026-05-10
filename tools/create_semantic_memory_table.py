#!/usr/bin/env python3

# tools/create_semantic_memory_table.py

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.db import get_connection


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            print("Checking pgvector availability...")

            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_available_extensions
                    WHERE name = 'vector'
                );
                """
            )

            vector_available = cur.fetchone()[0]

            if not vector_available:
                print("[WARN] pgvector extension is not available in this PostgreSQL install.")
                print("Semantic memory table was not created.")
                print("")
                print("Next install step may be needed:")
                print("  sudo apt install postgresql-*-pgvector")
                return

            print("[PASS] pgvector extension is available.")

            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("[PASS] vector extension enabled.")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id SERIAL PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    embedding vector(384),
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

            print("[PASS] semantic_memories table is ready.")

    print("")
    print("Semantic memory database prep complete.")


if __name__ == "__main__":
    main()
