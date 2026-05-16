# Jarvis System Documentation

## Project Overview

Jarvis is Marty's local AI assistant platform. It is designed to run primarily on local hardware with persistent memory, local language model inference, PostgreSQL-backed history, and future support for voice, vision, semantic memory, and manufacturing-focused prototype workflows.

Jarvis began on the NVIDIA Jetson AGX Xavier and has now been migrated to the NVIDIA Jetson AGX Thor Developer Kit as the primary development and inference platform.

---

## Current Primary Platform

### NVIDIA Jetson AGX Thor Developer Kit

Current host:

    y-thor

Current platform summary:

- Hardware: NVIDIA Jetson AGX Thor Developer Kit
- Architecture: ARM64
- Operating System: Ubuntu 24.04.4 LTS
- Kernel: Linux 6.8.12-tegra
- Memory: 128 GB
- GPU: NVIDIA Thor / Blackwell architecture
- CUDA: 13.0
- JetPack: 7.0
- Native inference engine: llama.cpp
- llama.cpp build: CUDA-enabled ARM64 build
- Primary model: Qwen3-30B-A3B-Q4_K_M.gguf
- Database: PostgreSQL 16
- Vector extension: pgvector
- Main repo: git@github.com:mnahtygal/Jarvis.git

---

## Previous Platform

### NVIDIA Jetson AGX Xavier

The Xavier was the original Jarvis development platform.

It successfully proved:

- Local Python assistant architecture
- Memory commands
- PostgreSQL-backed memory
- llama.cpp local inference
- CUDA-enabled local LLM serving
- OpenAI-compatible local API
- Streaming response pipeline
- MartyBench local benchmark workflow

The Xavier remains useful as:

- A backup node
- A comparison benchmark platform
- A historical baseline
- A model transfer/source machine

---

## Current Jarvis Architecture

    User Input
       ↓
    testbrain.py / API / UI
       ↓
    core.brain.think()
       ↓
    core.router.route()
       ↓
    Intent routing
       ↓
    Memory / Time / System / Chat / Docs / LLM
       ↓
    PostgreSQL memory + llama.cpp inference
       ↓
    Jarvis Response

---

## Main Repo Structure

    jarvis/
    ├── api.py
    ├── main.py
    ├── testbrain.py
    ├── testbrain_stream.py
    ├── core/
    │   ├── brain.py
    │   ├── context.py
    │   ├── db.py
    │   ├── llm.py
    │   ├── memory.py
    │   ├── router.py
    │   └── session.py
    ├── skills/
    │   ├── chat_skill.py
    │   ├── docs_skill.py
    │   ├── health_skill.py
    │   ├── help_skill.py
    │   ├── llama_cpp_skill.py
    │   ├── llm_skill.py
    │   ├── llm_stream_skill.py
    │   ├── memory_summary_skill.py
    │   ├── ollama_skill.py
    │   ├── system_skill.py
    │   ├── time_skill.py
    │   └── version_skill.py
    ├── audio/
    │   ├── listen.py
    │   └── speak.py
    ├── tools/
    │   ├── create_semantic_memory_table.py
    │   ├── create_session_state_table.py
    │   └── health_check.py
    ├── docs/
    │   ├── JARVIS_SYSTEM_DOCUMENTATION.md
    │   ├── early_sessions.md
    │   └── jarvis_system_visual.html
    ├── data/
    │   ├── memory.json
    │   └── memory_backup_before_postgres.json
    ├── benchmarks/
    │   └── singlefilegame.prompt
    └── ui-app/

---

## Core Components

### core/brain.py

Primary entry point for Jarvis thinking.

Responsibilities:

- Receives user command
- Cleans input
- Stores conversation history
- Sends command to router
- Handles fallback behavior
- Stores Jarvis response

### core/router.py

Routes user commands to the correct skill.

Current routing areas include:

- Greetings
- Time/date
- System status
- Memory commands
- Documentation commands
- Health checks
- LLM fallback

### core/db.py

PostgreSQL connection layer.

Current database:

    jarvis

Current user:

    mnahtygal

Current password used during migration:

    jarvis123

### core/memory.py

Handles persistent memory facts.

Examples:

- my favorite ship is Eurodam
- my wife's name is Kelly
- my workplace is GM
- my preferred database is SQL Server
- my taco tuesday drink is Diet Coke

### core/session.py

Handles conversation history.

Current storage:

    PostgreSQL table: conversation_history

Responsibilities:

- Save user messages
- Save assistant messages
- Retrieve recent session context
- Support future context assembly

### core/context.py

Context assembler for Jarvis.

Purpose:

- Combine memory facts
- Combine recent conversation history
- Prepare context for LLM prompts
- Eventually support semantic memory and RAG context

---

## Skills

### skills/llama_cpp_skill.py

Primary local LLM skill.

Current model:

    Qwen3-30B-A3B-Q4_K_M.gguf

Current endpoint:

    http://127.0.0.1:8080/v1/chat/completions

Current purpose:

- Call local llama.cpp server
- Send OpenAI-compatible chat payload
- Strip Qwen3 thinking blocks from visible output
- Return clean Jarvis responses

### skills/llm_skill.py

General LLM routing skill.

Current behavior:

- Prefer llama.cpp
- Fall back to Ollama if configured
- Return friendly failure message if local brains are unavailable

### skills/llm_stream_skill.py

Streaming LLM skill.

Used for:

- Long responses
- Benchmarks
- MartyBench
- Future UI streaming

### skills/ollama_skill.py

Legacy/fallback local LLM integration.

Current status:

- Optional
- Not primary on Thor
- Useful if Ollama is installed later

### skills/system_skill.py

Reports system information.

Uses:

- CPU
- Memory
- Disk
- System status

Requires:

    psutil

### Other Skills

- skills/time_skill.py handles date/time requests.
- skills/chat_skill.py handles simple conversational responses.
- skills/docs_skill.py handles Jarvis documentation responses.
- skills/health_skill.py provides Jarvis health checks.
- skills/memory_summary_skill.py summarizes current Jarvis memory.

---

## PostgreSQL Database

Current database engine:

    PostgreSQL 16

Current database:

    jarvis

Current tables:

- conversation_history
- memories
- memory_history
- semantic_memories
- session_state

Current extensions:

    vector

Migration from Xavier to Thor restored:

- Conversation history
- Memory facts
- Memory history
- Session state
- Semantic memory table structure

Verified table list:

- public.conversation_history
- public.memories
- public.memory_history
- public.semantic_memories
- public.session_state

---

## Current Local Model

### Primary Model

    Qwen3-30B-A3B-Q4_K_M.gguf

Downloaded from:

    unsloth/Qwen3-30B-A3B-GGUF

Stored at:

    ~/models/qwen3-30b/Qwen3-30B-A3B-Q4_K_M.gguf

Why this model is currently primary:

- Major upgrade from Qwen2.5-Coder 7B
- Runs well on Thor
- Good reasoning and coding capability
- Strong local assistant candidate
- Approximately 60 tokens/sec generation observed during testing
- Works with llama.cpp OpenAI-compatible server

### Previous Model

    qwen2.5-coder-7b-instruct.Q4_K_M.gguf

Stored at:

    ~/models/qwen2.5-coder-7b/qwen2.5-coder-7b-instruct.Q4_K_M.gguf

Current role:

- Fast fallback
- Coding baseline
- Xavier comparison model
- MartyBench historical benchmark model

---

## llama.cpp

Current location:

    ~/llama.cpp

Build verified:

    version: 9173
    built with GNU 13.3.0 for Linux aarch64

CUDA build enabled:

- DGGML_CUDA=ON
- DLLAMA_CURL=ON

Current build command:

    cd ~/llama.cpp

    cmake -B build \
      -DGGML_CUDA=ON \
      -DLLAMA_CURL=ON

    cmake --build build --config Release -j$(nproc)

---

## Starting Qwen3 30B Server

    cd ~/llama.cpp

    ./build/bin/llama-server \
      -m ~/models/qwen3-30b/Qwen3-30B-A3B-Q4_K_M.gguf \
      --host 0.0.0.0 \
      --port 8080 \
      -ngl 999 \
      -t $(nproc) \
      --jinja \
      --reasoning-format none

Expected successful server lines:

    CUDA0 : NVIDIA Thor
    n_ctx = 40960
    chat template, thinking = 1
    model loaded
    server is listening on http://0.0.0.0:8080

---

## Testing llama.cpp API

    curl http://127.0.0.1:8080/v1/models

Test completion:

    curl http://127.0.0.1:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{
        "model": "Qwen3-30B-A3B-Q4_K_M.gguf",
        "messages": [
          {"role": "user", "content": "What is Flask? Answer in one sentence."}
        ],
        "max_tokens": 300,
        "temperature": 0.2
      }'

---

## Testing Jarvis CLI

    cd ~/jarvis
    source .venv/bin/activate

    python3 testbrain.py

Example memory test:

    what do you remember

Expected behavior:

Jarvis should return stored memory facts from PostgreSQL.

Example:

    Here's what I remember, Marty: favorite_ship is Eurodam; my favorite color is blue; my favorite ship is Eurodam; my preference is SQL Server; my preferred database is SQL Server; my taco tuesday drink is Diet Coke; my test project is blue falcon; my wife's name is Kelly; my workplace is GM

Example LLM fallback test:

    what is flask and how is it different from express

Expected behavior:

- Jarvis routes to LLM fallback
- llama.cpp handles request
- Qwen3 responds
- thinking content is stripped from visible answer

---

## Python Environment

Current virtual environment:

    ~/jarvis/.venv

Activate:

    cd ~/jarvis
    source .venv/bin/activate

Core packages:

- requests
- flask
- flask-cors
- psycopg2-binary
- python-dotenv
- openai
- numpy
- psutil

---

## GitHub

Current repo:

    git@github.com:mnahtygal/Jarvis.git

GitHub SSH verified:

    Hi mnahtygal! You've successfully authenticated, but GitHub does not provide shell access.

Current Git identity on Thor:

    user.name=mnahtygal
    user.email=mnahtyga@hotmail.com

Important commit:

    3a7efdc Add Thor Qwen3 llama.cpp support and thinking cleanup

This commit added:

- Qwen3 30B llama.cpp support
- Qwen3 thinking block cleanup
- Updated .gitignore
- Thor model compatibility changes

---

## Current Working Milestones

Completed:

- Thor booted and validated
- CUDA 13 installed
- JetPack 7 installed
- PostgreSQL 16 installed
- pgvector installed
- Jarvis repo cloned
- GitHub SSH restored
- llama.cpp built natively on Thor
- Qwen3 30B downloaded and tested
- PostgreSQL restored from Xavier
- Jarvis memory verified on Thor
- llama.cpp inference verified
- Jarvis LLM fallback verified with Qwen3
- Qwen3 thinking output cleaned
- Thor migration commit pushed to GitHub

---

## MartyBench

MartyBench is the local benchmark concept used to evaluate Jarvis inference performance.

Initial benchmark used:

- Qwen2.5-Coder 7B
- llama.cpp
- Three.js single-file game generation
- Jetson AGX Xavier
- Windows gaming rig for rendering validation

Future MartyBench direction:

- Compare Xavier vs Thor
- Compare 7B vs 30B models
- Track tokens/sec
- Track first token latency
- Track long-context stability
- Track code generation quality
- Track browser/runtime success
- Track model hallucinated APIs
- Track final patch effort
- Store benchmark outputs in repo

---

## Current Priorities

Recommended next development order:

1. Stabilize Thor docs and config
2. Create repeatable start scripts for llama.cpp
3. Create Jarvis health check for model/database availability
4. Add model selection config
5. Add pgvector semantic memory workflow
6. Re-run MartyBench on Qwen3 30B
7. Add streaming UI support
8. Restore voice input/output
9. Add camera/vision later
10. Prototype manufacturing-focused assistant workflows

---

## Future Directions

### Semantic Memory

Use pgvector to store embedded memories and retrieve relevant context.

Planned table:

    semantic_memories

Possible fields:

- id
- text
- source
- category
- embedding
- created_at
- updated_at

### Voice

Voice remains later-stage.

Planned stack:

- USB microphone
- Whisper or faster-whisper
- Piper TTS
- Jarvis wake/command loop
- Conversation memory logging

### Vision

Vision remains later-stage.

Possible stack:

- USB camera
- OpenCV
- YOLO
- local vision model
- document/image understanding
- manufacturing inspection prototypes

### Manufacturing Prototype Ideas

Possible future Thor/Jarvis manufacturing prototypes:

- Shift handoff assistant
- Plant-floor Q&A assistant
- Maintenance triage helper
- Operational data copilot
- Quality image review assistant
- Local SOP/document assistant
- VLive/ODS query helper
- Manufacturing issue summarizer

Recommended first manufacturing prototype:

    Shift Handoff Jarvis

Why:

- Low risk
- High practical value
- Does not control equipment
- Easy to demonstrate
- Good fit for local AI
- Builds on memory, summarization, and search

---

## Safety / Design Principle

Jarvis should start as an assistant, summarizer, observer, and recommender.

Jarvis should not directly control manufacturing equipment or make autonomous plant-floor decisions without formal safety architecture, validation, and human approval.

---

## Current System Status

As of the Thor migration:

    Jarvis is now a local Blackwell-powered AI assistant platform with PostgreSQL memory, CUDA llama.cpp inference, and Qwen3 30B primary model support.

This marks the transition from:

    Jetson Xavier local assistant experiment

to:

    Jetson Thor local AI platform
EOF
