#!/usr/bin/env bash

echo "[JARVIS] Stopping llama.cpp server on port 8080..."

PIDS=$(pgrep -f "llama-server.*8080" || true)

if [ -z "$PIDS" ]; then
  echo "[JARVIS] No llama.cpp server found."
  exit 0
fi

echo "$PIDS" | xargs kill
echo "[JARVIS] Stop signal sent."
