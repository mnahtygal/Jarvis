#!/usr/bin/env bash
set -euo pipefail

MODEL_KEY="${1:-}"
CONFIG="$HOME/jarvis/config/models.json"
ACTIVE="$HOME/jarvis/config/active_model"
SERVICE="jarvis-llama.service"

if [[ -z "$MODEL_KEY" ]]; then
  echo "Usage: ./scripts/switch_model.sh qwen3|deepseek|qwen25coder"
  exit 1
fi

VALID=$(python3 - <<PY
import json
from pathlib import Path
cfg=json.loads(Path('$CONFIG').read_text())
print('yes' if '$MODEL_KEY' in cfg['models'] else 'no')
PY
)

if [[ "$VALID" != "yes" ]]; then
  echo "Invalid model: $MODEL_KEY"
  exit 1
fi

echo "$MODEL_KEY" > "$ACTIVE"

echo "Stopping service..."
sudo systemctl stop "$SERVICE"
sleep 2

echo "Checking port 8080..."
if ss -ltn | grep -q ':8080 '; then
  echo "Port 8080 still busy"
  exit 1
fi

echo "Starting service..."
sudo systemctl start "$SERVICE"

for i in {1..20}; do
  if curl -s http://127.0.0.1:8080/health >/dev/null 2>&1; then
    echo "Model switched successfully"
    curl -s http://127.0.0.1:8080/v1/models
    exit 0
  fi
  sleep 3
done

echo "Service failed health check"
exit 1
