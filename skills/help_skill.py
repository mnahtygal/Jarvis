# skills/help_skill.py


def get_help_response() -> str:
    return """
Jarvis capabilities, Marty:

Core commands:
- "what can you do" or "jarvis help" - show this help
- "jarvis health" - run Jarvis health checks
- "jarvis version" - show Jarvis version and backend info
- "jarvis memory summary" - summarize current memory/session state
- "what time is it" or "what is the date" - time/date response
- "system status" - CPU, memory, disk, or system status

Memory commands:
- "remember that my favorite ship is Eurodam"
- "my test project is called blue falcon"
- "what is my favorite ship?"
- "what do you remember about me?"
- "update my preferred database to PostgreSQL"
- "forget that my test project"

AI brain:
- Unknown questions fall back to the local LLM.
- Primary LLM backend: llama.cpp on port 8080.
- Fallback LLM backend: Ollama on port 11434.
- Jarvis uses long-term memory, recent conversation history, and last_topic for context.

Current project status:
- Voice and camera are planned later.
- pgvector semantic memory is planned next, but not active yet.
""".strip()
