#!/usr/bin/env bash
set -euo pipefail

JARVIS_HOME="$HOME/jarvis"
LLAMA_HOME="$HOME/llama.cpp"
MODEL_HOME="$HOME/models"
LLAMA_SERVER="$LLAMA_HOME/build/bin/llama-server"
TEXT_MODEL="$MODEL_HOME/qwen3-30b/Qwen3-30B-A3B-Q4_K_M.gguf"
VISION_MODEL="$MODEL_HOME/gemma-3-4b-vision/gemma-3-4b-it.gguf"
source "$JARVIS_HOME/scripts/jarvis-service-common.sh"

start_model_if_needed () {
  local port="$1" name="$2" health_url="$3" model="$4" profile_flag="$5" listener_pid started_pid
  local -a listener_pids
  shift 5
  if port_is_listening "$port"; then
    mapfile -t listener_pids < <(listener_pids_for_port "$port")
    if ((${#listener_pids[@]} != 1)) \
      || ! pid_matches_model "${listener_pids[0]:-}" "$LLAMA_SERVER" "$model" "$port" "$profile_flag"; then
      echo "✗ Port ${port} is occupied by a process other than the configured ${name}" >&2
      return 1
    fi
    listener_pid="${listener_pids[0]}"
    wait_for_url "$health_url" 180 || {
      echo "✗ Configured ${name} PID ${listener_pid} is listening but not healthy" >&2
      return 1
    }
    echo "✓ ${name} already running and ready (PID ${listener_pid})"
    return 0
  else
    echo "→ Starting ${name}"
    nohup "$@" >/tmp/${name}.log 2>&1 &
    started_pid=$!
  fi

  if ! wait_for_url "$health_url" 180; then
    echo "✗ ${name} did not become ready; inspect /tmp/${name}.log" >&2
    return 1
  fi
  if ! pid_matches_model "$started_pid" "$LLAMA_SERVER" "$model" "$port" "$profile_flag" \
    || ! pid_listens_on_port "$started_pid" "$port"; then
    echo "✗ ${name} health responded, but the expected process does not own port ${port}" >&2
    return 1
  fi
  echo "✓ ${name} ready (PID ${started_pid})"
}

[[ -x "$LLAMA_SERVER" ]] || {
  echo "✗ Missing llama-server: $LLAMA_SERVER" >&2
  exit 1
}
[[ -f "$TEXT_MODEL" ]] || {
  echo "✗ Missing text model: $TEXT_MODEL" >&2
  exit 1
}

start_model_if_needed 8080 Qwen3 http://127.0.0.1:8080/health "$TEXT_MODEL" "" "$LLAMA_SERVER" -m "$TEXT_MODEL" --host 127.0.0.1 --port 8080 -ngl auto -t 14

if port_is_listening 8081; then
  start_model_if_needed 8081 GemmaVision http://127.0.0.1:8081/health "$VISION_MODEL" "--vision-gemma-4b-default" "$LLAMA_SERVER" -m "$VISION_MODEL" --host 127.0.0.1 --port 8081 -ngl auto -t 8
elif [[ -f "$VISION_MODEL" ]]; then
  start_model_if_needed 8081 GemmaVision http://127.0.0.1:8081/health "$VISION_MODEL" "--vision-gemma-4b-default" "$LLAMA_SERVER" -m "$VISION_MODEL" --host 127.0.0.1 --port 8081 -ngl auto -t 8
else
  echo "! Vision model unavailable; continuing with text-only UI: $VISION_MODEL"
fi

mapfile -t current_api_pids < <(api_pids)
if ((${#current_api_pids[@]} > 1)); then
  echo "✗ Multiple Jarvis API processes found: ${current_api_pids[*]}" >&2
  exit 1
elif ((${#current_api_pids[@]} == 1)); then
  pid_listens_on_port "${current_api_pids[0]}" 5000 || {
    echo "✗ Jarvis API PID ${current_api_pids[0]} does not own port 5000" >&2
    exit 1
  }
  printf '%s\n' "${current_api_pids[0]}" >"$API_PID_FILE"
  echo "✓ Jarvis API already running (PID ${current_api_pids[0]})"
elif port_is_listening 5000; then
  echo "✗ Port 5000 is occupied by a process other than the Jarvis API" >&2
  exit 1
else
  echo "→ Starting Jarvis API"
  cd "$JARVIS_HOME"
  if [[ -x "$API_ENTRY" ]]; then
    nohup "$API_ENTRY" >"$API_LOG" 2>&1 &
  else
    [[ -x "$API_PYTHON" ]] || { echo "✗ Missing API interpreter: $API_PYTHON" >&2; exit 1; }
    nohup "$API_PYTHON" "$API_SCRIPT" >"$API_LOG" 2>&1 &
  fi
  api_pid=$!
  printf '%s\n' "$api_pid" >"$API_PID_FILE"
fi

if ! wait_for_url "http://127.0.0.1:5000/health" 30; then
  echo "✗ Jarvis API did not become ready; inspect $API_LOG" >&2
  exit 1
fi
pid_matches_api "$(<"$API_PID_FILE")" && pid_listens_on_port "$(<"$API_PID_FILE")" 5000 || {
  echo "✗ API health responded, but the expected Jarvis API does not own port 5000" >&2
  exit 1
}
echo "✓ Jarvis API ready (PID $(<"$API_PID_FILE"))"
if curl -m 3 -fsS "http://127.0.0.1:5000/api/cameras" >/dev/null 2>&1; then
  echo "✓ Camera API route available"
else
  echo "! Camera API route check failed; API health remains ready"
fi

mapfile -t current_ui_pids < <(ui_pids)
if ((${#current_ui_pids[@]} > 1)); then
  echo "✗ Multiple Jarvis UI processes found: ${current_ui_pids[*]}" >&2
  exit 1
elif ((${#current_ui_pids[@]} == 1)); then
  pid_listens_on_port "${current_ui_pids[0]}" 5173 || {
    echo "✗ Jarvis UI PID ${current_ui_pids[0]} does not own port 5173" >&2
    exit 1
  }
  printf '%s\n' "${current_ui_pids[0]}" >"$UI_PID_FILE"
  echo "✓ Jarvis UI already running (PID ${current_ui_pids[0]})"
elif port_is_listening 5173; then
  echo "✗ Port 5173 is occupied by a process other than the Jarvis UI" >&2
  exit 1
else
  [[ -x "$JARVIS_HOME/ui-app/node_modules/.bin/vite" ]] || {
    echo "✗ Missing UI dependencies; run npm install in $JARVIS_HOME/ui-app" >&2
    exit 1
  }
  echo "→ Starting Jarvis UI"
  bash -lc 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; cd "$HOME/jarvis/ui-app"; nvm use >/dev/null 2>&1 || true; nohup ./node_modules/.bin/vite >/tmp/jarvis_ui.log 2>&1 & echo $! >/tmp/jarvis-ui.pid'
fi

if ! wait_for_url "http://127.0.0.1:5173" 30; then
  echo "✗ Jarvis UI did not become ready; inspect $UI_LOG" >&2
  exit 1
fi
pid_matches_ui "$(<"$UI_PID_FILE")" && pid_listens_on_port "$(<"$UI_PID_FILE")" 5173 || {
  echo "✗ UI health responded, but the expected Jarvis UI does not own port 5173" >&2
  exit 1
}
echo "✓ Jarvis UI ready (PID $(<"$UI_PID_FILE"))"

echo
echo "Jarvis started and readiness checks passed."
echo "UI      : http://localhost:5173"
echo "API     : http://localhost:5000"
echo "Text LLM: http://127.0.0.1:8080"
echo "Vision  : http://127.0.0.1:8081"
echo "Logs are in /tmp"
