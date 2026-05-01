import os
import signal
import subprocess
import time
import whisper

model = whisper.load_model("tiny")

DEVICE = "alsa_input.usb-Samson_Technologies_Samson_Q2U_Microphone-00.analog-stereo"


def record_wav(filename: str, seconds: int = 5) -> bool:
    print("🎤 Get ready...")

    if os.path.exists(filename):
        os.remove(filename)

    raw_file = "temp_audio.raw"
    if os.path.exists(raw_file):
        os.remove(raw_file)

    time.sleep(1)
    print("🎤 SPEAK NOW")

    cmd = [
        "parec",
        "-d", DEVICE,
        "--format=s16le",
        "--rate=16000",
        "--channels=1",
    ]

    try:
        with open(raw_file, "wb") as f:
            proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.PIPE)
            time.sleep(seconds)
            proc.send_signal(signal.SIGINT)
            _, stderr = proc.communicate(timeout=5)

        if stderr:
            err_text = stderr.decode(errors="ignore").strip()
            if err_text:
                print("parec stderr:", err_text)

        if not os.path.exists(raw_file):
            print("❌ Raw audio file was not created")
            return False

        raw_size = os.path.getsize(raw_file)
        print(f"✅ Raw audio captured: {raw_size} bytes")

        if raw_size < 1000:
            print("❌ Raw audio file too small")
            return False

        convert_cmd = [
            "ffmpeg",
            "-y",
            "-f", "s16le",
            "-ar", "16000",
            "-ac", "1",
            "-i", raw_file,
            filename,
        ]

        result = subprocess.run(convert_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("❌ ffmpeg conversion failed")
            print(result.stderr)
            return False

        if not os.path.exists(filename):
            print("❌ WAV file was not created")
            return False

        wav_size = os.path.getsize(filename)
        print(f"✅ WAV created: {filename} ({wav_size} bytes)")
        return wav_size >= 1000

    except Exception as e:
        print(f"❌ record_wav exception: {e}")
        return False

    finally:
        if os.path.exists(raw_file):
            os.remove(raw_file)


def transcribe_file(filename: str) -> str:
    result = model.transcribe(filename, fp16=False, language="en")
    return result["text"].strip().lower()


def listen_command() -> str:
    filename = "command.wav"

    ok = record_wav(filename, 5)
    if not ok:
        return ""

    text = transcribe_file(filename)
    print(f"You said: {text}")
    return text
