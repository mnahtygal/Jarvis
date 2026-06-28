#!/usr/bin/env bash
set -u

API_BASE="${JARVIS_API_BASE:-http://127.0.0.1:5000}"
BRAIN_BASE="${JARVIS_BRAIN_BASE:-http://127.0.0.1:8080}"
VISION_BASE="${JARVIS_VISION_BASE:-http://127.0.0.1:8081}"
FAILURES=0

pass() {
  echo "[pass] $1"
}

fail() {
  echo "[fail] $1"
  FAILURES=$((FAILURES + 1))
}

check_http() {
  local label="$1"
  local url="$2"

  if curl -m 5 -fsS "$url" >/dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_json_ok() {
  local label="$1"
  local url="$2"
  local payload="${3:-{}}"
  local response

  response=$(curl -m 180 -fsS -X POST "$url" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>/dev/null)

  if echo "$response" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("ok") else 1)' 2>/dev/null; then
    pass "$label"
  else
    fail "$label"
    echo "$response"
  fi
}

echo "=== Jarvis smoke test ==="
check_http "Qwen brain health" "${BRAIN_BASE}/health"
check_http "Gemma vision health" "${VISION_BASE}/health"
check_http "Flask API health" "${API_BASE}/health"
check_http "Dashboard API" "${API_BASE}/api/status/dashboard"

check_json_ok "Camera snapshot" "${API_BASE}/api/camera/snapshot"
check_json_ok "Vision analyze latest snapshot" "${API_BASE}/api/camera/analyze"

TEXT_RESPONSE=$(curl -m 60 -fsS -X POST "${API_BASE}/text" \
  -H "Content-Type: application/json" \
  -d '{"command":"brain status","use_voice":false}' 2>/dev/null)

if echo "$TEXT_RESPONSE" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("response") else 1)' 2>/dev/null; then
  pass "Text command"
else
  fail "Text command"
  echo "$TEXT_RESPONSE"
fi

echo
if [[ "$FAILURES" -eq 0 ]]; then
  echo "Jarvis smoke test passed."
  exit 0
fi

echo "Jarvis smoke test failed with ${FAILURES} failure(s)."
exit 1
