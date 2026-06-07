# Jarvis Brain Next Steps

## Purpose

This file is the working roadmap for getting the Jarvis brain where it needs to be without losing track of progress.

Jarvis is now running on the NVIDIA Jetson AGX Thor with local llama.cpp model serving, PostgreSQL, pgvector semantic memory, local/offline embeddings, startup services, health checks, deterministic routing, exact-memory routing, MartyBench v2, context regression testing, brain regression testing, a combined regression check script, and MartyBench score reporting.

The current phase is reliability, repeatable evaluation, dynamic runtime awareness, UI/API polish, and preparing for the next major capabilities.

---

## Current Stable State

Completed and working:

- Thor is the primary Jarvis platform.
- Qwen3 30B runs locally through llama.cpp.
- DeepSeek-R1-Distill-Qwen-7B also runs locally through llama.cpp for testing/comparison.
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
- Semantic memory is injected into normal Jarvis context.
- Semantic memory uses weighted ranking.
- Runtime/project identity responses are deterministic, but current model identity still needs to become dynamic.
- Common exact-memory questions avoid LLM fallback.
- Context assembly has a dedicated regression test.
- Brain behavior has a dedicated regression test.
- Combined regression check works:

```bash
./scripts/regression_check.sh
```

- MartyBench v2 benchmark runner works.
- MartyBench latest report tool works.
- MartyBench score summary template generation works.
- MartyBench score report parsing works.
- Generated benchmark result outputs are ignored by Git.
- Jarvis CLI launcher works.
- Health check works.
- UI runs after Node 22 update.
- GitHub SSH works from Thor.

---

## Current Brain Flow

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
llama.cpp / active local model
  ↓
Jarvis response
```

Important note:

Not every command reaches the LLM. Known deterministic questions are handled by router/skills first.

Benchmark exception:

- MartyBench v2 uses a raw llama.cpp path without normal Jarvis memory/context injection.
- This keeps benchmark evaluation isolated from personal Jarvis memory unless synthetic benchmark memory is explicitly injected.

---

## Completed Build Items

### 1. Brain Status Command

Status: Complete

Command:

```text
brain status
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

---

### 4. Better Memory Answer Rules

Status: Complete

Jarvis follows these memory-answer rules:

- If an answer comes from exact memory, Jarvis says it is based on saved memory when useful.
- If an answer comes from semantic memory, Jarvis says it is based on saved semantic memory or what Marty told it when useful.
- If no saved memory exists and no approved external source exists, Jarvis avoids inventing current facts.
- Runtime/project identity questions are deterministic and do not require LLM fallback.
- Common exact-memory questions answer directly without LLM fallback.

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

---

### 8. MartyBench v2 Baseline

Status: Complete

MartyBench v2 includes:

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

Current Qwen3 30B / llama.cpp / Thor baseline scores:

```text
basic    33/35 Pass
messy    33/35 Pass
conflict 34/35 Pass
memory   34/35 Pass
```

---

### 9. MartyBench Reporting Tools

Status: Complete

Completed reporting work:

- Latest-run report tool added.
- Variant filter works.
- `latest_report.md` generation works.
- `score_summary.md` template generation works.
- Score report parser added.
- Score report rollup works.
- Latest and best scored runs are shown by variant.
- All scored/unscored runs are listed.

---

## Immediate Next Build Items

### 1. Dynamic Model Identity and Safe Model Switching

Status: Next

Goal:

Keep Qwen3 30B as the default Jarvis model, preserve DeepSeek as a selectable secondary model, and ensure Jarvis reports the model actually loaded by llama.cpp.

Checklist:

```text
[ ] Read active model dynamically from llama.cpp /v1/models
[ ] Remove hard-coded Qwen3-only identity from runtime responses
[ ] Make brain status and runtime identity use the same active-model source
[ ] Add a model registry/config for Qwen3 and DeepSeek
[ ] Keep Qwen3 30B as default Jarvis model
[ ] Keep DeepSeek-R1-Distill-Qwen-7B as selectable comparison/test model
[ ] Add safe model switch command/script
[ ] Prevent two llama.cpp servers from colliding on port 8080
[ ] Verify service startup still defaults to Qwen3
[ ] Add regression coverage for dynamic model identity
[ ] Re-run MartyBench against DeepSeek for comparison later
```

Implementation targets:

```text
skills/runtime_skill.py
skills/brain_status_skill.py
skills/llama_cpp_skill.py
scripts/
systemd service/config
```

Expected result:

```text
what model are you using
brain status
```

must always agree with the model returned by:

```text
http://127.0.0.1:8080/v1/models
```

---

### 2. API/UI Dashboard Pass

Status: Next after model switching

Goal:

Make the frontend/API useful as a real Jarvis dashboard.

Potential dashboard sections:

- Ask Jarvis.
- Runtime status.
- Brain status.
- Memory status.
- Recent conversation.
- Semantic search.
- Model/runtime metadata.
- MartyBench run status.
- Active model and model-switch status.

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

---

### 4. Voice Pipeline

Status: Later

Voice remains intentionally later.

---

### 5. Camera / Vision Pipeline

Status: Last

Vision remains after voice.

---

## Current Priority Order

```text
1. Dynamic model identity and safe model switching
2. API/UI dashboard pass
3. Memory review command expansion
4. Voice pipeline
5. Camera/vision pipeline
```

---

## Notes

Voice and camera are still deliberately last.

Jarvis is now in a stable local-first brain foundation state with repeatable context/brain regression checks, a working MartyBench v2 evaluation/reporting harness, and a new multi-model runtime direction.
