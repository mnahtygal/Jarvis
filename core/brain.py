# core/brain.py

from core.router import route
from core.llm import ask_llm

def think(command: str) -> str:
    if not command:
        return "I didn't catch that."

    command = command.lower().strip()

    print(f"[BRAIN] Heard: {command}")

    # 1. Try fast skill routing
    response = route(command)

    if response:
        print("[BRAIN] Skill handled it")
        return response

    # 2. Fallback to LLM
    print("[BRAIN] Falling back to LLM...")
    return ask_llm(command)
