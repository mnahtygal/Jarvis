#!/usr/bin/env bash
set -euo pipefail

MODEL_KEY="${1:-}"
CONFIG="$HOME/jarvis/config/models.json"
ACTIVE="$HOME/jarvis/config/active_model"
SERVICE="jarvis-llama.service"
MODELS_URL="http://127.0.0.1:8080/v1/models"
HEALTH_URL="http://127.0.0.1:8080/health"
MAX_ATTEMPTS=40
SLEEP_SECONDS=3

usage() {
  echo "Usage: ./scripts/switch_model.sh qwen3|deepseek|qwen25coder"
}

if [[ -z "$MODEL_KEY" ]]; then
  usage
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "Model config not found: $CONFIG"
  exit 1
fi

if [[ ! -f "$ACTIVE" ]]; then
  echo "Active model file not found: $ACTIVE"
  exit 1
fi

readarray -t MODEL_INFO < <(
  python3 - <<PY
import json
from pathlib import Path

config_path = Path("$CONFIG")
model_key = "$MODEL_KEY"
config = json.loads(config_path.read_text())
model = config.get("models", {}).get(model_key)

if not model:
    raise SystemExit(1)

print(model.get("model_id", ""))
print(model.get("display_name", model_key))
print(model.get("path", ""))
PY
)

if [[ ${#MODEL_INFO[@]} -lt 3 ]]; then
  echo "Invalid model: $MODEL_KEY"
  usage
  exit 1
fi

EXPECTED_MODEL_ID="${MODEL_INFO[0]}"
DISPLAY_NAME="${MODEL_INFO[1]}"
MODEL_PATH="${MODEL_INFO[2]}"
PREVIOUS_MODEL_KEY="$(tr -d '[:space:]' < "$ACTIVE")"

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Model file not found: $MODEL_PATH"
  exit 1
fi

wait_for_expected_model() {
  local attempt
  local runtime_model

  for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    runtime_model="$(
      curl -s "$MODELS_URL" 2>/dev/null |
        python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)

models = data.get("data", [])
print(models[0].get("id", "") if models else "")
' 2>/dev/null || true
    )"

    if [[ "$runtime_model" == "$EXPECTED_MODEL_ID" ]]; then
      echo "Model switched successfully"
      echo "Active model: $DISPLAY_NAME"
      echo "Runtime model ID: $runtime_model"
      return 0
    fi

    if (( attempt == 1 || attempt % 5 == 0 )); then
      echo "Waiting for model load ($attempt/$MAX_ATTEMPTS)..."
    fi

    sleep "$SLEEP_SECONDS"
  done

  return 1
}

rollback_previous_model() {
  if [[ -z "$PREVIOUS_MODEL_KEY" || "$PREVIOUS_MODEL_KEY" == "$MODEL_KEY" ]]; then
    return 0
  fi

  echo "Attempting rollback to previous model: $PREVIOUS_MODEL_KEY"
  echo "$PREVIOUS_MODEL_KEY" > "$ACTIVE"
  sudo systemctl restart "$SERVICE" || true
}

echo "Requested model: $MODEL_KEY ($DISPLAY_NAME)"
echo "Expected model ID: $EXPECTED_MODEL_ID"
echo "$MODEL_KEY" > "$ACTIVE"

echo "Stopping service..."
sudo systemctl stop "$SERVICE"
sleep 2

echo "Checking port 8080..."
if ss -ltn | grep -q ':8080 '; then
  echo "Port 8080 is still busy. Another process may be using it."
  echo "Active model file remains set to: $MODEL_KEY"
  exit 1
fi

echo "Starting service..."
sudo systemctl start "$SERVICE"

if wait_for_expected_model; then
  echo
  curl -s "$HEALTH_URL" || true
  echo
  exit 0
fi

echo "Model failed to become ready within $((MAX_ATTEMPTS * SLEEP_SECONDS)) seconds."
rollback_previous_model
exit 1
