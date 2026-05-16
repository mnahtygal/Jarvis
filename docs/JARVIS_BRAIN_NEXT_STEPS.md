# Jarvis Brain Next Steps

## Purpose

This file is the working roadmap for getting the Jarvis brain where it needs to be without losing track of progress.

Jarvis is now running on the NVIDIA Jetson AGX Thor with Qwen3 30B, PostgreSQL, pgvector semantic memory, local/offline embeddings, startup services, health checks, and a working UI. The next phase is to make the brain architecture clean, reliable, and easy to extend.

---

## Current Stable State

Completed and working:

- Thor is the primary Jarvis platform.
- Qwen3 30B runs locally through llama.cpp.
- `jarvis-llama.service` auto-starts after reboot.
- PostgreSQL is active after reboot.
- Exact key/value memory works.
- pgvector semantic memory works.
- Local MiniLM embeddings are copied into `~/jarvis/models/embeddings/all-MiniLM-L6-v2`.
- Semantic embeddings are local/offline with no Hugging Face token required.
- Freeform `remember:` commands save semantic memories.
- Semantic memory is injected into Qwen3 context.
- Jarvis CLI launcher works: `./scripts/jarvis_cli.sh`.
- Health check works: `./scripts/health_check.sh`.
- UI runs after Node 22 update.
- GitHub SSH works from Thor.

---

## Current Brain Flow

Current high-level flow:

```text
User input
  ↓
testbrain.py / scripts/jarvis_cli.sh
  ↓
core.brain.think()
  ↓
core.router.route()
  ↓
Skill handler or LLM fallback
  ↓
core.context.build_messages()
  ↓
llama.cpp / Qwen3 30B
  ↓
Jarvis response
```

---

## Desired Brain Responsibilities

### `core/brain.py`

The brain should stay thin and reliable.

Responsibilities:

- Receive command.
- Clean input.
- Save user message to session history.
- Call router.
- Save Jarvis response to session history.
- Handle errors gracefully.

The brain should not own detailed memory parsing, semantic retrieval, or LLM API logic.

---

### `core/router.py`

The router should own intent detection.

Responsibilities:

- Exact memory commands.
- Freeform semantic memory commands.
- Recall commands.
- Health/status commands.
- Help/version/docs commands.
- System/time/chat commands.
- LLM fallback.

Important rule:

```text
Memory commands should be handled before the LLM fallback.
```

This prevents Qwen3 from saying it remembered something without Jarvis actually saving it.

---

### `core/context.py`

The context builder should own what Qwen3 sees.

Responsibilities:

- System prompt.
- Exact long-term memory.
- Relevant semantic memories.
- Last topic.
- Recent conversation history.
- Current user question.

Future improvement:

- Add stronger instructions that `Marty` means Marty Nahtygal unless the user explicitly refers to Marty McFly or another Marty.
- Add source-style labels for memory: exact memory, semantic memory, recent history.
- Add confidence/recency rules for answers based on memory.

---

### `skills/llama_cpp_skill.py`

The llama.cpp skill should only talk to the local model server.

Responsibilities:

- Build/send OpenAI-compatible request.
- Use `core.context.build_messages()`.
- Strip Qwen3 thinking blocks from visible output.
- Return clean text.
- Fail gracefully if the server is offline.

---

## Immediate Next Build Items

### 1. Brain Status Command

Add a command such as:

```text
brain status
```

Expected output:

```text
Jarvis Brain Status:
- Runtime: Thor / Qwen3 30B / llama.cpp
- PostgreSQL: online
- Exact memory: online, X facts
- Semantic memory: online, X rows
- Last topic: X
- Recent history rows: X
- LLM endpoint: online
- Local embeddings: online/offline-only
```

Implementation target:

```text
skills/brain_status_skill.py
core/router.py
```

---

### 2. Semantic Memory Commands

Add commands:

```text
show semantic memories
semantic memory status
semantic search: <query>
```

Expected behavior:

- `show semantic memories` lists recent semantic notes.
- `semantic memory status` shows row count and embedding status.
- `semantic search: <query>` searches pgvector directly and shows top matches.

Implementation target:

```text
skills/semantic_memory_skill.py
core/router.py
```

---

### 3. Improve Freeform Remember

Current working command:

```text
remember: Marty said ...
```

Enhance support for:

```text
remember this: ...
note: ...
note that ...
save this: ...
```

Also consider duplicate detection so repeated notes do not create noisy semantic memory rows.

Implementation target:

```text
core/router.py
core/semantic_memory.py
```

---

### 4. Better Memory Answer Rules

Jarvis should answer memory-based current/recent questions like this:

```text
Based on what you told me, over 600 IT professionals were laid off at GM that week. I cannot independently verify live/current numbers without an approved external source.
```

Rule:

- If answer comes from memory, say it is based on Marty's saved memory/context.
- If no memory exists and no approved external source exists, say Jarvis does not have current data.
- Do not hallucinate public current events.

Implementation target:

```text
core/context.py
SYSTEM_PROMPT
```

---

### 5. Brain/Memory Health in Health Check

Extend health check to verify:

- Exact memory count.
- Semantic memory count.
- Local embedding folder exists.
- Embedding model loads offline.
- Semantic search returns expected test memory.
- llama.cpp endpoint returns Qwen3 model.

Implementation target:

```text
tools/health_check.py
scripts/health_check.sh
```

---

## MartyBench Direction

The old Three.js benchmark is no longer the best primary test.

It was useful for proving:

- long-context generation
- local model speed
- HTML/JS generation
- browser runtime validation

But it is too random and too browser-debug-heavy for the next phase.

Better future benchmark candidates:

### Manufacturing Shift Handoff Benchmark

Tests:

- Summarization.
- Memory.
- Semantic recall.
- Operational reasoning.
- Structured handoff output.
- Risk identification.
- No hallucinated controls.

This is the recommended MartyBench v2 direction.

### SQL/Data Benchmark

Tests:

- Schema understanding.
- SQL generation.
- Index suggestions.
- BI/reporting logic.
- Databricks vs SQL Server reasoning.

### Local Assistant Memory Benchmark

Tests:

- Exact memory recall.
- Semantic memory recall.
- Corrections.
- Follow-up questions.
- Recent conversation context.

---

## Recommended Next Session Order

1. Add `brain status` command.
2. Add semantic memory command skill.
3. Improve `remember:` command coverage.
4. Add memory/source answer rules to system prompt.
5. Extend health check for semantic memory/offline embeddings.
6. Design MartyBench v2 manufacturing shift handoff benchmark.
7. Revisit streaming + voice after brain behavior is stable.

---

## Current North Star

Jarvis should become a reliable local assistant platform that can:

- remember exact facts,
- remember freeform notes by meaning,
- retrieve relevant memory in context,
- answer honestly from saved context,
- avoid unsupported claims,
- run fully local unless Marty explicitly approves an external source,
- support future voice, vision, and manufacturing prototype workflows.
