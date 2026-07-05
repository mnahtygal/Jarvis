# AI Lab Notes

_Last updated: July 5, 2026_

These notes capture the current Marty AI Lab architecture after the July 2026 Jarvis / Jetson / Thor buildout.

## Big picture

The lab is being split into two main roles:

```text
Thor = production AI server
Jetson = AI development sandbox / Open WebUI front end
Laptop = browser / remote control
GitHub = source of truth
```

## Current architecture

```text
Windows Laptop
    |
    | Browser
    v
Jetson AGX Xavier - 10.0.0.42
    |
    | Open WebUI :8080
    |
    +--> Jetson Ollama :11434
    |       - phi3:latest
    |       - qwen2.5-coder:3b
    |       - qwen2.5-coder:7b
    |
    +--> Thor llama.cpp :8080
            - Qwen3-30B-A3B-Q4_K_M.gguf
```

## Thor role

Thor remains the production Jarvis machine.

Current responsibilities:

- Jarvis core development
- Mission Control UI
- llama.cpp server
- Qwen3-30B model hosting
- Vision model hosting
- PostgreSQL / pgvector memory
- Long-running services
- GitHub-backed Jarvis source of truth

Current verified llama.cpp health checks:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/models
```

Observed Thor model:

```text
Qwen3-30B-A3B-Q4_K_M.gguf
```

OpenAI-compatible endpoint:

```text
http://10.0.0.213:8080/v1
```

## Jetson role

The Jetson is now the AI development sandbox and front-end machine.

Current responsibilities:

- NoMachine remote desktop
- Open WebUI front end
- Ollama local small models
- AI experimentation
- Future camera / vision / sensor work
- Future agent / RAG testing

Current Jetson address:

```text
10.0.0.42
```

Current Jetson web UI:

```text
http://10.0.0.42:8080
```

Current local Ollama models:

```text
phi3:latest
qwen2.5-coder:3b
qwen2.5-coder:7b
```

## Open WebUI state

Open WebUI v0.10.2 is running on the Jetson.

It currently connects to:

1. Jetson Ollama
2. Thor llama.cpp via OpenAI-compatible API

Current model list in Open WebUI:

```text
phi3:latest
qwen2.5-coder:3b
qwen2.5-coder:7b
Thor.Qwen3-30B-A3B-Q4_K_M.gguf
```

Important quirk:

```text
Function Calling should be set to Legacy for Jetson Ollama models.
```

Default/native function calling caused:

- Qwen2.5-Coder returning tool-call JSON
- Qwen2.5-Coder repeating `G`
- Phi3 reporting that it does not support tools

Legacy mode fixed normal chat behavior.

## Weekend build recap

### Thursday / Friday / Saturday GitHub + Jarvis work

- Continued Jarvis cleanup on Thor
- Validated Jarvis service health
- Discussed Mission Control direction
- Continued GitHub-backed Jarvis documentation
- Added / discussed versioning and project notes
- Confirmed Thor as the stable Jarvis production box

### Jetson remote desktop work

- XRDP was tested but produced unusable 592x440 resolution
- NoMachine was installed instead
- XRDP and Vino conflicts were identified and disabled
- NoMachine produced usable 1920x1080 remote desktop
- Jetson is currently headless with only power and CAT6 connected

### Jetson Python / SQLite work

- System Python was Python 3.8.10
- Installed Python 3.11.9 with pyenv
- Built SQLite 3.53.3 locally
- Built pysqlite3 against SQLite 3.53.3
- Used pysqlite3 injection to satisfy ChromaDB / Open WebUI requirements

### Open WebUI work

- Installed Open WebUI v0.10.2 in `~/repos/openwebui-venv`
- Solved SQLite / Chroma startup failure
- Started Open WebUI on Jetson port 8080
- Verified laptop browser access
- Verified Jetson Ollama models
- Fixed function calling behavior by using Legacy mode
- Added Thor as an OpenAI-compatible connection
- Verified Thor Qwen3-30B response from Open WebUI

## Desired future architecture

```text
Laptop Browser
    |
    v
Open WebUI / Mission Control
    |
    +--> Jetson Ollama for quick local models
    +--> Thor llama.cpp for large local models
    +--> OpenAI API for cloud GPT models
    +--> OpenRouter for Claude / Gemini / Mistral / Qwen / DeepSeek
    +--> Jarvis router for task-based model selection
```

## Future model routing idea

Jarvis / Mission Control could route by task type:

```text
Quick local chat       -> Jetson Phi3
Coding helper          -> Jetson Qwen2.5-Coder or Thor Qwen3-30B
Heavy reasoning        -> Thor Qwen3-30B or cloud GPT
Vision task            -> Thor vision server or Jetson camera stack
RAG / documents        -> Jetson Open WebUI + Chroma / future vector store
Voice assistant        -> Jarvis STT/TTS stack
```

## Near-term TODOs

- Create `scripts/start-openwebui.sh` for the Jetson.
- Create a systemd service for Open WebUI.
- Document how to add OpenAI-compatible endpoints in Open WebUI.
- Make Legacy function calling default if possible.
- Add a Jetson bootstrap script for rebuilds.
- Add NoMachine setup script.
- Add optional Docker setup.
- Decide whether Open WebUI belongs permanently on Jetson or eventually behind Mission Control.
- Connect this architecture back into Jarvis routing.

## Useful commands

### Jetson Open WebUI startup

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

### Check Jetson Ollama

```bash
ollama list
ollama run phi3:latest
ollama run qwen2.5-coder:7b
```

### Check Thor from Jetson

```bash
curl http://10.0.0.213:8080/health
curl http://10.0.0.213:8080/v1/models
```

### Check Open WebUI

```text
http://10.0.0.42:8080
```

## Working principle

Keep Thor stable.

Use the Jetson to experiment.

Promote only proven pieces from the Jetson into Jarvis / Thor.
