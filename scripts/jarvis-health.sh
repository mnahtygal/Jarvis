#!/usr/bin/env bash

check_url() {
  NAME="$1"
  URL="$2"

  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "✓ $NAME online - $URL"
    return 0
  else
    echo "✗ $NAME offline - $URL"
    return 1
  fi
}

echo "========================================"
echo "      JARVIS HEALTH CHECK"
echo "========================================"
echo "Time: $(date)"
echo

check_url "Jarvis UI" "http://localhost:5173"

echo
echo "Processes:"
echo "LLM servers:"
pgrep -af "llama-server" || echo "No llama-server found"

echo
echo "Jarvis UI:"
pgrep -af "npm run dev|vite --host|node .*vite" || echo "No UI process found"

echo
echo "VS Code:"
pgrep -af "^/usr/share/code/code .* /home/mnahtygal/jarvis|code /home/mnahtygal/jarvis" || echo "VS Code not detected"
echo
echo "========================================"
