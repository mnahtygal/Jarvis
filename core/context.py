# core/context.py

from __future__ import annotations

import logging
from typing import Dict, List

from core.brain_request_context import get_active_request_context
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
- You run locally for Marty Nahtygal.
- When the user says "Marty", assume they mean Marty Nahtygal unless they explicitly mention Marty McFly, Back to the Future, or another Marty.
- You are practical, direct, helpful, and a little conversational.
- Marty is building you as a local Jarvis-style assistant.

Runtime facts:
- You are Jarvis running locally on Marty's NVIDIA Thor system.
- Primary model runtime is Qwen3 30B through llama.cpp.
- PostgreSQL exact memory is enabled.
- PostgreSQL conversation history is enabled.
- Semantic memory via pgvector is enabled.
- You are a local-first assistant and should know your runtime environment.
- Voice and camera features are planned later, not active yet.

Local-only rule:
- You are a local assistant.
- Do not claim to have checked the internet, live news, external APIs, cloud services, email, calendar, files, or private systems unless a tool/source is explicitly provided and approved.
- If a question requires current public information and it is not in saved memory or recent context, say you do not have live/current data.
- Do not invent current events, layoff numbers, prices, schedules, or recent facts.

Memory/source rules:
- Use exact long-term memory when it directly answers the question.
- Use semantic memory when it helps answer the question.
- Use recent conversation history for follow-up questions.
- If an answer comes from exact memory, say "Based on your saved memory..." when useful.
- If an answer comes from semantic memory, say "Based on saved semantic memory..." or "Based on what you told me..." when useful.
- If an answer comes from recent conversation, say "Based on our recent conversation..." when useful.
- If saved memory conflicts with model knowledge, trust saved memory but state that it came from Marty's saved context.
- Do not claim you remember something unless it appears in exact memory, semantic memory, or recent context.
- If you are unsure, say so.

Conversation rules:
- Answer clearly and briefly unless Marty asks for detail.
- If Marty asks a follow-up like "how is it different", compare against the recent topic.
- Do not show internal reasoning or thinking text.

Technical facts:
- Flask is Python.
- Express is Node.js / JavaScript.
""".strip()


SEMANTIC_MEMORY_UNAVAILABLE = "Semantic memory unavailable."
NO_EXACT_MEMORY = "No exact long-term memories saved yet."
NO_RECENT_HISTORY = "No recent conversation history yet."
NO_RELEVANT_SEMANTIC_MEMORY = "No relevant semantic memories found."


logger = logging.getLogger(__name__)


def _safe_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _format_long_term_memory() -> str:
    try:
        memory_context = build_memory_context()
    except Exception:
        logger.exception("Exact memory context unavailable")
        return "Exact long-term memory unavailable."

    if not memory_context:
        return NO_EXACT_MEMORY

    return memory_context


def _format_recent_history(limit: int = 8) -> str:
    try:
        history = get_recent_history(limit=limit)
    except Exception:
        logger.exception("Recent conversation context unavailable")
        return "Recent conversation history unavailable."

    if not history:
        return NO_RECENT_HISTORY

    lines = []

    for item in history:
        role = _safe_text(item.get("role"), "unknown")
        content = _safe_text(item.get("content"))

        if not content:
            continue

        lines.append(f"{role}: {content}")

    if not lines:
        return NO_RECENT_HISTORY

    return "\n".join(lines)


def _format_semantic_memory(
    user_text: str,
    limit: int = 4,
    min_similarity: float = 0.50,
) -> str:
    """
    Retrieve meaning-based memories relevant to the current user text.

    Defensive behavior:
    - If semantic memory import fails, Jarvis keeps working.
    - If embedding/model/search fails, Jarvis keeps working.
    - Low-similarity results are filtered out to reduce noise.
    """

    if not search_semantic_memories or not format_semantic_results:
        return SEMANTIC_MEMORY_UNAVAILABLE

    cleaned = (user_text or "").strip()

    if not cleaned:
        return "No semantic memory query provided."

    try:
        results = search_semantic_memories(cleaned, limit=limit)
    except Exception:
        logger.exception("Semantic memory context unavailable")
        return "Semantic memory search unavailable."

    try:
        filtered = [
            item
            for item in results
            if float(
                item.get(
                    "weighted_similarity",
                    item.get("similarity", 0.0),
                )
            ) >= min_similarity
        ]

        if not filtered:
            return NO_RELEVANT_SEMANTIC_MEMORY

        return format_semantic_results(filtered)
    except Exception:
        logger.exception("Semantic memory results unavailable")
        return "Semantic memory search unavailable."


def _get_last_topic() -> str:
    try:
        return get_last_topic() or "None"
    except Exception:
        logger.exception("Last-topic context unavailable")
        return "Last topic unavailable."


def build_context_sections(
    user_text: str,
    history_limit: int = 8,
    respect_policy: bool = True,
) -> Dict[str, str]:
    """
    Build the reusable context sections used by prompt, chat messages,
    and debugging summaries.
    """

    request_context = get_active_request_context() if respect_policy else None
    policy = request_context.context_policy if request_context else None
    sections: Dict[str, str] = {}

    if policy is None or policy.use_last_topic:
        sections["last_topic"] = _get_last_topic()
    if policy is None or policy.use_exact_memory:
        sections["exact_memory"] = _format_long_term_memory()
    if policy is None or policy.use_semantic_memory:
        sections["semantic_memory"] = _format_semantic_memory(user_text)
    if policy is None or policy.use_recent_history:
        sections["recent_history"] = _format_recent_history(limit=history_limit)

    return sections


def _build_system_content(user_text: str, history_limit: int = 8) -> str:
    sections = build_context_sections(user_text=user_text, history_limit=history_limit)

    if get_active_request_context() is None:
        return f"""
{SYSTEM_PROMPT}

IMPORTANT:
Use the memory/context sections below before relying on general model knowledge.
If semantic memory exists, treat it as user-provided saved context.
If a section says it is unavailable or no relevant memory was found, do not invent details for that section.

Exact long-term memory:
{sections["exact_memory"]}

Semantic memory:
{sections["semantic_memory"]}

Last topic:
{sections["last_topic"]}

Recent conversation:
{sections["recent_history"]}
""".strip()

    if not sections:
        return SYSTEM_PROMPT

    labels = {
        "exact_memory": "Exact long-term memory",
        "semantic_memory": "Semantic memory",
        "last_topic": "Last topic",
        "recent_history": "Recent conversation",
    }
    context_sections = "\n\n".join(
        f"{labels[key]}:\n{value}" for key, value in sections.items()
    )

    return f"""
{SYSTEM_PROMPT}

IMPORTANT:
Use the memory/context sections below before relying on general model knowledge.
If semantic memory exists, treat it as user-provided saved context.
If a section says it is unavailable or no relevant memory was found, do not invent details for that section.

{context_sections}
""".strip()


def build_prompt(user_text: str, history_limit: int = 8) -> str:
    """
    Build a single prompt string for completion-style local LLM APIs,
    such as Ollama /api/generate.
    """

    system_content = _build_system_content(
        user_text=user_text,
        history_limit=history_limit,
    )

    return f"""
{system_content}

Current user message:
{user_text}

Jarvis response:
""".strip()


def build_messages(user_text: str, history_limit: int = 8) -> List[Dict[str, str]]:
    """
    Build OpenAI-compatible chat messages for llama.cpp server or
    other /v1/chat/completions style APIs.
    """

    system_content = _build_system_content(
        user_text=user_text,
        history_limit=history_limit,
    )

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

    sections = build_context_sections(
        user_text=user_text,
        history_limit=history_limit,
        respect_policy=False,
    )

    return f"""
Last topic:
{sections["last_topic"]}

Exact long-term memory:
{sections["exact_memory"]}

Semantic memory:
{sections["semantic_memory"]}

Recent conversation:
{sections["recent_history"]}
""".strip()
