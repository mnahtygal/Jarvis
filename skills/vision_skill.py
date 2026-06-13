# skills/vision_skill.py

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VISION_URL = os.getenv(
    "JARVIS_VISION_URL",
    "http://127.0.0.1:8081/v1/chat/completions",
)
VISION_MODEL = os.getenv(
    "JARVIS_VISION_MODEL",
    "ggml-org/gemma-3-4b-it-qat-GGUF",
)
DEFAULT_PROMPT = (
    "Briefly describe what you see in this image. "
    "Do not identify people. Mention uncertainty when needed."
)


def analyze_image(
    image_path: Path,
    prompt: str = DEFAULT_PROMPT,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    if not image_path.exists():
        return {
            "ok": False,
            "error": "Snapshot file does not exist.",
        }

    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                        },
                    },
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 220,
    }

    request = Request(
        VISION_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            result = json.load(response)
    except HTTPError as error:
        return {
            "ok": False,
            "error": f"Vision server returned HTTP {error.code}.",
        }
    except URLError:
        return {
            "ok": False,
            "error": "Vision server is offline on port 8081.",
        }
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
        }

    try:
        description = result["choices"][0]["message"]["content"].strip()
    except Exception:
        return {
            "ok": False,
            "error": "Vision server returned an unexpected response.",
        }

    return {
        "ok": True,
        "model": result.get("model", VISION_MODEL),
        "description": description,
        "image_name": image_path.name,
        "usage": result.get("usage", {}),
        "timings": result.get("timings", {}),
    }
