import subprocess


MODEL = "qwen2.5-coder:3b"


SYSTEM_PROMPT = """
You are Jarvis, a concise and helpful local AI assistant running on Marty's Jetson device.
Be clear, practical, and conversational.
Keep most answers short unless more detail is asked for.
If asked about system/device/project help, be technically helpful.
""".strip()


def ask_local_llm(user_text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_text}\nJarvis:"

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print("ollama stderr:", result.stderr)
            return "I had trouble reaching my local brain."

        response = result.stdout.strip()
        if not response:
            return "My local brain did not return anything."

        return response

    except subprocess.TimeoutExpired:
        return "My local brain took too long to respond."

    except Exception as e:
        print("ask_local_llm error:", e)
        return "Something went wrong with my local brain."
