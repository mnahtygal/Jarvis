# skills/llm_skill.py

import requests
from core.session import get_context


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"


SYSTEM_PROMPT = """
You are Jarvis, Marty's local AI assistant.

Rules:
- Answer clearly and briefly.
- Use recent context for follow-up questions.
- If Marty asks "how is it different", compare against the last topic.
- Flask is Python.
- Express is Node.js / JavaScript.
""".strip()


def ask_local_llm(user_text: str) -> str:
    context = get_context()

    prompt = f"""
{SYSTEM_PROMPT}

Recent context:
{context}

Question:
{user_text}

Answer:
""".strip()

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 200
                }
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()
        answer = data.get("response", "").strip()

        if not answer:
            return "My local brain returned nothing."

        if len(set(answer)) <= 2 and len(answer) > 10:
            return "My local brain returned a bad repeated-character response. Try again."

        return answer

    except requests.exceptions.RequestException as error:
        return f"Sorry Marty, I had trouble reaching my local brain: {error}"


def get_llm_response(command: str) -> str:
    return ask_local_llm(command)
