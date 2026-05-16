#!/usr/bin/env python3

"""
Standalone semantic memory test for Jarvis.

Usage:

    python3 tools/test_semantic_memory.py

This will:
- verify the semantic memory schema
- add a few test memories if table is empty
- run meaning-based searches
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.semantic_memory import (  # noqa: E402
    add_semantic_memory,
    count_semantic_memories,
    ensure_semantic_memory_schema,
    format_semantic_results,
    search_semantic_memories,
)


SEED_MEMORIES = [
    {
        "content": "Marty prefers SQL Server over Databricks for indexed relational reporting workloads.",
        "source_type": "seed",
        "source_id": "database_preference",
        "metadata": {"category": "technology", "topic": "database"},
    },
    {
        "content": "Marty and Kelly enjoy Holland America cruises, especially the Eurodam.",
        "source_type": "seed",
        "source_id": "cruise_preference",
        "metadata": {"category": "travel", "topic": "cruises"},
    },
    {
        "content": "Jarvis now runs on the NVIDIA Jetson AGX Thor with CUDA 13 and Qwen3 30B.",
        "source_type": "seed",
        "source_id": "thor_migration",
        "metadata": {"category": "jarvis", "topic": "hardware"},
    },
    {
        "content": "Marty is building Jarvis as a local AI assistant with memory, voice, vision, and manufacturing prototype potential.",
        "source_type": "seed",
        "source_id": "jarvis_goal",
        "metadata": {"category": "jarvis", "topic": "roadmap"},
    },
]


TEST_QUERIES = [
    "What database does Marty like for reporting?",
    "What cruise ship does Marty like?",
    "What hardware is Jarvis running on now?",
    "What is the long term goal for Jarvis?",
]


def seed_if_empty() -> None:
    count = count_semantic_memories()

    if count > 0:
        print(f"[INFO] semantic_memories already has {count} row(s); skipping seed insert.")
        return

    print("[INFO] semantic_memories is empty; adding seed memories...")

    for item in SEED_MEMORIES:
        memory_id = add_semantic_memory(
            content=item["content"],
            source_type=item["source_type"],
            source_id=item["source_id"],
            metadata=item["metadata"],
        )
        print(f"[ADD] #{memory_id}: {item['content']}")


def run_queries() -> None:
    print("")
    print("===================================")
    print(" Semantic Search Tests")
    print("===================================")

    for query in TEST_QUERIES:
        print("")
        print(f"[QUERY] {query}")
        results = search_semantic_memories(query, limit=3)
        print(format_semantic_results(results))


def main() -> int:
    print("")
    print("===================================")
    print(" Jarvis Semantic Memory Test")
    print("===================================")

    ensure_semantic_memory_schema()
    print("[PASS] semantic memory schema verified")

    seed_if_empty()

    count = count_semantic_memories()
    print(f"[PASS] semantic memory count: {count}")

    run_queries()

    print("")
    print("===================================")
    print(" Semantic memory test complete")
    print("===================================")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
