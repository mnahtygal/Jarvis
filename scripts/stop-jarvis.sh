#!/usr/bin/env bash
set -u

JARVIS_HOME="$HOME/jarvis"
source "$JARVIS_HOME/scripts/jarvis-service-common.sh"

echo "Stopping Jarvis API..."
mapfile -t pids < <(api_pids)
if ((${#pids[@]} == 0)); then
  echo "Jarvis API is not running."
else
  for pid in "${pids[@]}"; do
    stop_pid_gracefully "$pid" "Jarvis API"
  done
fi
rm -f "$API_PID_FILE"

for attempt in {1..10}; do
  port_is_listening 5000 || break
  sleep 0.5
done
if port_is_listening 5000; then
  echo "✗ Port 5000 is still in use after stopping the Jarvis API" >&2
  exit 1
fi

echo "Stopping Jarvis UI..."
if [[ -r "$UI_PID_FILE" ]]; then
  ui_pid=$(<"$UI_PID_FILE")
  [[ "$ui_pid" =~ ^[0-9]+$ ]] && stop_pid_gracefully "$ui_pid" "Jarvis UI"
fi
pkill -TERM -f "$JARVIS_HOME/ui-app/node_modules/.bin/vite" 2>/dev/null || true
rm -f "$UI_PID_FILE"

echo "Jarvis API and UI stopped."
echo "Leaving llama servers alone."
