# Jarvis System Documentation

## Document Purpose

This document describes the current Jarvis local AI assistant architecture using the same practical style used for documenting SQL stored procedures, SQL Agent jobs, and ETL/data flows.

The goal is to clearly identify:

- Source systems
- Processing modules
- Target systems
- Data flows
- Runtime dependencies
- Operational health checks
- Built-in Jarvis commands
- Future enhancement points

---

# 1. System Overview

Jarvis is a local AI assistant running on an NVIDIA Jetson AGX Xavier.

The current architecture supports:

- CLI-based user interaction
- Rule-based command routing
- Long-term memory stored in PostgreSQL
- Conversation history stored in PostgreSQL
- Persistent session state stored in PostgreSQL
- Context assembly for LLM prompts
- llama.cpp as the primary local LLM backend
- Ollama as fallback local LLM backend
- Health check validation script
- Built-in Jarvis health, help, version, and memory summary commands
- Future pgvector semantic memory preparation

Voice and camera are intentionally planned later and are not part of the current active flow.

---

# 2. High-Level Architecture

```text
User
  |
  v
testbrain.py / future UI / future voice
  |
  v
core/brain.py
  |
  +--> core/session.py
  |       |
  |       +--> PostgreSQL conversation_history
  |       +--> PostgreSQL session_state
  |
  +--> core/router.py
  |       |
  |       +--> skills/time_skill.py
  |       +--> skills/system_skill.py
  |       +--> skills/chat_skill.py
  |       +--> core/memory.py
  |       |       |
  |       |       +--> PostgreSQL memories
  |       |       +--> PostgreSQL memory_history
  |       |
  |       +--> skills/llm_skill.py
  |               |
  |               +--> skills/llama_cpp_skill.py
  |               |       |
  |               |       +--> llama.cpp server
  |               |
  |               +--> skills/ollama_skill.py
  |                       |
  |                       +--> Ollama server
  |
  v
Response back to user
```

---

# 3. Source Systems

| Source | Current/Future | Description |
|---|---:|---|
| `testbrain.py` | Current | CLI test harness for typing commands into Jarvis |
| React/Vite UI | Future | Browser-based Jarvis interface |
| Voice input | Future | Whisper/STT command source |
| Camera input | Future | Visual context source |
| API endpoint | Future | Flask backend input route |

---

# 4. Target Systems

## PostgreSQL Targets

| Table | Purpose | Status |
|---|---|---|
| `memories` | Current long-term known facts | Active |
| `memory_history` | Audit trail of remember/update/forget events | Active |
| `conversation_history` | User and assistant message history | Active |
| `session_state` | Persistent session-level values such as `last_topic` | Active |
| `semantic_memories` | Future pgvector semantic memory table | Planned |

## Local LLM Targets

| Target | Role | Endpoint |
|---|---|---|
| llama.cpp server | Primary local LLM backend | `http://127.0.0.1:8080/v1/chat/completions` |
| Ollama server | Fallback local LLM backend | `http://localhost:11434/api/generate` |

---

# 5. Built-In Jarvis Commands

These commands are available from `testbrain.py` through `core/router.py`.

| Command | Purpose | Module |
|---|---|---|
| `jarvis help` / `what can you do` | Show current Jarvis capabilities | `skills/help_skill.py` |
| `jarvis health` | Run Jarvis health checks inside the chat loop | `skills/health_skill.py` |
| `jarvis version` | Show version, model/backend, and runtime status | `skills/version_skill.py` |
| `jarvis memory summary` | Summarize stored memories, recent history, and last topic | `skills/memory_summary_skill.py` |
| `what time is it` / `what is the date` | Return time/date response | `skills/time_skill.py` |
| `system status` | Return CPU, memory, disk, or system status | `skills/system_skill.py` |
| `remember that ...` | Store long-term memory | `core/memory.py` |
| `what is my ...` | Recall long-term memory | `core/memory.py` |
| `update my ... to ...` | Update long-term memory | `core/memory.py` |
| `forget that ...` | Delete long-term memory | `core/memory.py` |

---

# 6. Core Processing Modules

## `testbrain.py`

CLI-based manual test harness.

Responsibilities:

- Accept user input
- Ignore blank input
- Send command to `core.brain.think()`
- Print Jarvis response

## `core/brain.py`

Main orchestration layer.

Responsibilities:

- Clean user command
- Save user message to session history
- Detect topic
- Persist `last_topic`
- Route command
- Save assistant response
- Return response

Flow:

```text
think(command)
  -> strip command
  -> remember_user_message(command)
  -> detect_topic(command)
  -> set_last_topic(topic)
  -> route(command)
  -> remember_assistant_message(response)
  -> return response
```

## `core/router.py`

Rule-based command router.

Routing order:

```text
empty command
remember that ...
update my ...
forget that ...
what is my ...
what do you remember
natural memory detection
time/date
system/cpu/memory/disk/status
hello/how are you
LLM fallback
```

## `core/memory.py`

Long-term structured memory management.

Targets:

```text
memories
memory_history
```

Responsibilities:

- Store memories
- Recall memories
- Update memories
- Forget memories
- List all memories
- Build memory context for LLM prompts
- Write memory history audit records

## `core/session.py`

Conversation and session state manager.

Targets:

```text
conversation_history
session_state
```

Responsibilities:

- Save user messages
- Save assistant messages
- Read recent conversation history
- Store and retrieve persistent `last_topic`
- Clear session history
- Create new session IDs

## `core/context.py`

Central context assembler for LLM calls.

Outputs:

| Function | Target |
|---|---|
| `build_prompt()` | Ollama `/api/generate` |
| `build_messages()` | llama.cpp `/v1/chat/completions` |
| `build_context_summary()` | Debug / health check |

## `skills/llm_skill.py`

Main LLM backend selector.

Flow:

```text
ask_local_llm(user_text)
  -> ask_llama_cpp(user_text)
      -> if good answer, return
  -> ask_ollama(user_text)
      -> if good answer, return
  -> return local brain error
```

## `skills/llama_cpp_skill.py`

Primary LLM backend.

Target endpoint:

```text
http://127.0.0.1:8080/v1/chat/completions
```

Current model:

```text
qwen2.5-coder-7b
```

## `skills/ollama_skill.py`

Fallback LLM backend.

Target endpoint:

```text
http://localhost:11434/api/generate
```

Current model:

```text
qwen2.5-coder:7b
```

---

# 7. Data Flow: Normal LLM Question

Example:

```text
what is flask
```

Flow:

```text
testbrain.py
  -> core.brain.think()
      -> core.session.remember_user_message()
          -> conversation_history insert
      -> core.brain.detect_topic()
          -> detects Flask
      -> core.session.set_last_topic()
          -> session_state upsert
      -> core.router.route()
          -> falls through to LLM
      -> skills.llm_skill.ask_local_llm()
          -> skills.llama_cpp_skill.ask_llama_cpp()
              -> core.context.build_messages()
                  -> core.memory.build_memory_context()
                  -> core.session.get_recent_history()
                  -> core.session.get_last_topic()
              -> llama.cpp server
      -> core.session.remember_assistant_message()
          -> conversation_history insert
      -> response returned to user
```

Targets updated:

| Target | Action |
|---|---|
| `conversation_history` | Insert user message |
| `session_state` | Update `last_topic` |
| `conversation_history` | Insert assistant response |

---

# 8. Data Flow: Memory Write

Example:

```text
remember that my favorite ship is Eurodam
```

Flow:

```text
testbrain.py
  -> core.brain.think()
      -> remember_user_message()
      -> core.router.route()
          -> remember command detected
          -> core.memory.remember()
              -> upsert memories
              -> insert memory_history
      -> remember_assistant_message()
      -> response returned
```

Targets updated:

| Target | Action |
|---|---|
| `conversation_history` | Insert user message |
| `memories` | Insert/update memory |
| `memory_history` | Insert audit event |
| `conversation_history` | Insert assistant response |

---

# 9. Data Flow: Memory Recall

Example:

```text
what is my favorite ship?
```

Flow:

```text
testbrain.py
  -> core.brain.think()
      -> remember_user_message()
      -> core.router.route()
          -> recall pattern detected
          -> core.memory.recall()
              -> select from memories
      -> remember_assistant_message()
      -> response returned
```

Targets read/updated:

| Target | Action |
|---|---|
| `memories` | Select memory value |
| `conversation_history` | Insert user and assistant messages |

---

# 10. Data Flow: Built-In Operational Command

Example:

```text
jarvis health
```

Flow:

```text
testbrain.py
  -> core.brain.think()
      -> remember_user_message()
      -> core.router.route()
          -> health command detected
          -> skills.health_skill.get_health_response()
              -> check PostgreSQL
              -> check session_state
              -> check memories
              -> check conversation_history
              -> check context builder
              -> check llama.cpp
              -> check Ollama
      -> remember_assistant_message()
      -> response returned
```

Similar built-in operational commands:

```text
jarvis help
jarvis version
jarvis memory summary
```

---

# 11. Data Flow: Follow-Up Question

Example:

```text
what is flask
how is it different from express
```

First question:

```text
detect_topic("what is flask")
  -> Flask
set_last_topic("Flask")
```

Follow-up:

```text
detect_topic("how is it different from express")
  -> follow-up phrase detected
  -> does not overwrite last_topic
```

LLM context includes:

```text
Last topic: Flask
Recent conversation:
user: what is flask
assistant: ...
user: how is it different from express
```

---

# 12. Database Tables

## `memories`

Stores current known long-term facts.

| Column | Description |
|---|---|
| `memory_key` | Unique memory key |
| `memory_value` | Stored value |
| `updated_at` | Last update timestamp |

## `memory_history`

Audit trail for memory changes.

| Column | Description |
|---|---|
| `action_type` | remember/update/forget |
| `memory_key` | Memory key |
| `old_value` | Previous value |
| `new_value` | New value |
| `event_timestamp` | Event timestamp |

## `conversation_history`

Stores user/assistant conversation turns.

| Column | Description |
|---|---|
| `id` | Row identifier |
| `session_id` | Session identifier |
| `role` | user or assistant |
| `message` | Message text |
| `created_at` | Insert timestamp |

## `session_state`

Stores persistent session state.

| Column | Description |
|---|---|
| `session_id` | Session identifier |
| `last_topic` | Most recent durable topic |
| `updated_at` | Last update timestamp |

## `semantic_memories`

Future pgvector semantic memory table.

Current status:

- Prep script exists
- pgvector extension is not currently available from apt packages on current Jetson PostgreSQL install
- Table is not yet active

Expected future columns:

| Column | Description |
|---|---|
| `id` | Row identifier |
| `source_type` | Source category |
| `source_id` | Optional external/source row ID |
| `content` | Text to embed |
| `metadata` | JSON metadata |
| `embedding` | Vector embedding |
| `created_at` | Created timestamp |
| `updated_at` | Updated timestamp |

---

# 13. Operational Scripts

## Health Check

Script:

```text
tools/health_check.py
```

Checks:

| Check | Description |
|---|---|
| Python imports | Confirms core modules import |
| PostgreSQL connection | Confirms database access |
| Session state | Confirms `session_state` and `last_topic` |
| Long-term memories | Confirms memories are readable |
| Conversation history | Confirms recent history is readable |
| Context builder | Confirms prompt context can be assembled |
| llama.cpp server | Confirms primary LLM backend is reachable |
| Ollama server | Confirms fallback LLM backend is reachable |

Run:

```bash
./tools/health_check.py
```

## Session State Table Migration

Script:

```text
tools/create_session_state_table.py
```

Run:

```bash
python3 tools/create_session_state_table.py
```

## Semantic Memory Table Prep

Script:

```text
tools/create_semantic_memory_table.py
```

Known current result:

```text
pgvector extension is not available in current PostgreSQL install
```

Run:

```bash
python3 tools/create_semantic_memory_table.py
```

---

# 14. Runtime Dependencies

## PostgreSQL

Current version:

```text
PostgreSQL 12.22 on Ubuntu 20.04 aarch64
```

Used for:

- memories
- memory history
- conversation history
- session state
- future semantic memory

## llama.cpp

Primary LLM backend.

Typical launch:

```bash
cd ~/llama.cpp

./build/bin/llama-server \
  -m /home/mnahtygal/models/qwen2.5-coder-7b/qwen2.5-coder-7b-instruct.Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl auto \
  -t 8
```

## Ollama

Fallback LLM backend.

Known local models:

```text
phi3:latest
qwen2.5-coder:7b
qwen2.5-coder:3b
```

---

# 15. Current Operational Startup

Recommended startup:

```bash
cd ~/jarvis
./tools/health_check.py
python3 testbrain.py
```

Expected health status:

```text
Jarvis health check complete: READY
```

---

# 16. Current Known Limitations

| Area | Limitation |
|---|---|
| Voice | Planned later |
| Camera | Planned later |
| pgvector | Not installed yet |
| Topic detection | Improved but still rule-based |
| Context length | Recent history only, currently limited |
| LLM verbosity | Some answers are longer than desired |
| Security | DB password still has a local default in code |
| Session model | Default session only for now |

---

# 17. Recommended Next Steps

## Near-Term

1. Install/build pgvector
2. Add pgvector health check
3. Create embedding skill
4. Build semantic recall in read-only mode
5. Tune LLM response length
6. Keep documentation updated as commands are added

## Later

1. Add voice input
2. Add camera input
3. Add React/Vite control UI
4. Add memory management UI
5. Add benchmark dashboard
6. Add MartyBench model comparison tooling

---

# 18. Current Architecture Status

```text
Status: Stable local assistant foundation

Core path:
CLI -> brain -> router -> context -> llama.cpp -> response

Persistence:
PostgreSQL memories, history, session state

Fallback:
Ollama available

Built-in commands:
help, health, version, memory summary

Health:
tools/health_check.py passing
jarvis health available in chat loop

Next major feature:
pgvector semantic memory
```
