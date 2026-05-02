# skills/llm_skill.py

import subprocess
from core.session import get_context


MODEL = "qwen2.5-coder:3b"


SYSTEM_PROMPT = """
You are Jarvis, a concise and helpful local AI assistant running on Marty's Jetson device.

Be clear, practical, and conversational.
Keep most answers short unless more detail is asked for.
If asked about system/device/project help, be technically helpful.

Use the conversation context to answer follow-up questions.
If Marty says "it", "that", "this", or asks a comparison question,
infer what he means from the recent conversation and last topic.

Be technically accurate.
Do not say Flask and Express are both Python frameworks.
Flask is a Python web framework.
Express is a Node.js / JavaScript web framework.

When comparing technologies, use this format:
- What each one is
- Main difference
- When you would use each
""".strip()


def ask_local_llm(user_text: str) -> str:
    context = get_context()

    prompt = f"""
{SYSTEM_PROMPT}

Conversation context:
{context}

User: {user_text}
Jarvis:
""".strip()

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print("ollama stderr:", result.stderr)
            return "I had trouble reaching my local brain."

        response = result.stdout.strip()
        if not response:
            return "My local brain did not return anything."

        return response

    except subprocess.TimeoutExpired:
        return "My local brain took too long to respond."

    except Exception as e:
        print("ask_local_llm error:", e)
        return "Something went wrong with my local brain."


def get_llm_response(command: str) -> str:
    return ask_local_llm(command)
