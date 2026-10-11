# Farkle-2 Phase 8 Autonomous Benchmark Rerun

## Benchmark record

- Date: 2026-10-11
- Jarvis commit: `be0dc9f5cccf9ba2ab5db8de0575a7c924e0b1ee`
- Jarvis branch: `feature/jarvis-developer-agent`
- Farkle-2 baseline commit: `fc4e3922ed03064456898a5a0a214faf52fea220`
- Farkle-2 branch: `master`
- Final classification: `AGENT_REASONING_FAILURE`
- Phase 7 stopped reason: `invalid_model_output`

## Intentional benchmark defect

Before autonomous execution, the human/Codex operator added exactly one deterministic
test to `app/src/test/java/com/example/farkle2/FarkleScorerTest.kt`:

```kotlin
@Test
fun `four twos score 1000`() {
    assertEquals(1_000, FarkleScorer.score(listOf(2, 2, 2, 2)))
}
```

No production source was edited by the operator. The test is the only intentional
benchmark change and records the documented rule that four 2s score 1,000.

## Red baseline

The baseline used the registered `developer.gradle_test` capability, not arbitrary
Gradle execution. The capability ran the fixed offline task
`:app:testDebugUnitTest` through the reviewed Gradle 9.5.0 wrapper.

- Command family: `gradle_test`
- Infrastructure status: available and operating normally
- Exit code: 1
- Timed out: false
- Output truncated: false
- Tests: 7
- Passing: 6
- Failures: 1
- Errors: 0
- Skipped: 0
- Only failure: `four twos score 1000`
- Assertion: expected 1,000; actual 200

The original six tests remained green, so the failure was the intended scoring
defect rather than an infrastructure or unrelated regression.

## Bounded autonomous session

The rerun invoked the real `run_bounded_developer_session(...)` API. It did not
recreate the loop and did not provide a mock or replacement `model_call`.

Verification specification:

- Kind: `gradle_test`
- Project root: `/home/mnahtygal/projects/Farkle-2`
- Fixed task: `:app:testDebugUnitTest`

Candidate read files:

1. `app/src/main/java/com/example/farkle2/FarkleScorer.kt`
2. `app/src/test/java/com/example/farkle2/FarkleScorerTest.kt`

Allowed mutation path:

1. `app/src/main/java/com/example/farkle2/FarkleScorer.kt`

The benchmark test was readable but outside the mutation allowlist. The unchanged
Phase 7 ceilings were two repairs, three verification runs, two proposal requests,
five candidate files, and five mutation paths.

## Real llama.cpp execution

The session omitted `model_call`, so Phase 6 used its production default
`_default_model_call`, which invokes `get_llama_cpp_raw_response` against the real
local llama.cpp service. The backend returned non-empty output rather than raising
or returning empty data. Both allowed Phase 6 format attempts failed strict JSON
parsing, producing `invalid_model_output`. Raw prompts, model responses, and hidden
reasoning were not persisted.

## Autonomous attempt metadata

Attempt 1:

- Verification status: `verification_failed`
- Proposal request status: `invalid_model_output`
- Safe proposal type: `no_fix`
- Proposal path: none
- Safe normalized confidence: 0.0
- Mutation status: none
- Reverification status: not run

Session totals:

- Verification runs: 1
- Proposal requests: 1
- Live model calls: 2 format attempts
- Repairs applied: 0
- Changed paths: none
- Session success: false
- Stopped reason: `invalid_model_output`

The strict proposal gate stopped execution before conversion or
`developer.patch_file`. Because invalid model output is terminal in the current
Phase 7 orchestration, the unused outer repair and proposal limits were not treated
as permission to restart the session.

## Classification and final state

Classification: `AGENT_REASONING_FAILURE`

The model backend was reachable, the verification context was specific, both source
and test files were available, and the intended failure was deterministic. The
failure occurred when the live model did not produce valid schema-conforming JSON
after its bounded correction attempt. This is not a command-policy, scope, context,
or infrastructure block. The architecture nevertheless failed safely: no malformed
proposal reached mutation and no file outside scope changed.

No final green confirmation was run because the session did not report success.
The last verified test state remains 7 tests, 1 failure, 0 errors, and 0 skipped.

Source outcome:

- `FarkleScorer.kt`: unchanged
- `FarkleScorerTest.kt`: contains only the human-added benchmark test
- Test file autonomously modified: no
- Production code autonomously modified: no
- Production code manually modified: no
- Repairs applied: 0

The pre-existing `jarvis-build-session-v4.log` modification was not touched. Its
SHA-256 remained
`c7e1f31054bf77f2af0cba95635af0cd599495690a98c39b9c7872d07a53ab13`.

## Comparison with the original Phase 8 benchmark

The original benchmark ended at `COMMAND_POLICY_BLOCK`: Gradle verification could
not start, the model was not called, and no reasoning about a real test failure
occurred.

This rerun demonstrates additional autonomous capability. Jarvis independently:

- executed the fixed registered Gradle verification;
- observed a real, deterministic test failure;
- assembled bounded diagnostics and candidate source context;
- invoked the live llama.cpp repair path; and
- enforced strict proposal validation and stopped safely.

It did not produce a valid source repair, change production code, rerun verification
after a repair, or reach green. The original command-policy and fixture gaps are
therefore closed, while reliable structured repair generation by the active local
model remains unproven.

## Architecture limitation and recommendation

The observed limitation is structured-output reliability at the Phase 6 model
boundary. A malformed response is intentionally terminal, even when outer Phase 7
repair/proposal capacity remains.

The next step should be a separate human-reviewed investigation of llama.cpp JSON
schema adherence and bounded correction behavior. Preserve the current mutation
scope, command policy, evidence requirements, and Phase 7 hard limits; do not rescue
this benchmark by manually editing production code or loosening safety boundaries.

## Phase 8C follow-up

The historical rerun classification above remains `AGENT_REASONING_FAILURE`.
Phase 8C reproduced the failure without mutation and identified the exact cause:
both production-equivalent responses ended with `finish_reason=length` at 1,200
tokens while still inside an unclosed `<think>` block. They contained no completed
JSON object. This was truncation plus an incomplete thinking block, not Markdown,
surrounding final-answer prose, a backend outage, or parser over-strictness.

The remediation constrains generation with a fixed, internal-only GBNF grammar
equivalent to the existing three-variant repair JSON Schema, disables thinking for
repair calls, and uses deterministic repair-only sampling. The strict parser and
all semantic, path, patch, confidence, scope, and retry gates are unchanged. The
active llama.cpp server advertises JSON Schema response formats, but automatic
schema integration failed sampler initialization with the current Qwen chat
template; direct GBNF grammar sampling succeeded and remains generation-side.

Active inference configuration observed during the investigation:

- Model: `Qwen3-30B-A3B-Q4_K_M.gguf`
- Model path: `/home/mnahtygal/models/qwen3-30b/Qwen3-30B-A3B-Q4_K_M.gguf`
- Quantization: Q4_K_M
- Context size: 40,960 tokens
- llama.cpp build: `b9173-49d1701bd` (`49d1701bd24e4cedf6dfec9e50e185111203946b`)
- API: OpenAI-compatible `POST /v1/chat/completions` on port 8080
- Chat template: embedded Qwen template with Jinja enabled
- Server reasoning mode: `none`
- Previous repair profile: temperature 0.1, server-default top-p 0.95 and top-k
  40, repeat penalty 1.0, random seed, and 1,200 generated tokens
- Phase 8C repair profile: temperature 0.0, top-p 0.1, top-k 1, repeat penalty
  1.0, seed 0, prompt-cache reuse disabled, thinking disabled, and 1,200 generated
  tokens

Validation after the change:

- Generic real-model reliability: 5/5 strict-JSON parse successes
- Generic schema reliability: 5/5 exact-schema successes
- Generic source mutations: 0
- Farkle proposal-only result: valid accepted `patch_file`
- Farkle proposal path:
  `app/src/main/java/com/example/farkle2/FarkleScorer.kt`
- Farkle proposal confidence: 0.8
- Farkle mutations applied during Phase 8C: 0

Phase 8C did not rerun the autonomous benchmark and does not convert the historical
failure into a success. A separate explicitly approved rerun is required to test
whether the structured proposal can complete the bounded repair workflow.
