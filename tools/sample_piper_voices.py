#!/usr/bin/env python3

from pathlib import Path
import os
import subprocess
import tempfile


PIPER_DIR = Path.home() / "piper"
PIPER_BIN = PIPER_DIR / "piper"
VOICE_DIR = Path.home() / "jarvis" / "models" / "piper"

SAMPLE_TEXT = (
    "Hello Marty. This is Jarvis testing this voice. "
    "I am running locally on Thor."
)


def play_voice(model_path: Path) -> None:
    config_path = Path(str(model_path) + ".json")

    if not config_path.exists():
        print(f"[SKIP] Missing config for {model_path.name}")
        return

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{PIPER_DIR}:{env.get('LD_LIBRARY_PATH', '')}"

    with tempfile.NamedTemporaryFile(
        prefix="jarvis_voice_sample_",
        suffix=".wav",
        delete=False,
    ) as tmp:
        wav_path = Path(tmp.name)

    try:
        print("")
        print("=" * 60)
        print(f"Voice: {model_path.stem}")
        print("=" * 60)

        synth = subprocess.run(
            [
                str(PIPER_BIN),
                "--model",
                str(model_path),
                "--config",
                str(config_path),
                "--output_file",
                str(wav_path),
            ],
            input=SAMPLE_TEXT,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

        if synth.returncode != 0:
            print("[ERROR] Piper failed:")
            print(synth.stderr.strip())
            return

        subprocess.run(["paplay", str(wav_path)], check=False)

    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    voices = sorted(VOICE_DIR.glob("*.onnx"))

    if not voices:
        print(f"No Piper voices found in {VOICE_DIR}")
        return 1

    print(f"Found {len(voices)} voice(s).")
    print("Press ENTER after each sample to continue, or CTRL+C to stop.")

    for voice in voices:
        play_voice(voice)
        input("Press ENTER for next voice...")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
