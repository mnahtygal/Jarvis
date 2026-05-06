## 🚀 Quick Start

```bash
cd ~/jarvis
python3 main.py

# 🤖 Jarvis Project — Build Log & Architecture (Phase 1 Complete)

**Author:** Marty
**Platform:** NVIDIA Jetson
**Goal:** Build a local, modular, voice-capable AI assistant with persistent memory

---

# 🧠 Core Architecture

```
Input → Brain → Router → Skills → Memory → LLM → Response
```

### Components

| Layer                                 | Description                                    |
| ------------------------------------- | ---------------------------------------------- |
| `core/brain.py`                       | Entry point, orchestrates thinking             |
| `core/router.py`                      | Decision engine (rules + memory + fallback)    |
| `skills/`                             | Modular capabilities (time, system, chat, LLM) |
| `core/memory.py`                      | Persistent long-term memory (JSON)             |
| `core/session.py`                     | Short-term conversation memory                 |
| `core/llm.py` / `skills/llm_skill.py` | Local LLM integration (Ollama)                 |

---

# ⚙️ Phase 0 — Initial System

## ✅ Features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

* Command routing
* Basic skills:

  * Time
  * System stats
  * Chat responses
* LLM fallback (Ollama)

## 🧠 Behavior

* Deterministic first
* LLM as fallback

---

# 🧠 Phase 1A — Persistent Memory

## ✅ Added

* `core/memory.py`
* `data/memory.json`

## Features

```
remember that my favorite ship is Eurodam
```

```
what is my favorite ship
```

```
what do you remember
```

## Storage Format

```json
{
  "facts": {},
  "history": []
}
```

---

# 🧠 Phase 1B — LLM + Memory Integration

## ✅ Enhancement

* Inject long-term memory into LLM prompt

## Result

```
what ship do I like again
```

Jarvis can now answer naturally without exact phrasing.

---

# 🧠 Phase 1C — Memory Management (CRUD)

## Commands

### Create

```
remember that my workplace is GM
```

### Read

```
what is my workplace
what do you remember
```

### Update

```
update my workplace to Ford
```

### Delete

```
forget that my workplace
```

---

# 🧠 Phase 1D — Natural Language Memory Parsing

## New Capability

Jarvis understands:

```
I work at GM
I prefer SQL Server
my taco Tuesday drink is Diet Coke
```

No “remember that” required.

## Implementation

* `_try_natural_memory()` in router
* Pattern-based extraction

---

# 🧠 Phase 1E — Memory Normalization

## Problem Solved

```
my preference
my preferred database
```

## Solution

### `normalize_key()`

Maps:

```
preference → my preferred database
job/work → my workplace
wife → my wife's name
```

## Applied In:

* Remember
* Update
* Recall

---

# 🧠 Current Memory Capabilities

* ✔️ Persistent JSON memory
* ✔️ Natural language input → structured facts
* ✔️ Intelligent recall (direct + LLM-assisted)
* ✔️ Full lifecycle (Create / Read / Update / Delete)
* ✔️ Normalized keys for consistency

---

# 🧪 Example Session

```
You: I work at GM
Jarvis: Got it, Marty. I'll remember that your workplace is GM.

You: where is my job
Jarvis: Your workplace is GM, Marty.

You: I prefer SQL Server
Jarvis: Got it, Marty. I'll remember that your preferred database is SQL Server.

You: what database do I like
Jarvis: Your preferred database is SQL Server.
```

---

# 📁 Project Structure

```
jarvis/
├── core/
│   ├── brain.py
│   ├── router.py
│   ├── memory.py
│   ├── session.py
│   └── llm.py
│
├── skills/
│   ├── time_skill.py
│   ├── system_skill.py
│   ├── chat_skill.py
│   ├── llm_skill.py
│   └── llm_stream_skill.py
│
├── data/
│   └── memory.json
│
└── main.py
```

---

# 🚀 Next Phases

## Phase 2 — Intelligence Layer

* Smarter recall (synonyms)
* Context linking
* Memory categorization

## Phase 3 — Streaming

* Token-by-token responses
* Real-time feedback

## Phase 4 — Voice

* Wake word (“Hey Jarvis”)
* Continuous listening
* TTS streaming

## Phase 5 — Vision

* Camera integration
* Face recognition
* Object detection tied to memory

---

# 💬 Design Principles

* Local-first (no cloud dependency)
* Modular architecture
* Deterministic → AI fallback
* Incremental builds
* Git-backed evolution

---

# 🏁 Status

✅ Phase 1 Complete

Jarvis now has:

* Persistent memory
* Natural language understanding
* Structured reasoning layer

---

# 🧠 Final Note

This is no longer a prototype.

This is a **foundation for a real personal AI system**.

