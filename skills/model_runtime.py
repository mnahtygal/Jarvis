# skills/model_runtime.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


LLAMA_MODELS_URL = os.getenv(
    "LLAMA_MODELS_URL",
    "http://127.0.0.1:8080/v1/models",
)

DEFAULT_MODEL_ID = os.getenv(
    "JARVIS_DEFAULT_MODEL",
    "Qwen3-30B-A3B-Q4_K_M.gguf",
)

MODEL_FRIENDLY_NAMES = {
    "Qwen3-30B-A3B-Q4_K_M.gguf": "Qwen3 30B",
    "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf": "DeepSeek R1 Distill Qwen 7B",
}


@dataclass(frozen=True)
class ModelRuntimeStatus:
    online: bool
    active_model_id: Optional[str]
    model_ids: List[str]
    detail: str


def get_friendly_model_name(model_id: Optional[str]) -> str:
    if not model_id:
        return "unknown model"

    return MODEL_FRIENDLY_NAMES.get(model_id, model_id)


def get_model_runtime_status(timeout: float = 5.0) -> ModelRuntimeStatus:
    try:
        response = requests.get(LLAMA_MODELS_URL, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as error:
        return ModelRuntimeStatus(
            online=False,
            active_model_id=None,
            model_ids=[],
            detail=f"offline ({error})",
        )

    models = data.get("data", [])
    model_ids = [
        str(model.get("id", "")).strip()
        for model in models
        if str(model.get("id", "")).strip()
    ]

    if not model_ids:
        return ModelRuntimeStatus(
            online=False,
            active_model_id=None,
            model_ids=[],
            detail="online but no model listed",
        )

    active_model_id = model_ids[0]

    if len(model_ids) == 1:
        detail = f"online, model={active_model_id}"
    else:
        detail = f"online, model(s)={', '.join(model_ids)}"

    return ModelRuntimeStatus(
        online=True,
        active_model_id=active_model_id,
        model_ids=model_ids,
        detail=detail,
    )


def get_active_model_id(fallback_to_default: bool = True) -> str:
    status = get_model_runtime_status()

    if status.active_model_id:
        return status.active_model_id

    return DEFAULT_MODEL_ID if fallback_to_default else ""


def get_active_model_friendly_name(fallback_to_default: bool = True) -> str:
    return get_friendly_model_name(
        get_active_model_id(fallback_to_default=fallback_to_default)
    )
