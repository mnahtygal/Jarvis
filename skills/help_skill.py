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

Memory recall:
- "what is my favorite ship?"
- "what do you remember about me?"
- "semantic search calibration"
- Chat and voice cannot save, update, or forget long-term memories.
- The trusted local memory console supports approved project notes. Exact-memory approval is unavailable.

AI brain:
- Unknown questions fall back to the local LLM.
- Primary LLM backend: llama.cpp on port 8080.
- Fallback LLM backend: Ollama on port 11434.
- Jarvis uses long-term memory, recent conversation history, and last_topic for context.

Current project status:
- Voice and camera are planned later.
""".strip()
