import re
import requests

from core.memory import get_context

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:3b"

SYSTEM_PROMPT = """
You are Jarvis, a concise, intelligent, and helpful AI assistant running locally on Marty's Jetson device.

Rules:
- Keep answers short and clear by default, usually 1 to 3 sentences unless asked for more.
- Speak naturally, like a real assistant.
- Avoid markdown unless the user asks for lists, code, or steps.
- Be confident and direct.
- Prefer practical answers over theory.
- If it is technical, be precise but still concise.
- Use the conversation context carefully for follow-up questions.
- Never assume "it" means Qwen, Ollama, AI, or yourself unless the user specifically asks about those.
- Never say "as an AI model".
""".strip()


def clean_response(text: str) -> str:
    text = text.strip()
    text = text.replace("\n", " ")
    text = text.replace("Jarvis:", "").strip()
    return " ".join(text.split())


def get_last_user_topic(context: str) -> str:
    if not context:
        return ""

    user_lines = [
        line.replace("User:", "").strip()
        for line in context.splitlines()
        if line.startswith("User:")
    ]

    if not user_lines:
        return ""

    last_user = user_lines[-1].lower().strip()

    patterns = [
        r"what is ([a-zA-Z0-9 ._-]+)",
        r"what are ([a-zA-Z0-9 ._-]+)",
        r"explain ([a-zA-Z0-9 ._-]+)",
        r"tell me about ([a-zA-Z0-9 ._-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, last_user)
        if match:
            topic = match.group(1).strip()
            topic = topic.replace("?", "").strip()
            return topic

    return last_user.replace("?", "").strip()


def is_followup(user_text: str) -> bool:
    text = user_text.lower().strip()
    followup_phrases = [
        "it",
        "that",
        "this",
        "they",
        "them",
        "how is it",
        "how are they",
        "how is that",
        "what about",
        "compare it",
        "different from",
    ]
    return any(phrase in text for phrase in followup_phrases)


def build_prompt(user_text: str) -> str:
    context = get_context()
    current_topic = get_last_user_topic(context)

    followup_note = ""
    if context and current_topic and is_followup(user_text):
        followup_note = f"""
Important follow-up rule:
The user's current question is a follow-up.
In this question, words like "it", "that", or "this" refer to: {current_topic}.
Do not interpret them as Qwen, Ollama, AI, or yourself.
""".strip()

    if context:
        return f"""
{SYSTEM_PROMPT}

Conversation so far:
{context}

{followup_note}

User: {user_text}
Jarvis:
""".strip()

    return f"""
{SYSTEM_PROMPT}

User: {user_text}
Jarvis:
""".strip()


def ask_llm(user_text: str) -> str:
    prompt = build_prompt(user_text)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 180,
                },
            },
            timeout=60,
        )

        if response.status_code != 200:
            print("LLM HTTP error:", response.text)
            return "I’m having trouble thinking right now."

        data = response.json()
        text = data.get("response", "")

        if not text.strip():
            return "I didn’t come up with a response."

        return clean_response(text)

    except requests.exceptions.Timeout:
        return "My local brain took too long to respond."

    except requests.exceptions.ConnectionError:
        return "I cannot reach Ollama right now. Make sure it is running."

    except Exception as e:
        print("LLM error:", e)
        return "Something went wrong with my local brain."
