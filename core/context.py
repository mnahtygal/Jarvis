# core/context.py

from typing import Dict, List

from core.memory import build_memory_context
from core.session import get_last_topic, get_recent_history

try:
    from core.semantic_memory import format_semantic_results, search_semantic_memories
except Exception:
    format_semantic_results = None
    search_semantic_memories = None


SYSTEM_PROMPT = """
You are Jarvis, Marty's local AI assistant.

Identity:
- You run locally for Marty.
- You are practical, direct, helpful, and a little conversational.
- Marty is building you as a local Jarvis-style assistant.

Rules:
- Answer clearly and briefly unless Marty asks for detail.
- Use long-term memory when it helps answer Marty's question.
- Use semantic memory when it helps answer Marty's question.
- Use recent conversation history for follow-up questions.
- If Marty asks a follow-up like "how is it different", compare against the recent topic.
- Do not claim you remember something unless it appears in memory, semantic memory, or recent context.
- If you are unsure, say so.
- Voice and camera features are planned later, not now.
- Do not show internal reasoning or thinking text.

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


def _format_semantic_memory(user_text: str, limit: int = 4, min_similarity: float = 0.35) -> str:
    """
    Retrieve meaning-based memories relevant to the current user text.

    This is intentionally defensive:
    - If semantic memory import fails, Jarvis keeps working.
    - If embedding/model/search fails, Jarvis keeps working.
    - Low-similarity results are filtered out to reduce noise.
    """

    if not search_semantic_memories or not format_semantic_results:
        return "Semantic memory unavailable."

    cleaned = (user_text or "").strip()

    if not cleaned:
        return "No semantic memory query provided."

    try:
        results = search_semantic_memories(cleaned, limit=limit)
    except Exception as error:
        return f"Semantic memory search unavailable: {error}"

    filtered = [
        item
        for item in results
        if float(item.get("similarity", 0.0)) >= min_similarity
    ]

    if not filtered:
        return "No relevant semantic memories found."

    return format_semantic_results(filtered)


def build_prompt(user_text: str, history_limit: int = 8) -> str:
    """
    Build a single prompt string for completion-style local LLM APIs,
    such as Ollama /api/generate.
    """

    last_topic = get_last_topic() or "None"
    long_term_memory = _format_long_term_memory()
    semantic_memory = _format_semantic_memory(user_text)
    recent_history = _format_recent_history(limit=history_limit)

    prompt = f"""
{SYSTEM_PROMPT}

Long-term memory:
{long_term_memory}

Semantic memory:
{semantic_memory}

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
    semantic_memory = _format_semantic_memory(user_text)
    recent_history = _format_recent_history(limit=history_limit)

    system_content = f"""
{SYSTEM_PROMPT}

Long-term memory:
{long_term_memory}

Semantic memory:
{semantic_memory}

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


def build_context_summary(history_limit: int = 8, user_text: str = "Jarvis status") -> str:
    """
    Human-readable context summary for debugging.
    """

    last_topic = get_last_topic() or "None"
    long_term_memory = _format_long_term_memory()
    semantic_memory = _format_semantic_memory(user_text)
    recent_history = _format_recent_history(limit=history_limit)

    return f"""
Last topic:
{last_topic}

Long-term memory:
{long_term_memory}

Semantic memory:
{semantic_memory}

Recent conversation:
{recent_history}
""".strip()
