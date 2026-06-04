# Jarvis Brain Next Steps

## Purpose

This file is the working roadmap for getting the Jarvis brain where it needs to be without losing track of progress.

Jarvis is now running on the NVIDIA Jetson AGX Thor with Qwen3 30B, PostgreSQL, pgvector semantic memory, local/offline embeddings, startup services, health checks, deterministic runtime identity responses, exact-memory routing, MartyBench v2, a context regression test, and a combined regression check script.

The current phase is no longer basic brain bring-up. The current phase is reliability, repeatable evaluation, UI/API polish, and preparing for the next major capabilities.

---

## Current Stable State

Completed and working:

- Thor is the primary Jarvis platform.
- Qwen3 30B runs locally through llama.cpp.
- Ollama remains available as a fallback path if installed/configured later.
- `jarvis-llama.service` auto-starts after reboot.
- PostgreSQL is active after reboot.
- Exact key/value memory works.
- Conversation history is stored in PostgreSQL.
- pgvector semantic memory works.
- Local MiniLM embeddings are copied into:

```text
~/jarvis/models/embeddings/all-MiniLM-L6-v2
```

- Semantic embeddings are local/offline with no Hugging Face token required.
- Freeform remember/note/save commands save semantic memories.
- Duplicate detection is active for semantic notes.
- Semantic memory is injected into Qwen3 context.
- Semantic memory now uses weighted ranking.
- Runtime/project identity responses are deterministic.
- Common exact-memory questions avoid LLM fallback.
- Context assembly has a dedicated regression test.
- Brain behavior has a dedicated regression test.
- Combined regression check works:

```bash
./scripts/regression_check.sh
```

- Jarvis CLI launcher works:

```bash
./scripts/jarvis_cli.sh
```

- Health check works:

```bash
./scripts/health_check.sh
```

- UI runs after Node 22 update.
- GitHub SSH works from Thor.

---

## Current Brain Flow

Current high-level flow:

```text
User input
  ↓
testbrain.py / scripts/jarvis_cli.sh / API / UI
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

Important note:

Not every command reaches the LLM. Known deterministic questions are handled by router/skills first.

Examples:

- Runtime/platform questions route to `skills/runtime_skill.py`.
- Jarvis long-term goal routes to `skills/runtime_skill.py`.
- Common known facts route directly through exact memory.
- Semantic memory inspection routes to `skills/semantic_memory_skill.py`.
- Only open-ended questions fall through to llama.cpp.

Benchmark exception:

- MartyBench v2 uses a raw llama.cpp path without normal Jarvis memory/context injection.
- This keeps benchmark evaluation isolated from personal Jarvis memory unless synthetic benchmark memory is explicitly injected.

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
- Exact-memory direct answers for common known facts.
- Freeform semantic memory commands.
- Recall commands.
- Runtime/project identity routing.
- Health/status commands.
- Help/version/docs commands.
- System/time/chat commands.
- Semantic memory commands.
- LLM fallback.

Important rule:

```text
Memory commands and deterministic known-fact commands should be handled before the LLM fallback.
```

This prevents Qwen3 from saying it remembered something without Jarvis actually saving it, and it keeps known facts fast and deterministic.

---

### `core/context.py`

The context builder owns what Qwen3 sees.

Responsibilities:

- System prompt.
- Exact long-term memory.
- Relevant semantic memories.
- Weighted semantic memory filtering.
- Last topic.
- Recent conversation history.
- Current user question.
- Completion-style prompt building through `build_prompt()`.
- OpenAI-compatible chat messages through `build_messages()`.
- Human-readable context summaries through `build_context_summary()`.
- Reusable context sections through `build_context_sections()`.
- Defensive behavior when memory/history/semantic retrieval is unavailable.

Current behavior:

- Uses exact memory when available.
- Retrieves semantic memory with pgvector.
- Filters semantic memory using weighted similarity.
- Includes source/category/tag information in formatted semantic memory results.
- Tells Qwen3 to trust saved memory/context over general model knowledge.
- Keeps context construction testable through `tools/regression_test_context.py`.

---

### `core/semantic_memory.py`

Semantic memory owns meaning-based recall.

Current responsibilities:

- Load local/offline embedding model.
- Generate embeddings using local MiniLM.
- Store semantic memories in PostgreSQL with pgvector.
- Search semantic memories by vector similarity.
- Apply source weighting.
- Apply category boosts.
- Infer categories and tags.
- Format results for debug output and prompt context.

Current semantic memory categories:

```text
cruise
hardware
preference
project
test
work
```

Current semantic memory ranking uses:

```text
weighted_similarity = similarity + source_boost + category_boost
```

Current cleanup approach:

- Test/dev semantic memories are not deleted.
- Test/dev rows are categorized as `test`.
- Normal context is no longer polluted by test rows.
- Existing embeddings are preserved.

---

### `skills/llama_cpp_skill.py`

The llama.cpp skill talks to the local model server.

Responsibilities:

- Build/send OpenAI-compatible request.
- Use `core.context.build_messages()` for normal Jarvis LLM fallback.
- Provide a raw llama.cpp path for isolated benchmark/evaluation prompts.
- Strip Qwen3 thinking blocks from visible output.
- Return clean text.
- Fail gracefully if the server is offline.

Primary endpoint:

```text
http://127.0.0.1:8080/v1/chat/completions
```

Primary model:

```text
Qwen3-30B-A3B-Q4_K_M.gguf
```

---

### `skills/runtime_skill.py`

Runtime skill owns deterministic runtime and project identity responses.

Current responses include:

- Current platform / hardware.
- Current model runtime.
- Current memory stack.
- Jarvis long-term project goal.

This keeps known Jarvis identity questions out of the LLM fallback path.

Examples:

```text
what hardware are you running on
what model are you using
what memory systems do you have
what is the long term goal for Jarvis
```

---

## Completed Brain Build Items

### 1. Brain Status Command

Status: Complete

Command:

```text
brain status
```

Current output includes:

```text
Jarvis Brain Status:
- Overall: READY
- Runtime: Thor / Qwen3 30B / llama.cpp
- PostgreSQL: online
- Exact memory: online, X facts
- Semantic memory: online, X rows
- Last topic: X
- Recent history rows checked: X
- LLM endpoint: online
- Local embeddings: online/offline-only local model present
```

Implementation:

```text
skills/brain_status_skill.py
core/router.py
```

---

### 2. Semantic Memory Commands

Status: Complete

Commands:

```text
show semantic memories
semantic memory status
semantic search: <query>
show memory categories
show cruise memories
show project memories
show test memories
show work memories
```

Current behavior:

- `show semantic memories` lists recent semantic notes.
- `semantic memory status` shows row count and embedding status.
- `semantic search: <query>` searches pgvector directly and shows top matches.
- Category commands show normalized semantic memory categories and filtered category rows.

Implementation:

```text
skills/semantic_memory_skill.py
core/router.py
```

---

### 3. Freeform Remember Improvements

Status: Complete

Supported commands include:

```text
remember this: ...
remember that ...
remember ...
note: ...
note that ...
save this: ...
save ...
```

Duplicate detection is active so repeated semantic notes do not create unnecessary noise.

Implementation:

```text
core/router.py
core/semantic_memory.py
```

---

### 4. Better Memory Answer Rules

Status: Complete

Jarvis now follows these memory-answer rules:

- If an answer comes from exact memory, Jarvis says it is based on saved memory when useful.
- If an answer comes from semantic memory, Jarvis says it is based on saved semantic memory or what Marty told it when useful.
- If no saved memory exists and no approved external source exists, Jarvis avoids inventing current facts.
- Runtime/project identity questions are deterministic and do not require LLM fallback.
- Common exact-memory questions answer directly without LLM fallback.

Implementation:

```text
core/context.py
core/router.py
skills/runtime_skill.py
```

---

### 5. Brain/Memory Health

Status: Mostly complete

Current checks include:

- PostgreSQL online.
- Exact memory count.
- Semantic memory count.
- Local embedding folder exists.
- Embedding model loads offline.
- llama.cpp endpoint online.
- Runtime/model state.

Implementation:

```text
tools/health_check.py
scripts/health_check.sh
skills/brain_status_skill.py
```

---

### 6. Context Assembler Cleanup

Status: Complete

Completed work:

- Fixed `build_prompt()` undefined return bug.
- Added reusable `build_context_sections()`.
- Centralized context/system-message construction.
- Preserved `build_messages()` for llama.cpp.
- Preserved `build_context_summary()` for debugging.
- Added defensive wrappers around exact memory, semantic memory, recent history, and last-topic retrieval.
- Added dedicated context regression test.

Implementation:

```text
core/context.py
tools/regression_test_context.py
```

---

### 7. Combined Regression Check

Status: Complete

Run:

```bash
./scripts/regression_check.sh
```

Current behavior:

- Runs context regression first.
- Runs brain regression second.
- Stops on failure.
- Uses `.venv` automatically when present.

Implementation:

```text
scripts/regression_check.sh
tools/regression_test_context.py
tools/regression_test_brain.py
```

---

## Current Regression Tests

### Context Regression

Run:

```bash
python tools/regression_test_context.py
```

Checks:

```text
build_context_sections
build_prompt
build_messages
build_context_summary
```

Expected result:

```text
Context regression complete: 4/4 passed
```

### Brain Regression

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
show memory categories
show cruise memories
show project memories
show test memories
show work memories
```

Expected behavior:

- Runtime/project questions answer deterministically.
- Common exact-memory facts avoid LLM fallback.
- Semantic memory status confirms local/offline embedding model.
- Brain status reports Thor / Qwen3 30B / llama.cpp as ready.
- Memory category commands return normalized category results.

### Combined Regression

Run:

```bash
./scripts/regression_check.sh
```

Expected result:

```text
Combined regression check passed
```

---

## MartyBench v2 Status

Status: Working baseline complete

MartyBench v2 now includes:

- Basic shift notes variant.
- Messy shift notes variant.
- Conflict/uncertainty variant.
- Memory-aware variant.
- Scoring rubric.
- Expected output guide.
- Raw llama.cpp runner.
- Synthetic benchmark memory flag.
- Human scoring template generation.
- Metadata output for each run.
- Generated result output ignored by Git.

Runner:

```bash
python tools/run_martybench_v2_shift_handoff.py --variant basic
python tools/run_martybench_v2_shift_handoff.py --variant messy
python tools/run_martybench_v2_shift_handoff.py --variant conflict
python tools/run_martybench_v2_shift_handoff.py --variant memory --include-benchmark-memory
```

Why raw llama.cpp is used:

- Normal Jarvis LLM calls inject exact memory, semantic memory, and recent conversation.
- Benchmark prompts need isolation from normal personal/project memory.
- The raw llama.cpp path sends only benchmark prompt content unless synthetic benchmark memory is explicitly included.

---

## Sunday Polish Completed

Completed polish work:

- Runtime identity refactored into `skills/runtime_skill.py`.
- Deterministic answers added for:
  - hardware/platform
  - model/runtime
  - memory stack
  - Jarvis long-term goal
- Exact-memory direct routing added for common personal facts:
  - preferred database
  - favorite ship
  - wife's name
  - workplace
- Semantic memory ranking improved:
  - source weighting
  - category boost
  - weighted similarity
  - weighted context filtering
- Semantic metadata normalized:
  - cruise
  - hardware
  - preference
  - project
  - test
  - work
- Test/dev semantic memories kept but categorized as `test`.
- Brain regression test runner added.
- Context regression test runner added.
- Combined regression script added.

Regression tests currently pass.

---

## Immediate Next Build Items

### 1. MartyBench Scoring / Report Generation

Status: Next

Goal:

Turn MartyBench outputs into repeatable score/report artifacts.

Potential features:

- Human scoring template prefilled with run metadata.
- Score summary markdown.
- Latest-run report command.
- Basic model/runtime metadata capture.
- Optional self-check prompt.
- Compare runs by variant.

Implementation target:

```text
tools/run_martybench_v2_shift_handoff.py
benchmarks/results/
benchmarks/martybench_v2_shift_handoff/
```

---

### 2. API/UI Dashboard Pass

Status: Next

Goal:

Make the frontend/API useful as a real Jarvis dashboard.

Current UI improvement complete:

- Quick command buttons for brain status, semantic memory status, memory categories, cruise memories, project memories, and work memories.

Potential dashboard sections:

- Ask Jarvis.
- Runtime status.
- Brain status.
- Memory status.
- Recent conversation.
- Semantic search.
- Model/runtime metadata.
- MartyBench run status.

Implementation target:

```text
api.py
ui-app/
ui/JarvisUI.tsx
```

---

### 3. Memory Review Commands Expansion

Status: Later

Potential commands:

```text
show memories by category
show hardware memories
show preference memories
show memories tagged <tag>
show recent semantic memories
```

Implementation target:

```text
skills/memory_summary_skill.py
skills/semantic_memory_skill.py
core/router.py
```

---

### 4. Voice Pipeline

Status: Later

Voice remains intentionally later.

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

Initial approach:

- Push-to-talk or terminal voice loop first.
- No wake word yet.
- Confirm transcription quality.
- Keep voice actions conservative.
- Only enable voice after brain/API behavior is stable.

---

### 5. Camera / Vision Pipeline

Status: Last

Vision remains after voice.

Initial approach:

- Snapshot-based image understanding first.
- No live video loop at first.
- Use vision only after brain and voice flows are stable.
- Keep vision separate from core memory until the capture/consent behavior is clear.

---

## Current Priority Order

Recommended next order:

```text
1. MartyBench scoring / report generation
2. API/UI dashboard pass
3. Memory review command expansion
4. Voice pipeline
5. Camera/vision pipeline
```

---

## Notes

Voice and camera are still deliberately last.

Jarvis is now in a stable local-first brain foundation state with repeatable context/brain regression checks and a working MartyBench v2 evaluation harness.
