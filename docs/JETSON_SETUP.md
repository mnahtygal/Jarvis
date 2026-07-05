# Jetson Setup Notes

_Last updated: July 5, 2026_

This document captures the Jetson setup work completed during the July 2026 Jarvis / AI Lab buildout.

## Purpose

The Jetson is being used as the AI development sandbox and Open WebUI front end, while Thor remains the production Jarvis / llama.cpp host.

Current target architecture:

```text
Windows Laptop
    |
    v
Jetson AGX Xavier
    - NoMachine remote desktop
    - Open WebUI
    - Ollama
    - Small local models
    |
    v
Thor
    - Jarvis
    - Mission Control
    - llama.cpp
    - Qwen3-30B
```

## Hardware / OS baseline

Observed Jetson release:

```bash
cat /etc/nv_tegra_release
```

Result:

```text
# R35 (release), REVISION: 3.1, GCID: 32827747, BOARD: t186ref, EABI: aarch64, DATE: Sun Mar 19 15:19:21 UTC 2023
```

This corresponds to JetPack 5.x / Ubuntu 20.04 on ARM64.

```bash
uname -m
# aarch64
```

## Remote desktop

NoMachine was installed and used instead of XRDP.

XRDP created a tiny 592x440 desktop and was removed/disabled as the primary remote desktop path.

Useful checks:

```bash
sudo /usr/NX/bin/nxserver --status
ps -ef | grep -E "xrdp|vino|gnome-remote|nx|Xorg" | grep -v grep
```

Disable XRDP if it is running:

```bash
sudo systemctl stop xrdp xrdp-sesman
sudo systemctl disable xrdp xrdp-sesman
```

Disable Vino desktop sharing if it conflicts with NoMachine:

```bash
gsettings set org.gnome.Vino enabled false
gsettings set org.gnome.Vino prompt-enabled false
gsettings set org.gnome.Vino require-encryption false
mkdir -p ~/.config/autostart
cp /etc/xdg/autostart/vino-server.desktop ~/.config/autostart/ 2>/dev/null
echo "Hidden=true" >> ~/.config/autostart/vino-server.desktop
pkill vino-server
```

NoMachine server listens on port 4000.

## Python 3.11 with pyenv

The Jetson system Python was Python 3.8.10. Open WebUI required a newer Python, so Python 3.11.9 was installed using pyenv instead of replacing the system Python.

Install build dependencies:

```bash
sudo apt update
sudo apt install -y \
  build-essential curl git wget make \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libffi-dev liblzma-dev tk-dev \
  xz-utils uuid-dev libncursesw5-dev libgdbm-dev libnss3-dev
```

Install pyenv:

```bash
curl https://pyenv.run | bash
```

Add to `~/.bashrc`:

```bash
# pyenv
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

Reload shell and install Python:

```bash
source ~/.bashrc
pyenv install 3.11.9
pyenv global 3.11.9
python --version
```

Verify required modules:

```bash
python - <<'PY'
import bz2, readline, sqlite3, ssl
print("Python modules OK")
PY
```

## Open WebUI venv

Create and activate the venv:

```bash
cd ~/repos
python -m venv openwebui-venv
source openwebui-venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install open-webui
```

Open WebUI version tested:

```text
v0.10.2
```

## SQLite 3.53 workaround

Ubuntu 20.04 ships an older SQLite that is too old for ChromaDB. Open WebUI failed with an error similar to:

```text
RuntimeError: Your system has an unsupported version of sqlite3. Chroma requires sqlite3 >= 3.35.0.
```

Solution: build modern SQLite locally and compile `pysqlite3` inside the Open WebUI venv.

Build SQLite 3.53.3:

```bash
cd ~/repos
mkdir -p sqlite-build
cd sqlite-build
rm -rf sqlite-autoconf-* *.tar.gz

wget https://www.sqlite.org/2026/sqlite-autoconf-3530300.tar.gz
tar xzf sqlite-autoconf-3530300.tar.gz
cd sqlite-autoconf-3530300

./configure --prefix=$HOME/.local/sqlite353
make -j$(nproc)
make install
```

Build `pysqlite3` against the local SQLite:

```bash
cd ~/repos
source openwebui-venv/bin/activate

export LD_LIBRARY_PATH=$HOME/.local/sqlite353/lib:$LD_LIBRARY_PATH
export CFLAGS="-I$HOME/.local/sqlite353/include"
export LDFLAGS="-L$HOME/.local/sqlite353/lib"

pip uninstall -y pysqlite3 pysqlite3-binary
pip install --no-binary pysqlite3 pysqlite3
```

Test:

```bash
python - <<'PY'
import pysqlite3
print("pysqlite3 sqlite version:", pysqlite3.sqlite_version)
PY
```

Expected:

```text
3.53.3
```

## Running Open WebUI with pysqlite3 override

Because Chroma imports Python's `sqlite3`, start Open WebUI with `pysqlite3` injected first:

```bash
cd ~/repos
source openwebui-venv/bin/activate
export LD_LIBRARY_PATH=$HOME/.local/sqlite353/lib:$LD_LIBRARY_PATH

python - <<'PY'
import sys
import pysqlite3
sys.modules["sqlite3"] = pysqlite3

from open_webui import serve
serve()
PY
```

Open from another machine:

```text
http://10.0.0.42:8080
```

## Ollama on Jetson

Current local Ollama models observed:

```bash
ollama list
```

```text
qwen2.5-coder:7b
phi3:latest
qwen2.5-coder:3b
```

Ollama listens locally on:

```text
http://localhost:11434
```

Validate models directly before debugging Open WebUI:

```bash
ollama run phi3:latest
ollama run qwen2.5-coder:7b
```

## Open WebUI function calling setting

Open WebUI v0.10.2 showed buggy responses with default/native function calling:

- `qwen2.5-coder:7b` returned tool-call JSON or repeated `G` characters.
- `phi3:latest` returned `does not support tools`.

Fix in chat controls:

```text
Controls -> Advanced Params -> Function Calling -> Legacy
```

Use `Legacy` for Jetson Ollama models unless future Open WebUI/Ollama updates fix the default behavior.

## Connecting Open WebUI to Thor

Thor llama.cpp server was verified from Thor:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/models
```

And from Jetson:

```bash
curl http://10.0.0.213:8080/health
curl http://10.0.0.213:8080/v1/models
```

Open WebUI Admin Panel:

```text
Admin Panel -> Settings -> Connections -> OpenAI API -> +
```

Connection values:

```text
Name: Thor
Base URL: http://10.0.0.213:8080/v1
API Key: dummy / thor / anything
```

Resulting model displayed in Open WebUI:

```text
Thor.Qwen3-30B-A3B-Q4_K_M.gguf
```

Successful test prompt:

```text
Hello, who are you?
```

Response identified as Qwen from Thor.

## Current state

Working:

- NoMachine remote desktop to Jetson
- Python 3.11.9 via pyenv
- SQLite 3.53.3 local build
- `pysqlite3` compiled against SQLite 3.53.3
- Open WebUI v0.10.2 running on Jetson port 8080
- Jetson Ollama models visible in Open WebUI
- Thor llama.cpp Qwen3-30B endpoint visible in Open WebUI

Known quirks:

- NoMachine may briefly flicker during headless login.
- Open WebUI function calling should be set to `Legacy` for the Jetson Ollama models.
- Open WebUI must be launched with the `pysqlite3` override until this is wrapped in a startup script.

## Next steps

- Create a repeatable `start-openwebui.sh` script.
- Create a systemd service for Open WebUI.
- Make `Function Calling = Legacy` the default if possible.
- Add bootstrap scripts for a fresh Jetson rebuild.
- Add OpenAI / OpenRouter / Gemini endpoints if desired.
- Integrate this setup with Jarvis routing and Mission Control.
