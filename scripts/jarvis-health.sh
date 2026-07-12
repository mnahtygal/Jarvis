#!/usr/bin/env bash

check_url() {
  NAME="$1"
  URL="$2"

  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "✓ $NAME online - $URL"
    return 0
  else
    echo "✗ $NAME offline - $URL"
    return 1
  fi
}

source "$HOME/jarvis/scripts/jarvis-service-common.sh"

echo "============================================================"
echo "SYSTEM STATUS"
echo "============================================================"
echo "Time: $(date)"
echo

if check_url "Jarvis API    " "http://127.0.0.1:5000/health"; then
  mapfile -t pids < <(api_pids)
  if ((${#pids[@]} == 1)); then
    echo "  PID ${pids[0]} | age $(ps -o etime= -p "${pids[0]}" | xargs) | log $API_LOG"
  else
    echo "  Process mismatch: expected one Jarvis API, found ${#pids[@]} | log $API_LOG"
  fi
else
  echo "  Log: $API_LOG"
fi
check_url "Jarvis UI     " "http://localhost:5173" || echo "  Log: $UI_LOG"
check_url "Text LLM      " "http://127.0.0.1:8080/health" || echo "  Log: /tmp/Qwen3.log"
check_url "Vision LLM    " "http://127.0.0.1:8081/health" || echo "  Log: /tmp/GemmaVision.log"

echo
echo "Processes:"
echo "LLM servers:"
pgrep -af "llama-server" || echo "No llama-server found"

echo
echo "Jarvis UI:"
pgrep -af "npm run dev|vite --host|node .*vite" || echo "No UI process found"

echo
echo "VS Code:"
pgrep -af "^/usr/share/code/code .* /home/mnahtygal/jarvis|code /home/mnahtygal/jarvis" || echo "VS Code not detected"
echo
echo "============================================================"
