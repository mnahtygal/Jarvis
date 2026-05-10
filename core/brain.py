# core/brain.py

from core.router import route
from core.session import (
    remember_user_message,
    remember_assistant_message,
    set_last_topic,
)


TOPIC_ALIASES = {
    "flask api": "Flask API",
    "flask": "Flask",
    "express": "Express",
    "node.js": "Node.js",
    "node": "Node.js",
    "javascript": "JavaScript",
    "python": "Python",
    "ollama": "Ollama",
    "llama.cpp": "llama.cpp",
    "llama": "llama.cpp",
    "qwen": "Qwen",
    "jarvis": "Jarvis",
    "react": "React",
    "vite": "Vite",
    "backend": "backend",
    "frontend": "frontend",
    "memory": "memory",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "pgvector": "pgvector",
    "llm": "LLM",
    "conversation history": "conversation history",
    "health check": "health check",
}


FOLLOW_UP_PHRASES = [
    "how is it different",
    "how is that different",
    "what about that",
    "what about it",
    "tell me more",
    "explain more",
    "why is that",
    "how does it work",
    "compare it",
]


def detect_topic(command: str):
    text = command.lower().strip()

    if not text:
        return None

    # If this is clearly a follow-up, do not overwrite last_topic.
    for phrase in FOLLOW_UP_PHRASES:
        if phrase in text:
            return None

    # Match longer aliases first so "flask api" wins before "flask".
    for alias, topic in sorted(TOPIC_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in text:
            return topic

    # Basic "what is X" / "explain X" style fallback.
    starter_phrases = [
        "what is ",
        "what's ",
        "explain ",
        "tell me about ",
        "define ",
    ]

    for phrase in starter_phrases:
        if text.startswith(phrase):
            topic = text[len(phrase):].strip(" ?.!")
            if topic:
                return topic[:80]

    return None


def think(command: str) -> str:
    cleaned_command = command.strip()

    if not cleaned_command:
        return "I didn't hear anything, Marty."

    print(f"[BRAIN] Heard: {cleaned_command}")

    remember_user_message(cleaned_command)

    topic = detect_topic(cleaned_command)
    if topic:
        set_last_topic(topic)

    response = route(cleaned_command)

    remember_assistant_message(response)

    return response
