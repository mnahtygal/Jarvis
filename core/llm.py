# core/llm.py

import requests
from core.session import get_context
from core.memory import get_all_facts

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:3b"


def _format_long_term_memory() -> str:
    facts = get_all_facts()

    if not facts:
        return "No long-term memories saved yet."

    return "\n".join([f"- {key} is {value}" for key, value in facts.items()])


def ask_llm(prompt: str) -> str:
    context = get_context()
    long_term_memory = _format_long_term_memory()

    full_prompt = f"""
You are Jarvis, Marty's local AI assistant.

You are running locally on Marty's NVIDIA Jetson.

Use the long-term memory and conversation context to answer follow-up questions.
If Marty says "it", "that", "this", "they", or asks a comparison question,
infer the meaning from the recent conversation and last topic.

If the answer is in long-term memory, use it naturally.
Keep answers helpful, clear, and not too long.

Long-term memory:
{long_term_memory}

Conversation context:
{context}

Marty's question:
{prompt}

Jarvis answer:
""".strip()

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": full_prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()
        data = response.json()

        return data.get("response", "").strip()

    except requests.exceptions.RequestException as error:
        return f"Sorry Marty, I had trouble reaching Ollama: {error}"

