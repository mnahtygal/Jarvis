def get_chat_response(command: str) -> str:
    text = command.lower().strip()

    if "hello" in text or "hi" in text or "hey" in text:
        return "Hello Marty. I'm here and ready."

    return "I'm here."
