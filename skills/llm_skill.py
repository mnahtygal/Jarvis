# skills/llm_skill.py

import requests

from skills.llama_cpp_skill import ask_llama_cpp
from skills.ollama_skill import ask_ollama


def _is_bad_answer(answer: str) -> bool:
    """
    Basic sanity check for LLM responses.
    """

    if not answer:
        return True

    if len(set(answer)) <= 2 and len(answer) > 10:
        return True

    return False


def ask_local_llm(user_text: str) -> str:
    """
    Main Jarvis LLM router.

    Preferred backend:
    - llama.cpp OpenAI-compatible server on port 8080

    Fallback backend:
    - Ollama on port 11434
    """

    try:
        answer = ask_llama_cpp(user_text)

        if not _is_bad_answer(answer):
            print("[LLM] Using llama.cpp")
            return answer

        print("[LLM] llama.cpp returned an empty/bad answer. Falling back to Ollama...")

    except requests.exceptions.RequestException as error:
        print(f"[LLM] llama.cpp unavailable: {error}")
        print("[LLM] Falling back to Ollama...")

    except Exception as error:
        print(f"[LLM] llama.cpp unexpected error: {error}")
        print("[LLM] Falling back to Ollama...")

    try:
        answer = ask_ollama(user_text)

        if not _is_bad_answer(answer):
            print("[LLM] Using Ollama fallback")
            return answer

        return "My local brain returned nothing useful from llama.cpp or Ollama."

    except requests.exceptions.RequestException as error:
        return f"Sorry Marty, I had trouble reaching both local brains. Ollama error: {error}"

    except Exception as error:
        return f"Sorry Marty, both local brain paths failed. Error: {error}"


def get_llm_response(command: str) -> str:
    return ask_local_llm(command)
