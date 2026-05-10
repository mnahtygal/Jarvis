# skills/llama_cpp_skill.py

import requests

from core.context import build_messages


LLAMA_CPP_URL = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "qwen2.5-coder-7b"


def ask_llama_cpp(user_text: str, max_tokens: int = 300) -> str:
    """
    Ask the local llama.cpp OpenAI-compatible server.

    This is Jarvis's preferred LLM backend because it uses the
    CUDA-enabled llama.cpp server on the Jetson.
    """

    messages = build_messages(user_text)

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": False,
    }

    response = requests.post(
        LLAMA_CPP_URL,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return ""

    return answer
