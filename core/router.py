# core/router.py

from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response
from skills.llm_skill import get_llm_response
from skills.health_skill import get_health_response

from core.memory import (
    remember,
    recall,
    update_memory,
    forget,
    get_all_memories,
)


def normalize_key(key: str) -> str:
    key = key.lower().strip()

    if "preferred database" in key or "preference" in key or "prefer" in key:
        return "my preferred database"

    if "workplace" in key or "work" in key or "job" in key:
        return "my workplace"

    if "wife" in key:
        return "my wife's name"

    return key


def _clean_question_key(text: str) -> str:
    key = (
        text.replace("what is my ", "")
        .replace("what's my ", "")
        .replace("who is my ", "")
        .replace("who's my ", "")
        .replace("where is my ", "")
        .replace("where's my ", "")
        .replace(" called", "")
        .replace(" named", "")
        .replace("?", "")
        .strip()
    )

    return "my " + key


def _remember_is_fact(fact: str):
    lowered = fact.lower()

    if " is called " in lowered:
        split_text = " is called "
    elif " is named " in lowered:
        split_text = " is named "
    elif " is " in lowered:
        split_text = " is "
    else:
        return None

    index = lowered.find(split_text)

    key = fact[:index].strip()
    value = fact[index + len(split_text):].strip()

    key = normalize_key(key)

    if not key or not value:
        return None

    return remember(key, value)


def _try_natural_memory(command: str):
    text = command.lower().strip()

    if text.startswith("my ") and (
        " is called " in text
        or " is named " in text
        or " is " in text
    ):
        return _remember_is_fact(command)

    if text.startswith("i work at "):
        value = command[len("I work at "):].strip()
        return remember("my workplace", value)

    if text.startswith("i work for "):
        value = command[len("I work for "):].strip()
        return remember("my workplace", value)

    if text.startswith("i prefer "):
        value = command[len("I prefer "):].strip()
        return remember("my preferred database", value)

    if text.startswith("i like "):
        value = command[len("I like "):].strip()
        return remember("something I like", value)

    return None


def _is_health_check_request(text: str) -> bool:
    health_phrases = [
        "jarvis health",
        "health check",
        "system health",
        "jarvis status",
        "status check",
        "are you healthy",
        "are you ok",
        "are you okay",
    ]

    return any(phrase in text for phrase in health_phrases)


def route(command: str) -> str:
    text = command.lower().strip()

    if not text:
        return "I didn't hear anything, Marty."

    if _is_health_check_request(text):
        return get_health_response()

    if text.startswith("remember that "):
        fact = command[len("remember that "):].strip()

        response = _remember_is_fact(fact)
        if response:
            return response

        return "I can remember that, but say it like: remember that my favorite ship is Eurodam."

    if text.startswith("update my ") and " to " in text:
        fact = command[len("update "):].strip()
        key, value = fact.split(" to ", 1)

        key = normalize_key(key)
        value = value.strip()

        return update_memory(key, value)

    if text.startswith("forget that "):
        key = command[len("forget that "):].strip().lower()
        key = normalize_key(key)

        return forget(key)

    if (
        text.startswith("what is my ")
        or text.startswith("what's my ")
        or text.startswith("who is my ")
        or text.startswith("who's my ")
        or text.startswith("where is my ")
        or text.startswith("where's my ")
    ):
        key = normalize_key(_clean_question_key(text))

        value = recall(key)
        if value:
            return f"Your {key.replace('my ', '')} is {value}, Marty."

        return f"I don't have your {key.replace('my ', '')} saved yet."

    if text in ["what do you remember", "what do you remember about me"]:
        memories = get_all_memories()

        if not memories:
            return "I don't have any long-term memories saved yet, Marty."

        response = "Here's what I remember, Marty: "
        response += "; ".join([f"{k} is {v}" for k, v in memories.items()])
        return response

    natural_memory_response = _try_natural_memory(command)
    if natural_memory_response:
        return natural_memory_response

    if "time" in text or "date" in text:
        return get_time_response()

    if (
        "system" in text
        or "cpu" in text
        or "memory" in text
        or "disk" in text
        or "status" in text
    ):
        return get_system_response()

    if (
        text in ["hello", "hi", "hey", "hey jarvis", "hello jarvis"]
        or "how are you" in text
    ):
        return get_chat_response(command)

    print("[BRAIN] Falling back to LLM...")
    return get_llm_response(command)
