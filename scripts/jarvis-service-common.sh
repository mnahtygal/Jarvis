#!/usr/bin/env bash

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
API_PYTHON="$JARVIS_HOME/.venv/bin/python"
API_SCRIPT="$JARVIS_HOME/api.py"
API_ENTRY="/usr/libexec/jarvis-api-entry"
API_PID_FILE="/tmp/jarvis-api.pid"
UI_PID_FILE="/tmp/jarvis-ui.pid"
API_LOG="/tmp/jarvis-api.log"
UI_LOG="/tmp/jarvis_ui.log"

pid_matches_api() {
  local pid="${1:-}" cwd process_executable expected_executable argument script_path
  local -a cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  mapfile -d '' -t cmdline <"/proc/$pid/cmdline"
  cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)
  process_executable=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)
  expected_executable=$(readlink -f "$API_PYTHON" 2>/dev/null || true)
  [[ "$cwd" == "$JARVIS_HOME" && "$process_executable" == "$expected_executable" ]] || return 1
  for argument in "${cmdline[@]:1}"; do
    [[ "$argument" == -* ]] && continue
    if [[ "$argument" == /* ]]; then
      script_path=$(readlink -f "$argument" 2>/dev/null || true)
    else
      script_path=$(readlink -f "$cwd/$argument" 2>/dev/null || true)
    fi
    [[ "$script_path" == "$API_SCRIPT" ]] && return 0
  done
  return 1
}

api_pids() {
  local proc pid
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    pid_matches_api "$pid" && echo "$pid"
  done
}

ui_pids() {
  local proc pid cwd executable script
  local -a cmdline
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    [[ -r "$proc/cmdline" ]] || continue
    cwd=$(readlink "$proc/cwd" 2>/dev/null || true)
    [[ "$cwd" == "$JARVIS_HOME/ui-app" ]] || continue
    mapfile -d '' -t cmdline <"$proc/cmdline"
    executable="${cmdline[0]:-}"
    script="${cmdline[1]:-}"
    if [[ "${executable##*/}" =~ ^node(js)?$ ]] \
      && [[ "$script" == "$JARVIS_HOME/ui-app/node_modules/.bin/vite" \
        || "$script" == "./node_modules/.bin/vite" \
        || "$script" == "$JARVIS_HOME/ui-app/node_modules/vite/bin/vite.js" ]]; then
      echo "$pid"
    fi
  done
}

pid_matches_ui() {
  local expected="${1:-}" pid
  [[ "$expected" =~ ^[0-9]+$ ]] || return 1
  while IFS= read -r pid; do
    [[ "$pid" == "$expected" ]] && return 0
  done < <(ui_pids)
  return 1
}

listener_pids_for_port() {
  local port="$1" details matched_pid
  while IFS= read -r details; do
    while [[ "$details" =~ pid=([0-9]+) ]]; do
      matched_pid="${BASH_REMATCH[1]}"
      printf '%s\n' "$matched_pid"
      details="${details#*pid=$matched_pid}"
    done
  done < <(ss -H -ltnp "sport = :$port" 2>/dev/null)
}

pid_listens_on_port() {
  local expected="${1:-}" port="${2:-}" pid
  [[ "$expected" =~ ^[0-9]+$ && "$port" =~ ^[0-9]+$ ]] || return 1
  while IFS= read -r pid; do
    [[ "$pid" == "$expected" ]] && return 0
  done < <(listener_pids_for_port "$port")
  return 1
}

pid_matches_model() {
  local pid="${1:-}" executable="${2:-}" model="${3:-}" port="${4:-}" profile_flag="${5:-}"
  local index has_model=0 has_port=0 has_profile=0 process_executable expected_executable
  local -a cmdline
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
  mapfile -d '' -t cmdline <"/proc/$pid/cmdline"
  process_executable=$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)
  expected_executable=$(readlink -f "$executable" 2>/dev/null || true)
  [[ -n "$process_executable" && "$process_executable" == "$expected_executable" ]] || return 1
  for ((index = 1; index < ${#cmdline[@]} - 1; index++)); do
    [[ "${cmdline[index]}" == "-m" && "${cmdline[index + 1]}" == "$model" ]] && has_model=1
    [[ "${cmdline[index]}" == "--port" && "${cmdline[index + 1]}" == "$port" ]] && has_port=1
    [[ -n "$profile_flag" && "${cmdline[index]}" == "$profile_flag" ]] && has_profile=1
  done
  [[ -n "$profile_flag" && "${cmdline[-1]:-}" == "$profile_flag" ]] && has_profile=1
  ((has_port && (has_model || has_profile)))
}

port_is_listening() {
  local port="$1"
  ss -H -ltn "sport = :$port" 2>/dev/null | grep -q .
}

wait_for_url() {
  local url="$1" attempts="${2:-30}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    curl -m 2 -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

stop_pid_gracefully() {
  local pid="$1" label="$2"
  local attempt
  kill -TERM "$pid" 2>/dev/null || return 0
  for ((attempt = 1; attempt <= 10; attempt++)); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.5
  done
  echo "! $label PID $pid did not stop after SIGTERM; sending SIGKILL"
  kill -KILL "$pid" 2>/dev/null || true
}
