#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Jarvis virtual environment python not found: $VENV_PYTHON"
  echo "Run this from the Jarvis machine after creating the .venv."
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/ask_jarvis.sh \"what model are you using\""
  exit 1
fi

QUESTION="$*"

cd "$ROOT_DIR"
"$VENV_PYTHON" -c "from core.brain import think; print(think('$QUESTION'))"
