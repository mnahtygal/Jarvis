#!/usr/bin/env bash
set -e

cd "$HOME/jarvis"

if [ ! -d ".venv" ]; then
  echo "[JARVIS] ERROR: .venv not found at $HOME/jarvis/.venv"
  exit 1
fi

source .venv/bin/activate

echo "[JARVIS] Starting Jarvis CLI..."
python3 testbrain.py
