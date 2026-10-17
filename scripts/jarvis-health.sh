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
  if ((${#pids[@]} == 1)) && pid_listens_on_port "${pids[0]}" 5000; then
    echo "  PID ${pids[0]} | age $(ps -o etime= -p "${pids[0]}" | xargs) | log $API_LOG"
  else
    echo "  Process mismatch: port 5000 is not owned by exactly one Jarvis API | log $API_LOG"
  fi
else
  echo "  Log: $API_LOG"
fi
if check_url "Jarvis UI     " "http://localhost:5173"; then
  mapfile -t ui_processes < <(ui_pids)
  if ((${#ui_processes[@]} == 1)) && pid_listens_on_port "${ui_processes[0]}" 5173; then
    echo "  PID ${ui_processes[0]} | age $(ps -o etime= -p "${ui_processes[0]}" | xargs) | log $UI_LOG"
  else
    echo "  Process mismatch: port 5173 is not owned by exactly one Jarvis UI | log $UI_LOG"
  fi
else
  echo "  Log: $UI_LOG"
fi
check_url "Text LLM      " "http://127.0.0.1:8080/health" || echo "  Log: /tmp/Qwen3.log"
check_url "Vision LLM    " "http://127.0.0.1:8081/health" || echo "  Log: /tmp/GemmaVision.log"

echo
echo "Processes:"
echo "LLM servers:"
pgrep -af "llama-server" || echo "No llama-server found"

echo
echo "Jarvis UI:"
mapfile -t ui_processes < <(ui_pids)
if ((${#ui_processes[@]})); then
  printf 'PID %s\n' "${ui_processes[@]}"
else
  echo "No UI process found"
fi

echo
echo "VS Code:"
pgrep -af "^/usr/share/code/code .* /home/mnahtygal/jarvis|code /home/mnahtygal/jarvis" || echo "VS Code not detected"
echo
echo "============================================================"
