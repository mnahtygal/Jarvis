#!/usr/bin/env bash
set -euo pipefail

LLAMA_CPP_DIR="$HOME/llama.cpp"
CONFIG_DIR="$HOME/jarvis/config"
MODEL_CONFIG="$CONFIG_DIR/models.json"
ACTIVE_MODEL_FILE="$CONFIG_DIR/active_model"
HOST="0.0.0.0"
PORT="8080"

ACTIVE_KEY="qwen3"

if [[ -f "$ACTIVE_MODEL_FILE" ]]; then
  ACTIVE_KEY="$(tr -d '[:space:]' < "$ACTIVE_MODEL_FILE")"
fi

MODEL_PATH=$(python3 - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path.home().joinpath('jarvis/config/models.json').read_text())
key = Path.home().joinpath('jarvis/config/active_model').read_text().strip()
if not key:
    key = cfg['default_model']
print(cfg['models'][key]['path'])
PY
)

cd "$LLAMA_CPP_DIR"

echo "[JARVIS] Starting llama.cpp server..."
echo "[JARVIS] Active model key: $ACTIVE_KEY"
echo "[JARVIS] Model: $MODEL_PATH"
echo "[JARVIS] Endpoint: http://$HOST:$PORT"

exec ./build/bin/llama-server \
  -m "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  -ngl 999 \
  -t "$(nproc)" \
  --jinja \
  --reasoning-format none
