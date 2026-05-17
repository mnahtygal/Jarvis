# audio/speak.py

"""
Jarvis text-to-speech using local Piper.

Expected local files:

    ~/piper/piper
    ~/piper/libpiper_phonemize.so.1
    ~/jarvis/models/piper/en_US-lessac-medium.onnx
    ~/jarvis/models/piper/en_US-lessac-medium.onnx.json

Usage:

    python3 audio/speak.py "Hello Marty, Jarvis voice is online."

From Python:

    from audio.speak import speak
    speak("Hello Marty.")
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


PIPER_DIR = Path.home() / "piper"
PIPER_BIN = PIPER_DIR / "piper"
PIPER_MODEL = Path.home() / "jarvis" / "models" / "piper" / "en_GB-northern_english_male-medium.onnx"
PIPER_CONFIG = Path.home() / "jarvis" / "models" / "piper" / "en_GB-northern_english_male-medium.onnx.json"


def _verify_files() -> None:
    required = [
        PIPER_BIN,
        PIPER_DIR / "libpiper_phonemize.so.1",
        PIPER_MODEL,
        PIPER_CONFIG,
    ]

    missing = [str(path) for path in required if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Missing Piper file(s): " + ", ".join(missing)
        )


def clean_text_for_speech(text: str) -> str:
    """
    Remove Markdown/control formatting that sounds bad in TTS.
    """
    cleaned = text or ""

    # Remove fenced code markers and inline code ticks.
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")

    # Convert common markdown bullets/headings to plain speech.
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)

    # Remove markdown emphasis markers.
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = cleaned.replace("*", "")

    # Remove markdown links but keep the text.
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # Make whitespace speech-friendly.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned

def speak(text: str) -> bool:
    """
    Speak text using Piper and paplay.

    Returns True if synthesis/playback command completed successfully.
    """
    cleaned = clean_text_for_speech(text)

    if not cleaned:
        return False

    _verify_files()

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{PIPER_DIR}:{env.get('LD_LIBRARY_PATH', '')}"

    with tempfile.NamedTemporaryFile(
        prefix="jarvis_tts_",
        suffix=".wav",
        delete=False,
    ) as tmp:
        wav_path = Path(tmp.name)

    try:
        synth = subprocess.run(
            [
                str(PIPER_BIN),
                "--model",
                str(PIPER_MODEL),
                "--config",
                str(PIPER_CONFIG),
                "--output_file",
                str(wav_path),
            ],
            input=cleaned,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

        if synth.returncode != 0:
            print("[TTS] Piper failed:")
            print(synth.stderr.strip())
            return False

        play = subprocess.run(
            ["paplay", str(wav_path)],
            text=True,
            capture_output=True,
            check=False,
        )

        if play.returncode != 0:
            print("[TTS] paplay failed:")
            print(play.stderr.strip())
            return False

        return True

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    text = " ".join(sys.argv[1:]).strip()

    if not text:
        print('Usage: python3 audio/speak.py "Text to speak"')
        return 1

    ok = speak(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
