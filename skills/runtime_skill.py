# skills/runtime_skill.py

"""
Runtime and project identity responses for Jarvis.

These responses are deterministic on purpose. They describe what Jarvis is,
where it is running, what local model stack it uses, and what the project is
being built toward.
"""

from skills.model_runtime import get_active_model_friendly_name


def get_runtime_identity_response() -> str:
    active_model = get_active_model_friendly_name()

    return (
        f"I'm running locally on your NVIDIA Thor system using {active_model} "
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
    active_model = get_active_model_friendly_name()

    return (
        f"I'm currently using {active_model} through llama.cpp as the active local runtime. "
        "Qwen3 remains the default Jarvis model and additional local models can be used for testing."
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
