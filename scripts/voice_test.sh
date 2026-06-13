#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
SECONDS_TO_RECORD="${1:-7}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Jarvis virtual environment python not found: $VENV_PYTHON"
  exit 1
fi

if ! [[ "$SECONDS_TO_RECORD" =~ ^[0-9]+$ ]] || [[ "$SECONDS_TO_RECORD" -lt 1 ]]; then
  echo "Usage: ./scripts/voice_test.sh [seconds]"
  exit 1
fi

cd "$ROOT_DIR"

echo "==================================="
echo " Jarvis Voice Test"
echo "==================================="
echo "Listen window: ${SECONDS_TO_RECORD} second(s)"
echo "Say a full sentence after recording starts."
echo

"$VENV_PYTHON" audio/listen.py "$SECONDS_TO_RECORD"
