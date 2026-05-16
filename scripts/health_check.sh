#!/usr/bin/env bash
set -e

cd "$HOME/jarvis"

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

python3 tools/health_check.py
