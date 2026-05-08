import json
import requests


LLAMA_CPP_URL = "http://127.0.0.1:8080/v1/chat/completions"


def stream_local_llm(prompt: str, max_tokens: int = 200):
    """
    Streams response chunks from llama.cpp OpenAI-compatible API.
    Yields text as it arrives.
    """

    payload = {
        "model": "qwen2.5-coder-7b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Jarvis, a helpful local assistant. "
                    "Answer clearly and briefly unless asked for detail."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": True,
    }

    try:
        with requests.post(
            LLAMA_CPP_URL,
            json=payload,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                if line.startswith("data: "):
                    line = line[6:]

                if line.strip() == "[DONE]":
                    break

                try:
                    data = json.loads(line)
                    delta = data["choices"][0].get("delta", {})
                    text = delta.get("content", "")

                    if text:
                        yield text

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        yield f"[LLM STREAM ERROR] {str(e)}"
