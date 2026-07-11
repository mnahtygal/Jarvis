#!/usr/bin/env bash

ui="offline"
api="offline"
text_llm="offline"
vision_llm="offline"

curl -fsS http://localhost:5173 >/dev/null 2>&1 && ui="online"
curl -fsS http://localhost:5000 >/dev/null 2>&1 && api="online"
curl -fsS http://127.0.0.1:8080 >/dev/null 2>&1 && text_llm="online"
curl -fsS http://127.0.0.1:8081 >/dev/null 2>&1 && vision_llm="online"

cat <<JSON
{
  "time": "$(date)",
  "uptime": "$(uptime -p)",
  "memory": "$(free -h | awk '/Mem:/ {print $3 " used / " $2 " total"}')",
  "disk": "$(df -h "$HOME" | awk 'NR==2 {print $3 " used / " $2 " total (" $5 ")"}')",
  "ui": "$ui",
  "api": "$api",
  "text_llm": "$text_llm",
  "vision_llm": "$vision_llm"
}
JSON
