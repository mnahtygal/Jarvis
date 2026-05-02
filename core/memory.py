MAX_MEMORY = 5  # number of past exchanges to keep

conversation = []


def add_to_memory(user: str, assistant: str):
    conversation.append({
        "user": user,
        "assistant": assistant
    })

    if len(conversation) > MAX_MEMORY:
        conversation.pop(0)


def get_context() -> str:
    if not conversation:
        return ""

    lines = []
    for item in conversation:
        lines.append(f"User: {item['user']}")
        lines.append(f"Jarvis: {item['assistant']}")

    return "\n".join(lines)
