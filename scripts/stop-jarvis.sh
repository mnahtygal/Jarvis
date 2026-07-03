#!/usr/bin/env bash

echo "Stopping Jarvis UI..."
pkill -f "vite --host" || true
pkill -f "npm run dev --host" || true

echo "Jarvis UI stopped."
echo "Leaving llama servers alone."
