#!/usr/bin/env bash
set -o pipefail

LOG="$HOME/jarvis/logs/boot-v3.log"
JARVIS_VERSION="0.2.0"

line() {
  echo "============================================================"
}

boot_msg() {
  echo "[$(date '+%H:%M:%S')] $1"
}

check_url() {
  local NAME="$1"
  local URL="$2"

  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "✓ $NAME"
    return 0
  else
    echo "✗ $NAME"
    return 1
  fi
}

wait_for_url() {
  local NAME="$1"
  local URL="$2"
  local MAX="${3:-30}"

  boot_msg "Waiting for $NAME..."

  for i in $(seq 1 "$MAX"); do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      boot_msg "✓ $NAME ready"
      return 0
    fi
    sleep 2
  done

  boot_msg "⚠ $NAME did not respond"
  return 1
}

{
clear
line
echo "              THOR AI WORKSTATION"
echo "                 JARVIS v$JARVIS_VERSION"
line
echo
boot_msg "Good morning Marty."
boot_msg "Boot date: $(date)"
echo

boot_msg "Initializing AI Core..."
sleep 1

echo
boot_msg "Starting Jarvis services..."
bash "$HOME/jarvis/scripts/start-jarvis.sh" || exit 1

echo
boot_msg "Running service checks..."
wait_for_url "Jarvis API" "http://127.0.0.1:5000/health" 30 || exit 1
wait_for_url "Jarvis UI" "http://localhost:5173" 30

echo
line
echo "SYSTEM STATUS"
line

check_url "Jarvis API     http://localhost:5000" "http://127.0.0.1:5000/health"
check_url "Jarvis UI      http://localhost:5173" "http://localhost:5173"
check_url "Text LLM       http://127.0.0.1:8080" "http://127.0.0.1:8080"
check_url "Vision LLM     http://127.0.0.1:8081" "http://127.0.0.1:8081"

echo
line
echo "RUNNING MODELS"
line
pgrep -af "llama-server" || echo "No llama-server processes found"

echo
line
echo "SYSTEM RESOURCES"
line
echo "Uptime : $(uptime -p)"
echo "Memory : $(free -h | awk '/Mem:/ {print $3 " used / " $2 " total"}')"
echo "Disk   : $(df -h "$HOME" | awk 'NR==2 {print $3 " used / " $2 " total (" $5 ")"}')"

echo
line
boot_msg "Opening workspace..."

if ! pgrep -f "code.*$HOME/jarvis" >/dev/null 2>&1; then
  code "$HOME/jarvis" >/dev/null 2>&1 &
  boot_msg "✓ VS Code opened"
else
  boot_msg "✓ VS Code already running"
fi

sleep 3

boot_msg "Firefox launch skipped - session restore handles pinned tabs"

echo
line
boot_msg "JARVIS BOOT COMPLETE"
boot_msg "Welcome back Marty."
line
echo

} | tee -a "$LOG"
