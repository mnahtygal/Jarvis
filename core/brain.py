# core/brain.py

from core.router import route
from core.session import (
    remember_user_message,
    remember_assistant_message,
    set_last_topic,
)


def detect_topic(command: str):
    text = command.lower()

    topics = [
        "flask",
        "express",
        "python",
        "node",
        "node.js",
        "javascript",
        "ollama",
        "qwen",
        "jarvis",
        "react",
        "vite",
        "flask api",
        "backend",
        "frontend",
        "memory",
        "llm",
    ]

    for topic in topics:
        if topic in text:
            return topic

    return None


def think(command: str) -> str:
    cleaned_command = command.strip()

    print(f"[BRAIN] Heard: {cleaned_command}")

    remember_user_message(cleaned_command)

    topic = detect_topic(cleaned_command)
    if topic:
        set_last_topic(topic)

    response = route(cleaned_command)

    remember_assistant_message(response)

    return response
