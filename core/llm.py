# core/llm.py

import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:3b"


def ask_llm(prompt: str) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": (
                    "You are Jarvis, Marty's local AI assistant running on a Jetson. "
                    "Answer in 1 to 3 short sentences. "
                    "Be direct, practical, and conversational. "
                    "Do not give long lists unless Marty asks for details.\n\n"
                    f"Marty: {prompt}\n"
                    "Jarvis:"
                ),
                "stream": False,
                "options": {
                    "num_predict": 60,
                    "temperature": 0.3
                }
            },
            timeout=60
        )

        data = response.json()
        return data.get("response", "Hmm, I didn’t get that.")

    except Exception as e:
        return f"LLM error: {str(e)}"
