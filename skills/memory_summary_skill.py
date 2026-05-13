# skills/memory_summary_skill.py

from core.memory import get_all_memories
from core.session import get_recent_history, get_last_topic


def get_memory_summary_response() -> str:
    memories = get_all_memories()
    recent_history = get_recent_history(limit=5)
    last_topic = get_last_topic() or "None"

    lines = [
        "Jarvis memory summary, Marty:",
        "",
        f"Long-term memories: {len(memories)}",
        f"Recent conversation rows loaded: {len(recent_history)}",
        f"Last topic: {last_topic}",
        "",
        "Stored memories:",
    ]

    if not memories:
        lines.append("- No long-term memories saved yet.")
    else:
        for key, value in memories.items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)
