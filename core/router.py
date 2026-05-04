# core/router.py

from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response
from skills.llm_skill import get_llm_response
from core.memory import remember_fact, recall_fact, get_all_facts


def route(command: str) -> str:
    text = command.lower().strip()

    if not text:
        return "I didn't hear anything, Marty."

    # Long-term memory: remember simple facts
    if text.startswith("remember that "):
        fact = command[len("remember that "):].strip()

        if " is " in fact:
            key, value = fact.split(" is ", 1)
            key = key.strip().lower()
            value = value.strip()
            remember_fact(key, value)
            return f"Got it, Marty. I'll remember that {key} is {value}."

        return "I can remember that, but say it like: remember that my favorite ship is Eurodam."

    # Long-term memory: recall simple facts
    if text.startswith("what is my ") or text.startswith("what's my "):
        key = text.replace("what is my ", "").replace("what's my ", "").replace("?", "").strip()
        key = "my " + key

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

