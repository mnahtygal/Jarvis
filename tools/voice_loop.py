#!/usr/bin/env python3

"""
Jarvis Voice Loop

Flow:
    microphone → Whisper transcription → Jarvis brain → Piper speech

Usage:
    python3 tools/voice_loop.py

Optional:
    python3 tools/voice_loop.py 6
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from audio.listen import listen_command  # noqa: E402
from audio.speak import speak  # noqa: E402
from core.brain import think  # noqa: E402


EXIT_PHRASES = {
    "exit",
    "quit",
    "stop",
    "stop listening",
    "shutdown",
    "shut down",
    "goodbye",
    "goodbye jarvis",
}


def should_exit(text: str) -> bool:
    cleaned = (text or "").strip().lower().strip(".!?")
    return cleaned in EXIT_PHRASES


def main() -> int:
    seconds = 5

    if len(sys.argv) > 1:
        try:
            seconds = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 tools/voice_loop.py [listen_seconds]")
            return 1

    print("Jarvis Voice Loop Ready")
    print("Say 'stop listening' or 'goodbye Jarvis' to exit.")
    print("")

    speak("Jarvis voice loop is online.")

    while True:
        print("")
        print("[VOICE] Listening...")

        user_text = listen_command(seconds=seconds)

        if not user_text:
            print("[VOICE] No speech detected.")
            continue

        print(f"[YOU] {user_text}")

        if should_exit(user_text):
            response = "Goodbye Marty."
            print(f"[JARVIS] {response}")
            speak(response)
            break

        response = think(user_text)

        print(f"[JARVIS] {response}")
        speak(response)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
