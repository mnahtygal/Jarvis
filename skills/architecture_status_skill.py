from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_RELATIVE_PATH = Path("runtime/graphify/graphify-out/graph.json")


def _unavailable_status(
    detail: str,
    *,
    status: str,
    tree_available: bool,
    callflow_available: bool,
) -> Dict[str, Any]:
    return {
        "available": False,
        "ready": False,
        "status": status,
        "nodes": 0,
        "edges": 0,
        "generated_at": None,
        "tree_available": tree_available,
        "callflow_available": callflow_available,
        "graph_path": GRAPH_RELATIVE_PATH.as_posix(),
        "detail": detail,
    }


def get_architecture_status() -> Dict[str, Any]:
    """Return read-only status for the generated Graphify architecture graph."""
    graph_path = PROJECT_ROOT / GRAPH_RELATIVE_PATH
    output_dir = graph_path.parent
    tree_available = False
    callflow_available = False

    try:
        tree_available = (output_dir / "JARVIS_TREE.html").is_file()
        callflow_available = (output_dir / "graphify-callflow.html").is_file()

        if not graph_path.is_file():
            return _unavailable_status(
                "Graphify architecture graph has not been generated.",
                status="NOT GENERATED",
                tree_available=tree_available,
                callflow_available=callflow_available,
            )

        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        if not isinstance(graph, dict):
            raise ValueError("graph root must be a JSON object")

        nodes = graph.get("nodes")
        edges = graph.get("links", graph.get("edges"))
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise ValueError("graph must contain node and edge lists")

        generated_at = datetime.fromtimestamp(
            graph_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()
    except Exception as exc:
        return _unavailable_status(
            f"Graphify architecture graph could not be read: {exc}",
            status="ERROR",
            tree_available=tree_available,
            callflow_available=callflow_available,
        )

    return {
        "available": True,
        "ready": True,
        "status": "READY",
        "nodes": len(nodes),
        "edges": len(edges),
        "generated_at": generated_at,
        "tree_available": tree_available,
        "callflow_available": callflow_available,
        "graph_path": GRAPH_RELATIVE_PATH.as_posix(),
        "detail": "Graphify architecture graph available.",
    }
