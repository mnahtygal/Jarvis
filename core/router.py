# core/router.py

from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response
from skills.llm_skill import get_llm_response
from core.memory import remember_fact, update_fact, forget_fact, recall_fact, get_all_facts


def _clean_question_key(text: str) -> str:
    key = (
        text.replace("what is my ", "")
        .replace("what's my ", "")
        .replace("who is my ", "")
        .replace("who's my ", "")
        .replace("where is my ", "")
        .replace("where's my ", "")
        .replace("?", "")
        .strip()
    )

    return "my " + key


def _remember_is_fact(fact: str):
    if " is " not in fact:
        return None

    key, value = fact.split(" is ", 1)
    key = key.strip().lower()
    value = value.strip()

    if not key or not value:
        return None

    remember_fact(key, value)
    return f"Got it, Marty. I'll remember that {key} is {value}."


def _try_natural_memory(command: str):
    text = command.lower().strip()

    # "my wife is Kelly"
    # "my favorite ship is Eurodam"
    if text.startswith("my ") and " is " in text:
        return _remember_is_fact(command)

    # "I work at GM"
    if text.startswith("i work at "):
        value = command[len("I work at "):].strip()
        remember_fact("my workplace", value)
        return f"Got it, Marty. I'll remember that your workplace is {value}."

    # "I work for GM"
    if text.startswith("i work for "):
        value = command[len("I work for "):].strip()
        remember_fact("my workplace", value)
        return f"Got it, Marty. I'll remember that your workplace is {value}."

    # "I prefer SQL Server"
    if text.startswith("i prefer "):
        value = command[len("I prefer "):].strip()
        remember_fact("my preference", value)
        return f"Got it, Marty. I'll remember that you prefer {value}."

    # "I like Eurodam"
    if text.startswith("i like "):
        value = command[len("I like "):].strip()
        remember_fact("something I like", value)
        return f"Got it, Marty. I'll remember that you like {value}."

    return None


def route(command: str) -> str:
    text = command.lower().strip()

    if not text:
        return "I didn't hear anything, Marty."

    # Long-term memory: remember explicit facts
    if text.startswith("remember that "):
        fact = command[len("remember that "):].strip()

        response = _remember_is_fact(fact)
        if response:
            return response

        return "I can remember that, but say it like: remember that my favorite ship is Eurodam."

    # Long-term memory: update facts
    if text.startswith("update my ") and " to " in text:
        fact = command[len("update "):].strip()
        key, value = fact.split(" to ", 1)
        key = key.strip().lower()
        value = value.strip()

        old_value = update_fact(key, value)

        if old_value:
            return f"Updated, Marty. Your {key.replace('my ', '')} changed from {old_value} to {value}."

        return f"Got it, Marty. I saved your {key.replace('my ', '')} as {value}."

    # Long-term memory: forget facts
    if text.startswith("forget that "):
        key = command[len("forget that "):].strip().lower()

        old_value = forget_fact(key)

        if old_value:
            return f"Forgot it, Marty. I removed {key} from memory."

        return f"I couldn't find {key} in memory, Marty."

    # Long-term memory: recall simple facts
    if (
        text.startswith("what is my ")
        or text.startswith("what's my ")
        or text.startswith("who is my ")
        or text.startswith("who's my ")
        or text.startswith("where is my ")
        or text.startswith("where's my ")
    ):
        key = _clean_question_key(text)

        value = recall_fact(key)
        if value:
            return f"Your {key.replace('my ', '')} is {value}, Marty."

        return f"I don't have your {key.replace('my ', '')} saved yet."

    if text in ["what do you remember", "what do you remember about me"]:
        facts = get_all_facts()

        if not facts:
            return "I don't have any long-term memories saved yet, Marty."

        response = "Here's what I remember, Marty: "
        response += "; ".join([f"{k} is {v}" for k, v in facts.items()])
        return response

    # Natural memory parsing before LLM fallback
    natural_memory_response = _try_natural_memory(command)
    if natural_memory_response:
        return natural_memory_response

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

