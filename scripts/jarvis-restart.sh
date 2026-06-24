#!/usr/bin/env bash
set -euo pipefail

SERVICES=(
  "jarvis-llama.service"
  "jarvis-vision.service"
  "jarvis-api.service"
)

echo "Restarting Jarvis services..."
for service_name in "${SERVICES[@]}"; do
  echo "-> sudo systemctl restart ${service_name}"
  sudo systemctl restart "${service_name}"
done

echo
echo "Waiting for services to settle..."
sleep 5

if [[ -x /home/mnahtygal/jarvis/scripts/jarvis-status.sh ]]; then
  /home/mnahtygal/jarvis/scripts/jarvis-status.sh
else
  echo "jarvis-status.sh is not executable yet. Run: chmod +x scripts/jarvis-status.sh scripts/jarvis-restart.sh"
fi
