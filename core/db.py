# core/db.py

import os
from typing import Dict, Any

import psycopg2


def get_db_config() -> Dict[str, Any]:
    """
    Return PostgreSQL connection settings for Jarvis.

    Defaults are local-dev friendly, but each value can be overridden
    with environment variables later.
    """

    return {
        "host": os.getenv("JARVIS_DB_HOST", "localhost"),
        "port": int(os.getenv("JARVIS_DB_PORT", "5432")),
        "database": os.getenv("JARVIS_DB_NAME", "jarvis"),
        "user": os.getenv("JARVIS_DB_USER", "mnahtygal"),
        "password": os.getenv("JARVIS_DB_PASSWORD", "jarvis123"),
    }


def get_connection():
    """
    Create a new PostgreSQL connection.

    Callers should use this with a context manager:

        with get_connection() as conn:
            ...
    """

    return psycopg2.connect(**get_db_config())
