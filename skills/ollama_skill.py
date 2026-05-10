# skills/ollama_skill.py

import requests

from core.context import build_prompt


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"


def ask_ollama(user_text: str, max_tokens: int = 300) -> str:
    """
    Ask the local Ollama server.

    This is Jarvis's fallback LLM backend if llama.cpp is not running.
    """

    prompt = build_prompt(user_text)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens,
            },
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()
    answer = data.get("response", "").strip()

    return answer
