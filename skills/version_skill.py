# skills/version_skill.py

from core.session import get_last_topic


JARVIS_VERSION = "0.4.0"
JARVIS_STAGE = "Local assistant foundation"
PRIMARY_LLM = "llama.cpp on 127.0.0.1:8080"
FALLBACK_LLM = "Ollama on localhost:11434"
CURRENT_MODEL = "Qwen2.5-Coder 7B"
DATABASE = "PostgreSQL"
SEMANTIC_MEMORY = "planned - pgvector not active yet"


def get_version_response() -> str:
    last_topic = get_last_topic() or "None"

    return f"""
Jarvis version report, Marty:

Version: {JARVIS_VERSION}
Stage: {JARVIS_STAGE}

Runtime:
- Primary LLM: {PRIMARY_LLM}
- Fallback LLM: {FALLBACK_LLM}
- Current model family: {CURRENT_MODEL}
- Database: {DATABASE}
- Semantic memory: {SEMANTIC_MEMORY}

Session:
- Last topic: {last_topic}

Current status:
- CLI brain loop: active
- Long-term memory: active
- Conversation history: active
- Session state: active
- Health command: active
- Help command: active
- Voice/camera: planned later
""".strip()
