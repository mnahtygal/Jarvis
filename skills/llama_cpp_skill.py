# skills/llama_cpp_skill.py

import os
import re

import requests

from core.context import build_messages
from skills.model_runtime import get_active_model_id

LLAMA_CPP_URL = os.getenv(
    "LLAMA_CPP_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)


def strip_thinking(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def get_llama_cpp_response(prompt: str) -> str:
    payload = {
        "model": get_active_model_id(),
        "messages": build_messages(prompt),
        "temperature": 0.3,
        "max_tokens": 1200,
        "stream": False,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=180,
        )

        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        answer = message.get("content", "")

        if not answer:
            answer = message.get("reasoning_content", "")

        answer = strip_thinking(answer)

        return answer if answer else ""

    except Exception as error:
        print(f"[LLM] llama.cpp error: {error}")
        return ""


def get_llama_cpp_raw_response(
    prompt: str,
    system_prompt: str = "You are Jarvis, a local assistant. Follow the user's instructions exactly.",
    temperature: float = 0.2,
    max_tokens: int = 1800,
) -> str:
    payload = {
        "model": get_active_model_id(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(
            LLAMA_CPP_URL,
            json=payload,
            timeout=240,
        )

        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        answer = message.get("content", "")

        if not answer:
            answer = message.get("reasoning_content", "")

        answer = strip_thinking(answer)

        return answer if answer else ""

    except Exception as error:
        print(f"[LLM] llama.cpp raw error: {error}")
        return ""


def ask_llama_cpp(prompt: str) -> str:
    return get_llama_cpp_response(prompt)


def ask_local_llm(prompt: str) -> str:
    return get_llama_cpp_response(prompt)


def get_llm_response(prompt: str) -> str:
    return get_llama_cpp_response(prompt)
