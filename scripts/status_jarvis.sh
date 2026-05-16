#!/usr/bin/env bash

echo "=============================="
echo " Jarvis Thor Status"
echo "=============================="

echo
echo "[SYSTEM]"
hostnamectl | grep -E "Static hostname|Operating System|Kernel|Architecture|Hardware Model" || true

echo
echo "[CUDA]"
nvcc --version | tail -n 1 || echo "nvcc not found"

echo
echo "[GPU]"
nvidia-smi || true

echo
echo "[POSTGRES]"
systemctl is-active postgresql || true

echo
echo "[LLAMA SERVER]"
if curl -s http://127.0.0.1:8080/v1/models >/tmp/jarvis_models.json; then
  echo "llama.cpp server: ONLINE"
  cat /tmp/jarvis_models.json
  echo
else
  echo "llama.cpp server: OFFLINE"
fi

echo
echo "[JARVIS REPO]"
cd "$HOME/jarvis" && git status --short

echo
echo "[MODEL FILES]"
find "$HOME/models" -iname "*.gguf" 2>/dev/null

echo
echo "=============================="
