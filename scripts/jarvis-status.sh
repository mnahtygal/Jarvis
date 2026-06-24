#!/usr/bin/env bash
set -u

print_header() {
  echo
  echo "=== $1 ==="
}

check_service() {
  local service_name="$1"
  local label="$2"

  if systemctl is-active --quiet "$service_name"; then
    echo "[ok]      $label ($service_name)"
  else
    echo "[offline] $label ($service_name)"
  fi
}

check_http() {
  local url="$1"
  local label="$2"

  if curl -m 3 -fsS "$url" >/dev/null 2>&1; then
    echo "[ok]      $label $url"
  else
    echo "[offline] $label $url"
  fi
}

print_header "Jarvis services"
check_service "jarvis-llama.service" "Qwen brain"
check_service "jarvis-vision.service" "Gemma vision"
check_service "jarvis-api.service" "Flask API"

print_header "Jarvis health endpoints"
check_http "http://127.0.0.1:8080/health" "Qwen brain"
check_http "http://127.0.0.1:8081/health" "Gemma vision"
check_http "http://127.0.0.1:5000/health" "Flask API"
check_http "http://127.0.0.1:5000/api/status/dashboard" "Dashboard API"

print_header "Ports"
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -E ':(8080|8081|5000|5173|5174)\b' || echo "No Jarvis ports found listening."
else
  echo "ss command not found."
fi

print_header "Git"
cd /home/mnahtygal/jarvis 2>/dev/null && git status --short --branch || echo "Could not read /home/mnahtygal/jarvis git status."
