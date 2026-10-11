# Farkle-2 Phase 8 Autonomous Developer Benchmark

## Benchmark record

- Date: 2026-10-11
- Jarvis commit: `9cc3d30b0bdf1c80514d7d233a46fb0e34accd3b`
- Jarvis branch: `feature/jarvis-developer-agent`
- Farkle-2 path: `/home/mnahtygal/projects/Farkle-2`
- Farkle-2 starting commit: `7cae8981c6fb91ffc2d93dabb7c234ff800de2d4`
- Farkle-2 branch: `master`
- Final classification: `COMMAND_POLICY_BLOCK`

## Initial project inspection

The target repository contained six tracked files:

- `app/build.gradle`
- `app/settings.gradle`
- `jarvis-build-session.log`
- `jarvis-build-session-v2.log`
- `jarvis-build-session-v3.log`
- `jarvis-build-session-v4.log`

There was no README, standalone specification, source directory, Android manifest,
test source, root Gradle configuration, Gradle wrapper, or prior machine-readable
benchmark result. The four session logs were the only requirements and development
history artifacts.

The repository began with a pre-existing modification to
`jarvis-build-session-v4.log`. That log change was not made or repaired during this
benchmark. The committed and working copies of `app/build.gradle` were identical:
an incomplete Markdown-fenced Gradle snippet ending inside an unterminated
dependency declaration. `app/settings.gradle` was empty.

The available `developer.run_command` baseline observations were:

- `pwd`: passed and confirmed the Farkle-2 workspace.
- `git status --short --branch`: passed and reported the pre-existing modified log.
- `git diff --check`: failed on trailing whitespace in the pre-existing log change.
- `gradle test`: rejected with `executable_not_allowed`.
- `./gradlew test`: rejected with `executable_not_allowed`.

The host also had no `gradle` executable, and the repository had no `gradlew` or
Gradle wrapper files. There were zero discoverable tests, so no passing/failing test
count or compile/build result could be established. The application was not in a
buildable or runnable state.

## Recovered requirements

The original session logs specify an independent native Android application named
Farkle-2 with six-dice gameplay, selectable scoring dice, visually distinct held
dice, banking, Farkle loss of unbanked points, held scoring dice, Hot Dice, turn and
total scores, New Game, and persisted game state.

The explicitly recorded scoring requirements are:

- Single 1: 100
- Single 5: 50
- Three 1s: 1000
- Three 2s through three 6s: 200 through 600 respectively
- Four of a kind: 1000
- Five of a kind: 2000
- Six of a kind: 3000
- Straight 1-2-3-4-5-6: 1500
- Three pairs: 1500
- Two triplets: 2500

No requirements were invented beyond those logs.

## Selected bounded task and scope

Because no game source or tests existed, a scoring or state-transition repair could
not be selected honestly. The smallest meaningful prerequisite task was:

> Validate and repair the existing Android Gradle configuration enough for the
> project's unit-test command to begin.

The explicitly approved Phase 7 session scope was:

- Verification command: `./gradlew test`
- Candidate read files:
  - `app/build.gradle`
  - `app/settings.gradle`
- Allowed mutation paths:
  - `app/build.gradle`
  - `app/settings.gradle`
- Maximum repairs: 2
- Maximum verification runs: 3
- Maximum proposal requests: 2

The candidate and mutation sets were fixed before execution and contained no log,
Git metadata, or unrelated path. Approval applied only to this one session.
The unchanged Phase 7 hard ceilings were two repairs, three verification runs, two
proposal requests, five candidate files, and five mutation paths. Each Phase 6
proposal request retained its separate two-call format-retry ceiling, giving a
theoretical session maximum of four model calls. This session used only two of the
five permitted candidate and mutation paths.

## Autonomous session result

The benchmark called the real `run_bounded_developer_session(...)` API with
`approved=True`. It did not reproduce the loop manually and supplied no mock model
callback.

Attempt 1:

- Verification result: `verification_policy_rejected`
- Underlying command-policy error: `executable_not_allowed`
- Proposal status: none
- Proposal type: none
- Proposal path: none
- Proposal confidence: none
- Mutation result: none
- Reverification: not run

Final safe result:

- Success: false
- Verification runs: 1
- Proposal requests: 0
- Model calls: 0
- Repairs applied: 0
- Mutations attempted: 0
- Changed paths: none
- Stopped reason: `verification_policy_rejected`

The default real llama.cpp proposal path was available to the API, but it was not
invoked because Phase 7 correctly stopped before source reads or proposal generation
when the verification command failed policy validation. Therefore this run does not
claim live inference occurred.

## Before and after

Before:

- Tests: none present; 0 passing and 0 failing could be measured.
- Build: not runnable through Developer Agent policy.
- Source: no application source existed.
- Git status: pre-existing modification to `jarvis-build-session-v4.log`.

After:

- Tests: unchanged; none present.
- Build: still blocked.
- Source: unchanged.
- Farkle-2 changed files from this benchmark: none.
- Git status: the same pre-existing modified log only.

Jarvis initiated verification itself through the actual Phase 7 session and existing
executor. Jarvis did not modify code, repair a failure, stage, commit, or push. The
human supervising operator did not manually edit Farkle-2 code.

## Classification and findings

Classification: `COMMAND_POLICY_BLOCK`

This is a safe boundary result, not a failure of the Phase 7 safety architecture.
The required Android verification command is outside the current fixed command
policy, and Phase 7 stopped immediately without reading source, calling the model,
or mutating files. The benchmark was blocked by command policy before repair
reasoning could begin. It must not be classified as an agent reasoning failure.

Additional target-infrastructure limitations are material: even if command policy
were broadened, this checkout has no Gradle wrapper, installed Gradle executable,
root project configuration, source, manifest, or tests. Allowing the command alone
would not make this repository benchmark-ready.

What Jarvis did correctly:

- Bound approval to one static command and two explicit files.
- Used the real Phase 7 session and existing executor.
- Enforced command policy before model or mutation work.
- Stopped safely with bounded metadata.
- Left both repositories' pre-existing content untouched.

Where Jarvis could not yet demonstrate capability:

- No live repair proposal was generated.
- No source change was applied.
- No build or test suite ran.
- Iterative repair reasoning was not exercised.

No prompt, raw model response, chain-of-thought, source excerpt, or failure payload
was persisted in the Phase 7 result.

## Repository validation

Jarvis remained at commit `9cc3d30b0bdf1c80514d7d233a46fb0e34accd3b`.
No Developer Agent framework, test, capability, planner, router, Brain, or protected
personal file changed. Its only worktree addition is this intentionally uncommitted
benchmark report under `docs/benchmarks/`.

Farkle-2 remained at commit `7cae8981c6fb91ffc2d93dabb7c234ff800de2d4`.
Its final status contains only the same pre-existing modified
`jarvis-build-session-v4.log`. Neither approved mutation path differs from `HEAD`.
`git diff --check` still fails exclusively on trailing whitespace in that pre-existing
log change; the benchmark did not repair or worsen it.

## Comparison with the original Farkle-2 finding

The original Farkle-2 session showed that Jarvis could discuss requirements,
architecture, code, and commands but could not modify files, execute verification,
or repair failures itself.

Phase 8 shows partial architectural progress: Jarvis can now accept a human-approved
bounded session and independently attempt verification through a controlled tool.
For this Android target, however, the three practical gaps remain unproven rather
than closed: no project verification executed, no file was modified, and no failure
was repaired. The stop occurred at the intended command-policy boundary.

## Recommended next action

Proceed in this order:

1. Build a valid, deterministic Farkle-2 benchmark fixture under human review,
   including a self-contained Gradle wrapper and unit-test target.
2. Design one narrowly scoped, offline Gradle verification capability without
   broadening generic command execution.
3. Rerun the benchmark without loosening any Phase 7 autonomy limit.
