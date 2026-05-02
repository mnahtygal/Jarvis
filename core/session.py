# core/session.py

conversation = {
    "last_topic": None,
    "history": []
}


def remember_user_message(message: str):
    conversation["history"].append({
        "role": "user",
        "content": message
    })
    conversation["history"] = conversation["history"][-8:]


def remember_assistant_message(message: str):
    conversation["history"].append({
        "role": "assistant",
        "content": message
    })
    conversation["history"] = conversation["history"][-8:]


def set_last_topic(topic: str):
    if topic:
        conversation["last_topic"] = topic


def get_last_topic():
    return conversation.get("last_topic")


def get_context() -> str:
    last_topic = conversation.get("last_topic") or "None"

    history_text = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in conversation["history"]
    )

    return f"""
Last topic: {last_topic}

Recent conversation:
{history_text}
""".strip()
