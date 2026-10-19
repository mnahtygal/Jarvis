# Jarvis Roadmap

Last updated: 2026-10-19

Jarvis now has two deliberate tracks: the Maker/Workshop product track and the
Developer Agent engineering track. They share the same local-first principle but
should not be mixed into one giant autonomy project.

## Track A — Maker & Workshop Assistant

### Foundation — Complete

- Thor local model runtime
- PostgreSQL + pgvector memory
- Brain/router foundation
- React/Vite UI
- voice and vision pipelines
- role-based cameras and microphone resolution
- startup/status tooling

### Measurement validation — Current

The software foundation for single-object rotated measurement and Accuracy v2 is
implemented. The next meaningful milestone is physical validation against known
reference objects.

Exit criteria:

- repeatable measurements on a small set of known objects
- recorded ruler/caliper ground truth
- error reported in mm and percent
- calibration provenance preserved
- failure/ambiguity states remain explicit

### Next maker milestones

1. Multi-object/internal-feature measurement
2. Diameter-specific fitting
3. Scan history and project memory
4. Conservative OpenSCAD starter generation
5. Maker Lab project workspace

## Track B — Developer Agent

### Controlled tools — Complete

- read/list/status tools
- explicit write/patch tools
- constrained verification commands
- offline Gradle verification boundary
- controlled local Git stage/commit tools
- strict structured repair proposals
- bounded developer sessions

### Isolated Python repair — Complete milestone

On 2026-10-19 Thor passed the live isolation suite and the existing-project stock
repair benchmark.

Current bounded Python session guarantees include:

- deterministic recognition of the canonical request grammar
- separate exact approval turn
- static source/test/verification scope
- maximum 2 repairs
- maximum 3 verification runs
- maximum 2 proposal requests
- disposable read-only candidate workspace
- disconnected network namespace
- AppArmor-gated user namespace creation
- Bubblewrap filesystem/process isolation
- no test mutation
- exact passing-byte sealing before promotion
- no automatic Git operation

### Next Developer Agent milestone

Improve usability and reliability **without widening authority**:

- expose a clearer bounded-session UI/CLI entry so users do not need to remember
  the canonical natural-language grammar
- add concise diagnostics when recognition fails
- add another small existing-project benchmark with a different bug shape
- retain the same hard safety limits unless a separate design review approves a
  change

Only after those are stable should we consider broader multi-file repair scopes.

## Deferred

Do not prioritize yet:

- unrestricted shell access
- package installation from the Developer Agent
- autonomous Git push
- recursive/self-spawning agents
- unrestricted multi-file mutation
- cloud dependency for core operation
- complex multi-agent orchestration
- robotics/autonomous camera movement
- replacing PostgreSQL memory
