import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:3b"

SYSTEM_PROMPT = """
You are Jarvis, a concise, intelligent, and helpful AI assistant running locally on Marty's Jetson device.

Rules:
- Keep answers short and clear by default (1–3 sentences unless asked for more)
- Speak naturally, like a real assistant (no markdown, no bullet lists unless asked)
- Be confident and direct
- Prefer practical answers over theory
- If it's a simple question, give a simple answer
- If it's technical, be precise but still concise

Never say "as an AI model".
""".strip()


def ask_llm(user_text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_text}\nJarvis:"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "num_predict": 200
                }
            },
            timeout=60,
        )

        if response.status_code != 200:
            print("LLM HTTP error:", response.text)
            return "I’m having trouble thinking right now."

        data = response.json()
        text = data.get("response", "").strip()

        if not text:
            return "I didn’t come up with a response."

        # Clean for speech
        text = text.replace("\n", " ").strip()

        return text

    except Exception as e:
        print("LLM error:", e)
        return "Something went wrong with my local brain."
