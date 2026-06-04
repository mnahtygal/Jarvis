#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

echo "==================================="
echo " Jarvis Combined Regression Check"
echo "==================================="
echo

echo "[1/2] Running context regression..."
python tools/regression_test_context.py

echo
echo "[2/2] Running brain regression..."
python tools/regression_test_brain.py

echo
echo "==================================="
echo " Combined regression check passed"
echo "==================================="
