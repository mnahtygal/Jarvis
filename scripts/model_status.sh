#!/usr/bin/env bash
set -e

echo "=== Active Model File ==="
cat "$HOME/jarvis/config/active_model"

echo
echo "=== Runtime Model ==="
curl -s http://127.0.0.1:8080/v1/models | python3 -m json.tool || true

echo
echo "=== Service ==="
systemctl status jarvis-llama.service --no-pager -n 5
