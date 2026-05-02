# core/router.py

from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response
from skills.llm_skill import get_llm_response


def route(command: str) -> str:
    text = command.lower().strip()

    if not text:
        return "I didn't hear anything, Marty."

    # Time / date
    if "time" in text or "date" in text:
        return get_time_response()

    # System status
    if (
        "system" in text
        or "cpu" in text
        or "memory" in text
        or "disk" in text
        or "status" in text
    ):
        return get_system_response()

    # Simple chat
    if (
        text in ["hello", "hi", "hey", "hey jarvis", "hello jarvis"]
        or "how are you" in text
    ):
        return get_chat_response(command)

    # Everything else goes to local LLM
    print("[BRAIN] Falling back to LLM...")
    return get_llm_response(command)
