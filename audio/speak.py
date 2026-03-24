import os
import shlex
import subprocess

PIPER_BIN = os.path.expanduser("~/piper/piper")
PIPER_MODEL = os.path.expanduser("~/jarvis/models/piper/en_US-lessac-medium.onnx")
PIPER_CONFIG = os.path.expanduser("~/jarvis/models/piper/en_US-lessac-medium.onnx.json")

def speak(text: str):
    text = text.strip()
    if not text:
        return

    safe_text = shlex.quote(text)
    safe_bin = shlex.quote(PIPER_BIN)
    safe_model = shlex.quote(PIPER_MODEL)
    safe_config = shlex.quote(PIPER_CONFIG)

    cmd = (
        f"echo {safe_text} | "
        f"{safe_bin} --model {safe_model} --config {safe_config} --output-raw | "
        f"aplay -r 22050 -f S16_LE -t raw -"
    )
    subprocess.run(cmd, shell=True, check=False)
