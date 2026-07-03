#!/usr/bin/env bash
set -euo pipefail

JARVIS_HOME="$HOME/jarvis"
LLAMA_HOME="$HOME/llama.cpp"
MODEL_HOME="$HOME/models"

start_if_free () {
  port="$1"; name="$2"; shift 2
  if ss -ltn | grep -q ":${port} "; then
    echo "✓ ${name} already running"
  else
    echo "→ Starting ${name}"
    nohup "$@" >/tmp/${name}.log 2>&1 &
    sleep 2
  fi
}

start_if_free 8080 Qwen3 "$LLAMA_HOME/build/bin/llama-server" -m "$MODEL_HOME/qwen3-30b/qwen3-30b.gguf" --host 127.0.0.1 --port 8080 -ngl auto -t 14

start_if_free 8081 GemmaVision "$LLAMA_HOME/build/bin/llama-server" -m "$MODEL_HOME/gemma-3-4b-vision/gemma-3-4b-it.gguf" --host 127.0.0.1 --port 8081 -ngl auto -t 8

if ! ss -ltn | grep -q ":5000 "; then
 bash -lc 'cd "$HOME/jarvis"; source .venv/bin/activate; nohup python api.py >/tmp/jarvis_api.log 2>&1 &'
fi

if ! ss -ltn | grep -q ":5173 "; then
 bash -lc 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; cd "$HOME/jarvis/ui-app"; nvm use >/dev/null 2>&1 || true; nohup npm run dev -- --host 0.0.0.0 >/tmp/jarvis_ui.log 2>&1 &'
fi

echo
echo "Jarvis started."
echo "UI      : http://localhost:5173"
echo "API     : http://localhost:5000"
echo "Text LLM: http://127.0.0.1:8080"
echo "Vision  : http://127.0.0.1:8081"
echo "Logs are in /tmp"
