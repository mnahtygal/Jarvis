#!/usr/bin/env bash
set -euo pipefail

JARVIS_HOME="$HOME/jarvis"
LLAMA_HOME="$HOME/llama.cpp"
MODEL_HOME="$HOME/models"
source "$JARVIS_HOME/scripts/jarvis-service-common.sh"

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

mapfile -t current_api_pids < <(api_pids)
if ((${#current_api_pids[@]} > 1)); then
  echo "✗ Multiple Jarvis API processes found: ${current_api_pids[*]}" >&2
  exit 1
elif ((${#current_api_pids[@]} == 1)); then
  printf '%s\n' "${current_api_pids[0]}" >"$API_PID_FILE"
  echo "✓ Jarvis API already running (PID ${current_api_pids[0]})"
elif port_is_listening 5000; then
  echo "✗ Port 5000 is occupied by a process other than the Jarvis API" >&2
  exit 1
else
  [[ -x "$API_PYTHON" ]] || { echo "✗ Missing API interpreter: $API_PYTHON" >&2; exit 1; }
  echo "→ Starting Jarvis API"
  cd "$JARVIS_HOME"
  nohup "$API_PYTHON" "$API_SCRIPT" >"$API_LOG" 2>&1 &
  api_pid=$!
  printf '%s\n' "$api_pid" >"$API_PID_FILE"
fi

if ! wait_for_url "http://127.0.0.1:5000/health" 30; then
  echo "✗ Jarvis API did not become ready; inspect $API_LOG" >&2
  exit 1
fi
echo "✓ Jarvis API ready (PID $(<"$API_PID_FILE"))"
if curl -m 3 -fsS "http://127.0.0.1:5000/api/cameras" >/dev/null 2>&1; then
  echo "✓ Camera API route available"
else
  echo "! Camera API route check failed; API health remains ready"
fi

if ! ss -ltn | grep -q ":5173 "; then
 bash -lc 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; cd "$HOME/jarvis/ui-app"; nvm use >/dev/null 2>&1 || true; nohup npm run dev -- --host 0.0.0.0 >/tmp/jarvis_ui.log 2>&1 & echo $! >/tmp/jarvis-ui.pid'
fi

echo
echo "Jarvis started and API readiness passed."
echo "UI      : http://localhost:5173"
echo "API     : http://localhost:5000"
echo "Text LLM: http://127.0.0.1:8080"
echo "Vision  : http://127.0.0.1:8081"
echo "Logs are in /tmp"
