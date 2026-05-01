# core/router.py

from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response


def route(command: str):
    text = command.lower().strip()

    if not text:
        return "I didn't hear anything."

    if "time" in text:
        return get_time_response()

    if any(word in text for word in ["cpu", "memory", "ram", "disk", "system", "status"]):
        return get_system_response()

    if text in ["hello", "hi", "hey", "hey jarvis", "hi jarvis", "hello jarvis"]:
        return get_chat_response(command)

    return None
