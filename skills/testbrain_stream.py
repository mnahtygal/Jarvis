from skills.llm_stream_skill import stream_local_llm


print("Jarvis Streaming CLI Ready (type 'exit' to quit)")

while True:
    user_input = input("\nYou: ").strip()

    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye.")
        break

    if not user_input:
        continue

    print("[BRAIN] Heard:", user_input.lower())
    print("[BRAIN] Falling back to streaming LLM...")
    print("Jarvis: ", end="", flush=True)

    for chunk in stream_local_llm(user_input):
        print(chunk, end="", flush=True)

    print()
