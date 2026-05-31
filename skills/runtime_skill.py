# skills/runtime_skill.py

"""
Runtime and project identity responses for Jarvis.

These responses are deterministic on purpose. They describe what Jarvis is,
where it is running, what local model stack it uses, and what the project is
being built toward.

Keeping this in a skill keeps core/router.py cleaner and avoids sending
identity questions through the LLM when Jarvis already knows the answer.
"""


def get_runtime_identity_response() -> str:
    return (
        "I'm running locally on your NVIDIA Thor system using Qwen3 30B "
        "through llama.cpp. My memory stack is PostgreSQL for exact memory "
        "and conversation history, plus pgvector semantic memory for meaning-based recall. "
        "Voice and camera are planned later, but not active yet."
    )


def get_platform_response() -> str:
    return (
        "I'm running on your NVIDIA Thor system. That is the active Jarvis platform now, "
        "with local inference, PostgreSQL memory, and pgvector semantic memory."
    )


def get_model_response() -> str:
    return (
        "I'm using Qwen3 30B through llama.cpp as the primary local model runtime. "
        "Ollama remains available as a fallback path."
    )


def get_memory_stack_response() -> str:
    return (
        "My memory stack has three main parts: exact long-term memory in PostgreSQL, "
        "conversation history in PostgreSQL, and semantic memory using pgvector for "
        "meaning-based recall."
    )


def get_jarvis_goal_response() -> str:
    return (
        "The long-term goal for Jarvis is to become your local-first AI assistant: "
        "running on Thor, using local models through llama.cpp, backed by PostgreSQL "
        "and pgvector memory, and eventually adding voice and camera support. "
        "Longer term, Jarvis could grow into a useful manufacturing prototype assistant too."
    )
