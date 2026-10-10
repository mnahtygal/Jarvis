# Jarvis Developer Agent

## Purpose

The Developer Agent is a controlled, local-first tool boundary for future software
development workflows. Phase 1 provides read-only inspection. Phase 2 adds two
explicit, bounded file-mutation tools. Phase 3 adds a confirmation-gated command
boundary with fixed command grammars, not a generic shell. Phase 4 adds a bounded,
confirmation-gated verify/repair/reverify orchestrator for predefined repairs.

Brain v2 advertises these capabilities, but does not invoke them from natural
language or run an autonomous tool loop.

## Architecture

The implementation is intentionally small:

- `core/developer_agent/tool_models.py` defines immutable tool results.
- `core/developer_agent/workspace.py` owns the shared workspace boundary and
  `core/developer_agent/policy.py` owns sensitive/protected path rules.
- `core/developer_agent/command_policy.py` owns the fixed executable and argument
  allowlist for command execution.
- `core/developer_agent/registry.py` contains a fixed tool registry.
- `core/developer_agent/executor.py` validates arguments and uses a fixed dispatch
  table.
- `core/developer_agent/repair_loop.py` sequences approved verification commands
  and predefined repairs through that executor with hard attempt limits.
- `core/developer_agent/mutation.py` provides shared atomic-write behavior.
- `core/developer_agent/tools/` contains the fixed tool implementations.
- `core/capability_registry.py` advertises the matching Brain v2 capabilities.

There is no dynamic registration, dynamic import, `eval`, `exec`, or generic shell
tool. Command requests are argv lists and never parsed as command strings.

## Phase 1 tools

### `developer.list_files`

Lists a directory inside the workspace. Results are sorted and bounded. Recursive
listings skip `.git`, `.venv`, `__pycache__`, `node_modules`, `build`, and `dist`
unless one of those directories is explicitly selected as the listing root.
Each visited directory also has a fixed scan ceiling, preventing a single unusually
large directory from consuming unbounded memory before sorting.

### `developer.read_file`

Reads bounded UTF-8 text and returns line-numbered output. It refuses directories,
binary or invalid UTF-8 files, and explicitly sensitive names: `.env`, `.env.*`,
`*.pem`, `*.key`, `credentials*`, and `secrets*`.

### `developer.git_status`

Runs only this fixed argument vector with a timeout and captured output:

```text
git status --short --branch
```

It uses the workspace root as its working directory, never enables a shell, and
sets `GIT_OPTIONAL_LOCKS=0` to prevent optional index refresh writes.

## Phase 2 tools

Phase 2 tools are enabled for explicit calls through the developer executor. Both
are marked mutating, non-read-only, and `requires_confirmation=True`. They are
marked `executable=False` for autonomous planning. No interactive confirmation UI
exists yet; a future caller must enforce a confirmation or policy gate before any
autonomous invocation.

### `developer.write_file`

Creates bounded UTF-8 text files. Existing files are refused unless
`overwrite=True`, and missing parent directories are refused unless
`create_parent_dirs=True`. Existing targets must already be bounded UTF-8 text;
binary files are not overwritten.

### `developer.patch_file`

Performs literal, case-sensitive text replacement without regular expressions,
fuzzy matching, or arbitrary diff application. `old_text` must be non-empty. The
actual exact match count must equal `expected_matches` (default `1`) or the file is
left byte-for-byte unchanged.

## Workspace and security model

The default approved root is the Jarvis repository containing the implementation.
A caller may construct a `Workspace` with another explicit project root for tests
or controlled embedding.

Every filesystem tool resolves the requested path and all symlinks before checking
containment. Absolute paths and `..` paths are accepted only when their resolved
destination remains inside the configured root. Escapes to a home directory,
`/etc`, `/proc`, or any other external location are rejected. Recursive listing
does not follow symlinks outside the root.

Tool results contain stable error codes and safe messages; raw exceptions are not
returned. File reads, line ranges, directory output, Git output, and subprocess
duration are bounded.

Mutation additionally refuses `.env*`, `*.pem`, `*.key`, `credentials*`,
`secrets*`, every path beneath `.git/`, and the three protected personal audio
tester filenames. `.gitignore` remains editable. Content and patch payload sizes
are bounded.

Successful mutations write a temporary file in the validated target directory,
flush and sync it, revalidate containment and protection immediately before the
mutation, and atomically link or replace the target. Existing file modes are
preserved. Concurrent changes detected during patching or overwrite validation
cause a safe refusal.

## Phase 3 command tool

### `developer.run_command`

Runs only policy-approved argv vectors at the fixed workspace root. It is enabled
for explicit executor calls but is marked mutating, `requires_confirmation=True`,
and `executable=False`. Brain v2 advertises the same manual-only capability. No
planner mapping, natural-language route, retry loop, or autonomous invocation is
present.

Allowed command forms are:

```text
pwd
git status --short --branch
git diff
git diff --check
git diff --cached
git diff --cached --check
git branch --show-current
python|python3 -m pytest [approved options and workspace targets]
pytest [approved options and workspace targets]
python|python3 -m compileall [-q] <workspace paths...>
python|python3 -m py_compile <workspace Python files...>
```

Git arguments must exactly match one of the listed read-only forms. Python accepts
only `-m` followed by `pytest`, `compileall`, or `py_compile`; `-c`, stdin, script
paths, arbitrary modules, and interpreter flags are rejected. The standalone
`pytest` spelling is translated to the current trusted Python interpreter. Pytest
allows only a small option set used for repository verification, validates all
test and ignore paths inside the workspace, disables third-party plugin autoload,
uses fixed workspace root/config boundaries, and ignores ambient `PYTEST_ADDOPTS`
and `PYTHONPATH` values. Safe-path mode prevents workspace files from shadowing the
approved `pytest`, `compileall`, or `py_compile` modules. Compileall additionally
ignores symlinks whose targets leave the workspace.

Executables are selected by policy rather than by a user-supplied path. Python
uses the interpreter already running Jarvis. Git and `pwd` resolve only from the
fixed system path `/usr/local/bin:/usr/bin:/bin`. Absolute executable paths and
alternate spellings are rejected.

The child receives no stdin, always runs with the workspace root as `cwd`, and
gets a minimal environment containing only a fixed `PATH`, workspace-scoped
`HOME`, UTF-8 locale settings, a safe active-virtualenv marker when applicable,
and command-specific safety variables. Git uses `GIT_OPTIONAL_LOCKS=0`, disables
global/system configuration, prompts, pagers, filesystem-monitor helpers, external
diff drivers, and text conversion commands.

The default timeout is 60 seconds and the hard maximum is 300 seconds. A timed-out
child is terminated, then killed if it does not exit during the bounded grace
period. Stdout and stderr are drained independently so a full pipe cannot deadlock
the process. Their combined in-memory capture defaults to 128 KiB and cannot
exceed 1 MiB; excess output is discarded while byte counts and truncation metadata
are retained. Results expose separate captured streams, exit status, timeout state,
byte counts, truncation state, and command family without returning raw exceptions.

Shell syntax, argument files, unknown executables, user-controlled `cwd` or
environment, pytest plugin/config injection flags, mutation-capable Git commands,
package installers, network clients, privilege tools, file mutation utilities,
service/process controls, and unrestricted interpreters are rejected.

## Phase 4 repair loop

`run_repair_loop(...)` is an explicit Python API for a controlled sequence:

```text
verify -> apply one predefined repair -> reverify -> stop or repeat
```

The caller supplies one verification argv list and the complete ordered repair
sequence. Every repair is a fully specified `developer.patch_file` or
`developer.write_file` request. The loop decides only when to apply the next
repair; it does not generate paths, source text, patch bodies, or fixes. There is
no LLM interpretation or LLM-generated repair in Phase 4.

The API validates the complete request before execution, rejects unknown fields
and tool IDs, and requires `approved=True` before running even the initial
verification. The hard limits are three repair attempts and four verification
runs (initial verification plus at most three reverification cycles). Callers may
choose a lower repair limit but cannot raise it. A deterministic fingerprint
prevents applying the same supplied repair twice in one loop.

Verification always calls `developer.run_command`, so the Phase 3 argv grammar,
workspace checks, timeout, environment, and output bounds remain authoritative.
Mutation always calls the existing developer executor and its `patch_file` or
`write_file` implementation, preserving all workspace, protected-path, size, and
atomic-write policies. The loop has no direct subprocess or filesystem mutation
path and cannot dispatch Git mutation, package management, network, deletion, or
shell tools.

The loop stops on verification success, rejected or timed-out verification,
rejected or failed repair, exhausted repairs, a duplicate repair, the attempt
limit, or an unexpected executor failure. Its immutable result contains only safe
summary metadata: status, counts, per-cycle outcomes, and the final exit code. It
does not retain command output, source contents, patch bodies, or raw exceptions.

Brain v2 advertises `developer.repair_loop` as enabled, mutating,
`requires_confirmation=True`, and `executable=False`. There is no planner mapping,
natural-language route, interactive confirmation UI, or autonomous Brain entry
point. Phase 4 remains a manual/internal API whose caller must explicitly approve
the supplied sequence.

## Execution limitations

Phase 2 can create or replace text only through the two explicit mutation tools.
Phase 3 commands can run tests and bytecode compilation, which may create ordinary
workspace artifacts such as `__pycache__` and `.pytest_cache`; this is why the
generic command capability remains classified as sensitive and mutating even
though its Git subset is read-only. It cannot delete files or directories, change
permissions, install packages, stage, commit, or push. The executor allows only
fixed registered IDs and arguments. Phase 4 adds only the bounded, predefined
sequence described above; it does not provide generated self-correction, planning,
or natural-language invocation.

This command policy is a constrained developer workflow boundary, not an operating
system sandbox. An approved pytest command necessarily imports and executes the
selected workspace tests and local `conftest.py` files. The policy prevents using
the command API to select arbitrary interpreters, modules, plugins, executables,
working directories, or environments; it does not make repository test code
non-executable. Explicit confirmation and trusted workspace contents are therefore
required before a caller invokes pytest.

Allowed examples:

```python
execute_tool("developer.list_files", {"path": "core", "recursive": False})
execute_tool("developer.read_file", {"path": "README.md", "start_line": 1, "end_line": 20})
execute_tool("developer.git_status", {})
execute_tool("developer.write_file", {"path": "notes/todo.md", "content": "TODO\n", "create_parent_dirs": True})
execute_tool("developer.patch_file", {"path": "notes/todo.md", "old_text": "TODO", "new_text": "DONE"})
execute_tool("developer.run_command", {"argv": ["python", "-m", "pytest", "-q", "tests/test_developer_agent.py"]})
```

Rejected examples include `../` or symlink escapes, `/etc/passwd`, `.env`, binary
files, protected audio tester files, Git metadata, unknown tool IDs, unsupported
arguments, shell command strings, `python -c`, arbitrary Python modules, absolute
executable paths, pytest plugin injection, and Git mutation commands.

## Roadmap

- Phase 1: bounded read-only repository inspection
- Phase 2: confirmation-sensitive file mutation tools
- Phase 3: constrained verification command execution
- Phase 4: bounded verify/repair/reverify loop using predefined repairs
- Phase 5: controlled Git commit
- Phase 6: LLM-assisted repair proposal and constrained developer reasoning
- Phase 7: Farkle-2 autonomous benchmark

Each later phase requires a separate security design and validation. Phase 5 and
beyond are not currently available.
