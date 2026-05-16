#!/usr/bin/env bash
set -e

LLAMA_CPP_DIR="$HOME/llama.cpp"
MODEL_PATH="$HOME/models/qwen3-30b/Qwen3-30B-A3B-Q4_K_M.gguf"
HOST="0.0.0.0"
PORT="8080"

cd "$LLAMA_CPP_DIR"

echo "[JARVIS] Starting llama.cpp server..."
echo "[JARVIS] Model: $MODEL_PATH"
echo "[JARVIS] Endpoint: http://$HOST:$PORT"

exec ./build/bin/llama-server \
  -m "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  -ngl 999 \
  -t "$(nproc)" \
  --jinja \
  --reasoning-format none
