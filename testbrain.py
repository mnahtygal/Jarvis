#!/usr/bin/env python3

from core.brain import think

print("Jarvis CLI Ready (type 'exit' to quit)\n")

while True:
    user_input = input("You: ").strip()

    if not user_input:
        continue

    if user_input.lower() in ["exit", "quit"]:
        print("Jarvis shutting down...")
        break

    response = think(user_input)
    print(f"Jarvis: {response}\n")
