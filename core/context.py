# core/context.py

from typing import List, Dict

from core.memory import build_memory_context
from core.session import get_recent_history, get_last_topic


SYSTEM_PROMPT = """
You are Jarvis, Marty's local AI assistant.

Identity:
- You run locally for Marty.
- You are practical, direct, helpful, and a little conversational.
- Marty is building you as a local Jarvis-style assistant.

Rules:
- Answer clearly and briefly unless Marty asks for detail.
- Use long-term memory when it helps answer Marty's question.
- Use recent conversation history for follow-up questions.
- If Marty asks a follow-up like "how is it different", compare against the recent topic.
- Do not claim you remember something unless it appears in memory or recent context.
- If you are unsure, say so.
- Voice and camera features are planned later, not now.

Technical facts:
- Flask is Python.
- Express is Node.js / JavaScript.
""".strip()


def _format_long_term_memory() -> str:
    memory_context = build_memory_context()

    if not memory_context:
        return "No long-term memories saved yet."

    return memory_context


def _format_recent_history(limit: int = 8) -> str:
    history = get_recent_history(limit=limit)

    if not history:
        return "No recent conversation history yet."

    lines = []

    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "").strip()

        if not content:
            continue

        lines.append(f"{role}: {content}")

    if not lines:
        return "No recent conversation history yet."

    return "\n".join(lines)


def build_prompt(user_text: str, history_limit: int = 8) -> str:
    """
    Build a single prompt string for completion-style local LLM APIs,
    such as Ollama /api/generate.
    """

    last_topic = get_last_topic() or "None"
    long_term_memory = _format_long_term_memory()
    recent_history = _format_recent_history(limit=history_limit)

    prompt = f"""
{SYSTEM_PROMPT}

Long-term memory:
{long_term_memory}

Last topic:
{last_topic}

Recent conversation:
{recent_history}

Current question:
{user_text}

Answer:
""".strip()

    return prompt


def build_messages(user_text: str, history_limit: int = 8) -> List[Dict[str, str]]:
    """
    Build OpenAI-compatible chat messages for llama.cpp server or
    other /v1/chat/completions style APIs.
    """

    last_topic = get_last_topic() or "None"
    long_term_memory = _format_long_term_memory()
    recent_history = _format_recent_history(limit=history_limit)

    system_content = f"""
{SYSTEM_PROMPT}

Long-term memory:
{long_term_memory}

Last topic:
{last_topic}

Recent conversation:
{recent_history}
""".strip()

    return [
        {
            "role": "system",
            "content": system_content,
        },
        {
            "role": "user",
            "content": user_text,
        },
    ]


def build_context_summary(history_limit: int = 8) -> str:
    """
    Human-readable context summary for debugging.
    """

    last_topic = get_last_topic() or "None"
    long_term_memory = _format_long_term_memory()
    recent_history = _format_recent_history(limit=history_limit)

    return f"""
Last topic:
{last_topic}

Long-term memory:
{long_term_memory}

Recent conversation:
{recent_history}
""".strip()
