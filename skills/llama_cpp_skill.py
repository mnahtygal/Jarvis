# skills/llama_cpp_skill.py

import os
import re
import requests


LLAMA_CPP_URL = os.getenv(
    "LLAMA_CPP_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)

LLAMA_CPP_MODEL = os.getenv(
    "LLAMA_CPP_MODEL",
    "Qwen3-30B-A3B-Q4_K_M.gguf",
)


def strip_thinking(text: str) -> str:
    """
    Removes Qwen3-style thinking blocks from visible Jarvis responses.
    """
    if not text:
        return ""

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def get_llama_cpp_response(prompt: str) -> str:
    """
    Sends a prompt to llama.cpp OpenAI-compatible chat endpoint.
    """

    payload = {
        "model": LLAMA_CPP_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Jarvis, Marty's helpful local AI assistant. "
                    "Answer clearly and directly. Do not show internal reasoning."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.3,
        "max_tokens": 1200,
        "stream": False,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=120,
        )

        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        answer = message.get("content", "")

        # Some reasoning models may return text in reasoning_content instead.
        # We do NOT expose that as the final answer unless content is empty.
        if not answer:
            answer = message.get("reasoning_content", "")

        answer = strip_thinking(answer)

        if not answer:
            return ""

        return answer

    except Exception as e:
        print(f"[LLM] llama.cpp error: {e}")
        return ""


def ask_llama_cpp(prompt: str) -> str:
    """
    Backward-compatible alias.
    """
    return get_llama_cpp_response(prompt)


def ask_local_llm(prompt: str) -> str:
    """
    Backward-compatible alias.
    """
    return get_llama_cpp_response(prompt)


def get_llm_response(prompt: str) -> str:
    """
    Backward-compatible alias.
    """
    return get_llama_cpp_response(prompt)
