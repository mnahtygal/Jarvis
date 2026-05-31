# Jarvis

Jarvis is Marty's local-first AI assistant project.

It runs on local hardware, uses local model inference, stores memory in PostgreSQL, and is being built toward a modular Jarvis-style assistant with future voice and vision support.

## Current Status

Jarvis is currently running on the NVIDIA Jetson AGX Thor Developer Kit as the primary development and inference platform.

Current brain foundation:

- Local inference through `llama.cpp`
- Primary model: `Qwen3-30B-A3B-Q4_K_M.gguf`
- Ollama available as fallback
- PostgreSQL exact long-term memory
- PostgreSQL conversation history
- pgvector semantic memory
- Local/offline MiniLM embeddings
- Runtime/project identity skill
- Direct exact-memory routing for common known facts
- Weighted semantic memory ranking
- Brain regression test runner

Voice and camera are intentionally later phases.

---

## Quick Start

```bash
cd ~/jarvis
source .venv/bin/activate
python testbrain.py
```

Run the brain regression test:

```bash
python tools/regression_test_brain.py
```

Run health checks:

```bash
./scripts/health_check.sh
```

Start the llama.cpp server if needed:

```bash
./scripts/start_jarvis_llama_server.sh
```

Check Jarvis status:

```bash
./scripts/status_jarvis.sh
```

---

## Current Architecture

```text
User input
  ↓
testbrain.py / scripts / API / UI
  ↓
core.brain.think()
  ↓
core.router.route()
  ↓
Skill handler, exact-memory direct answer, or LLM fallback
  ↓
core.context.build_messages()
  ↓
llama.cpp / Qwen3 30B
  ↓
Jarvis response
```

Not every request reaches the LLM.

Jarvis handles known deterministic questions first:

- Runtime/platform questions
- Model/runtime questions
- Memory stack questions
- Jarvis long-term goal questions
- Common exact-memory facts
- Health/status/help/docs commands
- Semantic memory commands

Open-ended questions fall through to the local LLM.

---

## Platform

Current primary platform:

```text
Host: y-thor
Hardware: NVIDIA Jetson AGX Thor Developer Kit
OS: Ubuntu 24.04.4 LTS
Architecture: ARM64
Memory: 128 GB
CUDA: 13.0
Inference: llama.cpp
Database: PostgreSQL 16
Vector extension: pgvector
```

Previous platform:

```text
NVIDIA Jetson AGX Xavier
```

The Xavier proved the early local Jarvis architecture. Thor is now the active development and inference platform.

---

## Core Components

| Component | Purpose |
|---|---|
| `core/brain.py` | Main thinking entry point. Stores user/assistant messages and calls the router. |
| `core/router.py` | Intent routing, memory commands, deterministic known-fact answers, and LLM fallback. |
| `core/context.py` | Builds the prompt/messages sent to llama.cpp using exact memory, semantic memory, and recent conversation. |
| `core/memory.py` | PostgreSQL-backed exact long-term memory. |
| `core/session.py` | PostgreSQL-backed conversation history and last-topic state. |
| `core/semantic_memory.py` | pgvector semantic memory, local embeddings, source/category/tag ranking. |
| `skills/llama_cpp_skill.py` | Calls the local llama.cpp OpenAI-compatible server. |
| `skills/llm_skill.py` | LLM routing layer with llama.cpp primary and Ollama fallback. |
| `skills/runtime_skill.py` | Deterministic runtime, model, memory stack, and Jarvis goal responses. |
| `tools/regression_test_brain.py` | Brain regression test runner. |

---

## Memory Architecture

Jarvis uses three local memory layers.

### 1. Exact Long-Term Memory

Stored in PostgreSQL and managed by:

```text
core/memory.py
```

Examples:

```text
favorite_ship = Eurodam
my wife's name = Kelly
my workplace = GM
my preferred database = SQL Server
my taco tuesday drink = Diet Coke
```

Common exact-memory questions are answered directly without LLM fallback.

Examples:

```text
what database does Marty prefer
what cruise ship does Marty like
what is my wife's name
where do I work
```

### 2. Conversation History

Stored in PostgreSQL table:

```text
conversation_history
```

Managed by:

```text
core/session.py
```

Used for recent context and follow-up awareness.

### 3. Semantic Memory

Stored in PostgreSQL with pgvector and managed by:

```text
core/semantic_memory.py
```

Embedding model:

```text
models/embeddings/all-MiniLM-L6-v2
```

The embedding model is local/offline. No Hugging Face token or external API is required.

Semantic memory supports:

- source weighting
- category inference
- tag inference
- category boosts
- weighted similarity ranking
- weighted context filtering
- debug formatting with category/tag details

Current normalized categories:

```text
cruise
hardware
preference
project
test
work
```

Ranking formula:

```text
weighted_similarity = similarity + source_boost + category_boost
```

---

## Runtime Identity

Runtime/project identity is handled by:

```text
skills/runtime_skill.py
```

Supported deterministic questions include:

```text
what hardware are you running on
what model are you using
what memory systems do you have
what is the long term goal for Jarvis
```

These questions do not require LLM fallback.

---

## Regression Test

Run:

```bash
python tools/regression_test_brain.py
```

Current regression prompts:

```text
what hardware are you running on
what model are you using
what memory systems do you have
what is the long term goal for Jarvis
what database does Marty prefer
what cruise ship does Marty like
what is my wife's name
where do I work
what do you remember
semantic memory status
brain status
```

Expected behavior:

- Runtime/project questions answer deterministically.
- Common exact-memory facts avoid LLM fallback.
- Semantic memory status confirms local/offline embedding model.
- Brain status reports Thor / Qwen3 30B / llama.cpp as ready.

---

## Useful Commands

Activate the Python environment:

```bash
cd ~/jarvis
source .venv/bin/activate
```

Start CLI:

```bash
python testbrain.py
```

Run regression test:

```bash
python tools/regression_test_brain.py
```

Run semantic memory test:

```bash
python tools/test_semantic_memory.py
```

Check semantic memory status in Jarvis:

```text
semantic memory status
```

Check brain status in Jarvis:

```text
brain status
```

---

## Project Structure

```text
jarvis/
├── api.py
├── main.py
├── testbrain.py
├── core/
│   ├── brain.py
│   ├── context.py
│   ├── db.py
│   ├── llm.py
│   ├── memory.py
│   ├── router.py
│   ├── semantic_memory.py
│   └── session.py
├── skills/
│   ├── brain_status_skill.py
│   ├── chat_skill.py
│   ├── docs_skill.py
│   ├── health_skill.py
│   ├── help_skill.py
│   ├── llama_cpp_skill.py
│   ├── llm_skill.py
│   ├── memory_summary_skill.py
│   ├── ollama_skill.py
│   ├── runtime_skill.py
│   ├── semantic_memory_skill.py
│   ├── system_skill.py
│   ├── time_skill.py
│   └── version_skill.py
├── tools/
│   ├── create_semantic_memory_table.py
│   ├── create_session_state_table.py
│   ├── health_check.py
│   ├── regression_test_brain.py
│   ├── test_semantic_memory.py
│   └── voice_loop.py
├── scripts/
│   ├── health_check.sh
│   ├── jarvis_cli.sh
│   ├── jarvis_voice_cli.sh
│   ├── start_jarvis_llama_server.sh
│   ├── status_jarvis.sh
│   └── stop_jarvis_llama_server.sh
├── docs/
│   ├── JARVIS_BRAIN_NEXT_STEPS.md
│   ├── JARVIS_SYSTEM_DOCUMENTATION.md
│   ├── MARTYBENCH_V2_SHIFT_HANDOFF.md
│   └── jarvis_system_visual.html
├── models/
│   ├── embeddings/
│   └── piper/
├── benchmarks/
├── audio/
├── ui/
└── ui-app/
```

---

## Current Roadmap

Recommended next order:

1. Verify API/UI uses the same `core.brain.think()` path as CLI.
2. Add memory review/category commands.
3. Start MartyBench v2.
4. Improve UI/API dashboard.
5. Bring back voice pipeline.
6. Add camera/vision pipeline last.

---

## Later Phases

### Voice

Target flow:

```text
microphone
  ↓
Whisper
  ↓
core.brain.think()
  ↓
Piper
  ↓
speaker
```

Initial voice approach:

- push-to-talk or terminal voice loop first
- no wake word yet
- confirm transcription quality
- keep voice actions conservative

### Vision

Vision comes after voice.

Initial vision approach:

- snapshot-based image understanding first
- no live video loop at first
- keep vision separate from core memory until capture behavior is clear

---

## Notes

Jarvis is intentionally local-first.

The current goal is a reliable local assistant foundation before adding messy audio/video behavior. Voice and camera are still deliberately later phases.
