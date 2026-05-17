# audio/listen.py

"""
Jarvis speech-to-text using local Whisper.

Thor audio note:
- The Samson Q2U is managed by PipeWire/PulseAudio.
- Direct ALSA arecord may fail with "Device or resource busy".
- This listener uses parec against the configured/default Pulse source.

Usage:

    python3 audio/listen.py

From Python:

    from audio.listen import listen_command
    text = listen_command(seconds=5)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import whisper


DEFAULT_SOURCE = os.getenv(
    "JARVIS_MIC_SOURCE",
    "alsa_input.usb-Samson_Technologies_Samson_Q2U_Microphone-00.analog-stereo",
)

DEFAULT_SECONDS = int(os.getenv("JARVIS_LISTEN_SECONDS", "5"))

_MODEL = None


def get_whisper_model():
    global _MODEL

    if _MODEL is None:
        model_name = os.getenv("JARVIS_WHISPER_MODEL", "tiny")
        print(f"[LISTEN] Loading Whisper model: {model_name}")
        _MODEL = whisper.load_model(model_name)

    return _MODEL


def record_wav(
    output_path: Path,
    seconds: int = DEFAULT_SECONDS,
    source: Optional[str] = DEFAULT_SOURCE,
) -> bool:
    """
    Record WAV audio using parec/PipeWire.

    Returns True if the recording command exits cleanly.
    """
    cmd = [
        "timeout",
        str(seconds),
        "parec",
        "--format=s16le",
        "--rate=16000",
        "--channels=1",
        "--file-format=wav",
        str(output_path),
    ]

    if source:
        cmd.insert(3, f"--device={source}")

    print(f"[LISTEN] Recording {seconds} second(s)...")

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )

    # timeout exits 124 when it stops parec after N seconds.
    if result.returncode not in (0, 124):
        print("[LISTEN] Recording failed:")
        print(result.stderr.strip())
        return False

    return output_path.exists() and output_path.stat().st_size > 0


def transcribe_file(wav_path: Path) -> str:
    """
    Transcribe a WAV file using local Whisper.
    """
    model = get_whisper_model()

    result = model.transcribe(
        str(wav_path),
        fp16=False,
        language="en",
    )

    return result.get("text", "").strip()


def listen_command(seconds: int = DEFAULT_SECONDS) -> str:
    """
    Record and transcribe one command.
    """
    with tempfile.NamedTemporaryFile(
        prefix="jarvis_listen_",
        suffix=".wav",
        delete=False,
    ) as tmp:
        wav_path = Path(tmp.name)

    try:
        ok = record_wav(wav_path, seconds=seconds)

        if not ok:
            return ""

        text = transcribe_file(wav_path)
        print(f"[LISTEN] Heard: {text}")
        return text

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    seconds = DEFAULT_SECONDS

    if len(sys.argv) > 1:
        try:
            seconds = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 audio/listen.py [seconds]")
            return 1

    text = listen_command(seconds=seconds)

    if text:
        print(text)
        return 0

    print("[LISTEN] No speech detected.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
