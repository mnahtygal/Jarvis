#!/usr/bin/env bash

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
API_PYTHON="$JARVIS_HOME/.venv/bin/python"
API_SCRIPT="$JARVIS_HOME/api.py"
API_PID_FILE="/tmp/jarvis-api.pid"
UI_PID_FILE="/tmp/jarvis-ui.pid"
API_LOG="/tmp/jarvis-api.log"
UI_LOG="/tmp/jarvis_ui.log"

pid_matches_api() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  mapfile -d '' -t cmdline <"/proc/$pid/cmdline"
  [[ "${cmdline[0]:-}" == "$API_PYTHON" && "${cmdline[1]:-}" == "$API_SCRIPT" ]]
}

api_pids() {
  local proc pid
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    pid_matches_api "$pid" && echo "$pid"
  done
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
