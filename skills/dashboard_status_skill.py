# skills/dashboard_status_skill.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import urlopen

from core.memory import get_all_memories
from core.session import get_last_topic, get_recent_history
from skills.architecture_status_skill import get_architecture_status
from skills.brain_status_skill import (
    _check_embedding_model,
    _check_llm_endpoint,
    _check_postgres,
    _count_semantic_memories,
)
from skills.calibration_skill import get_calibration_status
from skills.camera_diagnostics_skill import get_camera_diagnostics_status
from skills.device_status_skill import get_device_dashboard_status
from skills.measurement_skill import get_measurement_status
from skills.model_runtime import get_active_model_friendly_name, get_model_runtime_status
from skills.vision_skill import VISION_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARTYBENCH_RESULTS_DIR = (
    PROJECT_ROOT / "benchmarks" / "results" / "martybench_v2_shift_handoff"
)
VISION_HEALTH_URL = "http://127.0.0.1:8081/health"
VISION_MODELS_URL = "http://127.0.0.1:8081/v1/models"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")


def _fetch_json(url: str, timeout: int = 3) -> Dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (URLError, TimeoutError, Exception):
        return {}


def _latest_martybench_run_dir() -> Path | None:
    if not MARTYBENCH_RESULTS_DIR.exists():
        return None

    candidates = [path for path in MARTYBENCH_RESULTS_DIR.iterdir() if path.is_dir()]
    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _parse_score_summary(score_text: str) -> Dict[str, Any]:
    score: Dict[str, Any] = {
        "total": None,
        "max_total": 35,
        "verdict": "unknown",
        "raw_summary_present": bool(score_text.strip()),
    }

    for raw_line in score_text.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        if lower.startswith("total:"):
            value = line.split(":", 1)[1].strip()
            if "/" in value:
                left, right = value.split("/", 1)
                try:
                    score["total"] = int(left.strip())
                except Exception:
                    pass
                try:
                    score["max_total"] = int(right.strip())
                except Exception:
                    pass

        if lower.startswith("pass / partial / fail:"):
            verdict = line.split(":", 1)[1].strip()
            if verdict:
                score["verdict"] = verdict

    return score


def get_model_dashboard_status() -> Dict[str, Any]:
    runtime_status = get_model_runtime_status()

    return {
        "online": runtime_status.online,
        "active_model_id": runtime_status.active_model_id,
        "active_model_name": get_active_model_friendly_name(),
        "model_ids": runtime_status.model_ids,
        "detail": runtime_status.detail,
        "runtime": "llama.cpp",
        "host": "Thor",
    }


def get_vision_dashboard_status() -> Dict[str, Any]:
    health = _fetch_json(VISION_HEALTH_URL)
    models = _fetch_json(VISION_MODELS_URL)
    model_ids = [item.get("id") for item in models.get("data", []) if item.get("id")]
    active_model = model_ids[0] if model_ids else VISION_MODEL
    online = health.get("status") == "ok"

    return {
        "online": online,
        "overall": "READY" if online else "OFFLINE",
        "runtime": "llama.cpp",
        "host": "Thor",
        "port": 8081,
        "active_model_id": active_model,
        "active_model_name": "Gemma 3 4B Vision",
        "model_ids": model_ids,
        "detail": "Vision server online" if online else "Vision server offline on port 8081",
        "capabilities": [
            capability
            for item in models.get("data", [])
            for capability in item.get("capabilities", [])
        ],
    }


def get_memory_dashboard_status() -> Dict[str, Any]:
    postgres_ok, postgres_detail = _check_postgres()
    semantic_ok, semantic_detail = _count_semantic_memories()
    embedding_ok, embedding_detail = _check_embedding_model()
    memories = get_all_memories()
    recent_history = get_recent_history(limit=10)

    return {
        "postgres": {
            "online": postgres_ok,
            "detail": postgres_detail,
        },
        "exact_memory": {
            "online": True,
            "fact_count": len(memories),
            "keys": list(memories.keys()),
        },
        "semantic_memory": {
            "online": semantic_ok,
            "detail": semantic_detail,
        },
        "local_embeddings": {
            "online": embedding_ok,
            "detail": embedding_detail,
        },
        "recent_history": {
            "rows_checked": len(recent_history),
            "items": recent_history,
        },
        "last_topic": get_last_topic() or "None",
    }


def get_brain_dashboard_status() -> Dict[str, Any]:
    postgres_ok, postgres_detail = _check_postgres()
    semantic_ok, semantic_detail = _count_semantic_memories()
    llm_ok, llm_detail = _check_llm_endpoint()
    embedding_ok, embedding_detail = _check_embedding_model()
    memories = get_all_memories()
    recent_history = get_recent_history(limit=10)
    active_model = get_active_model_friendly_name()

    overall_ready = all(
        [
            postgres_ok,
            semantic_ok,
            llm_ok,
            embedding_ok,
            len(memories) >= 0,
        ]
    )

    return {
        "overall": "READY" if overall_ready else "NEEDS ATTENTION",
        "ready": overall_ready,
        "runtime": {
            "host": "Thor",
            "model": active_model,
            "engine": "llama.cpp",
        },
        "postgres": postgres_detail,
        "exact_memory": f"online, {len(memories)} facts",
        "semantic_memory": semantic_detail,
        "last_topic": get_last_topic() or "None",
        "recent_history_rows_checked": len(recent_history),
        "llm_endpoint": llm_detail,
        "local_embeddings": embedding_detail,
    }


def get_martybench_dashboard_status() -> Dict[str, Any]:
    run_dir = _latest_martybench_run_dir()

    if run_dir is None:
        return {
            "available": False,
            "detail": "No MartyBench result folders found.",
            "results_dir": str(MARTYBENCH_RESULTS_DIR.relative_to(PROJECT_ROOT)),
        }

    metadata = _read_json(run_dir / "metadata.json")
    score_text = _read_text(run_dir / "score_summary.md")
    score = _parse_score_summary(score_text)

    return {
        "available": True,
        "run_folder": str(run_dir.relative_to(PROJECT_ROOT)),
        "run_id": metadata.get("run_id", run_dir.name),
        "variant": metadata.get("variant", "unknown"),
        "include_benchmark_memory": metadata.get("include_benchmark_memory", False),
        "elapsed_seconds": metadata.get("elapsed_seconds", "unknown"),
        "started_at": metadata.get("started_at", "unknown"),
        "model_path": metadata.get("model_path", "unknown"),
        "score": score,
        "files": {
            "metadata": str((run_dir / "metadata.json").relative_to(PROJECT_ROOT)),
            "jarvis_output": str((run_dir / "jarvis_output.md").relative_to(PROJECT_ROOT)),
            "score_summary": str((run_dir / "score_summary.md").relative_to(PROJECT_ROOT)),
        },
    }


def get_dashboard_status() -> Dict[str, Any]:
    return {
        "brain": get_brain_dashboard_status(),
        "model": get_model_dashboard_status(),
        "vision": get_vision_dashboard_status(),
        "memory": get_memory_dashboard_status(),
        "martybench": get_martybench_dashboard_status(),
        "devices": get_device_dashboard_status(),
        "camera_diagnostics": get_camera_diagnostics_status(),
        "calibration": get_calibration_status(),
        "measurement": get_measurement_status(),
        "architecture": get_architecture_status(),
    }
