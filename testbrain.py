#!/usr/bin/env python3

from core.brain import think
from core.session import new_session, get_recent_history


HELP = """
Commands:
  :multi      Enter multiline prompt mode
  :end        Finish multiline prompt
  :new        Start a fresh Jarvis conversation session
  :history    Show recent conversation history
  :help       Show this help
  :quit       Exit Jarvis
""".strip()


def ask_jarvis(text: str):
    text = text.strip()

    if not text:
        return

    response = think(text)
    print(f"\nJarvis: {response}\n")


def multiline_prompt():
    print()
    print("Paste your multiline prompt.")
    print("When finished, enter :end on a line by itself.")
    print()

    lines = []

    while True:
        try:
            line = input()
        except EOFError:
            break

        if line.strip().lower() == ":end":
            break

        lines.append(line)

    return "\n".join(lines).strip()


print("Jarvis Developer Console")
print("Type :help for commands.")
print()

while True:
    try:
        user_input = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nJarvis shutting down...")
        break

    if not user_input:
        continue

    command = user_input.lower()

    if command in ("exit", "quit", ":quit", ":exit"):
        print("Jarvis shutting down...")
        break

    if command == ":help":
        print()
        print(HELP)
        print()
        continue

    if command == ":new":
        session_id = new_session()
        print(f"\n[JARVIS] New conversation session: {session_id}\n")
        continue

    if command == ":history":
        history = get_recent_history(limit=12)

        print()
        if not history:
            print("[JARVIS] No conversation history.")
        else:
            for item in history:
                role = item["role"].upper()
                print(f"{role}: {item['content']}")
        print()
        continue

    if command == ":multi":
        prompt = multiline_prompt()

        if not prompt:
            print("[JARVIS] Multiline prompt was empty.\n")
            continue

        print()
        print(f"[JARVIS] Submitting multiline prompt ({len(prompt)} characters)...")
        ask_jarvis(prompt)
        continue

    ask_jarvis(user_input)
