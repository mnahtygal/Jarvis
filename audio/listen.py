import os
import subprocess
import time
import whisper

model = whisper.load_model("tiny")
SOURCE = "alsa_input.usb-Amba_Insta360_Link-02.mono-fallback"


def record_wav(filename: str, seconds: int = 4):
    print("🎤 Get ready...")
    time.sleep(1.0)  # give PulseAudio time to settle before speaking

    cmd = [
        "timeout", f"{seconds}s",
        "parec",
        f"--device={SOURCE}",
        "--rate=16000",
        "--channels=1",
        "--format=s16le",
        "--file-format=wav",
        filename,
    ]

    subprocess.run(cmd, check=False)


def transcribe_file(filename: str) -> str:
    result = model.transcribe(filename, fp16=False, language="en")
    return result["text"].strip().lower()


def listen_command() -> str:
    print("🎤 Ready...")
    record_wav("command.wav", 3)

    if os.path.exists("command.wav"):
        subprocess.run(["ls", "-lh", "command.wav"], check=False)

    text = transcribe_file("command.wav")
    print(f"You said: {repr(text)}")
    return text
