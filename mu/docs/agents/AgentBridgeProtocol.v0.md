<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-09-01
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Agent Bridge Protocol v0

Purpose: define the minimal working protocol for configured reader/reviewer collaboration inside RCX.

## Why This Exists

Founder relay is reliable but expensive.
Bridge v1 reduces manual copy/paste while keeping the current RCX review doctrine intact:
- one writer
- one reviewer
- evidence-first claims
- git truth over agent summaries

## Architecture

Bridge v1 has 3 parts:
1. `tools/agents/bridge_supervisor.py`
2. SQLite bus at `.agent_bus/bridge.db`
3. local command adapters defined in `.agent_bus/bridge_config.json`

`AGENT_BRIDGE.md` is the tracked operator entrypoint.
It is not the runtime transcript ledger.

## Roles

- `reader`: primary task agent; may edit when the job allows edits
- `reviewer`: read-only skeptic; reviews the live candidate state
- `supervisor`: owns job state, prompts, validations, transcript rendering, and git-state truth

Reader and reviewer identities are configured per job. Identity selects the
recorded role context; reader execution mode is separate authority and is not
inferred from a provider name for newly created hybrid jobs.

## Runtime Layout

Untracked runtime state:

```text
.agent_bus/
  bridge.db
  bridge_config.json
  prompts/
  raw/
  rendered/
  validations/
```

Tracked implementation files:

```text
tools/agents/bridge_supervisor.py
tools/agents/bridge_schema.sql
tools/agents/bridge_adapters.py
tools/agents/templates/bridge_reader_prompt.txt
tools/agents/templates/bridge_reviewer_prompt.txt
tools/agents/bridge_config.example.json
```

## SQLite Schema

Tables in v1:
- `jobs`
- `turns`
- `validations`
- `job_actions` (append-only job-level authority markers)
- `schema_version`

This is intentionally minimal.
`findings` and `leases` stay out of v1.
The envelope JSON is stored on `turns` so the supervisor can render transcripts without inventing a second model.

## Job Lifecycle

1. `init`
- create runtime dirs and SQLite DB
- copy example config if local config is missing

2. `submit`
- create a job with task text, role names, edit permission, max rounds, and acceptance checks

3. `run`
- compute repo state
- prompt reader
- run validations
- if `--pause-after-reader`: enter `AWAITING_REVIEWER_APPROVAL` and return `PAUSED` (founder intervention point)
- prompt reviewer
- stop on `GO`, `NO_GO`, or `QUESTION`
- rerender transcript after each turn
- `--verbose` / `-v`: print step events to stdout and stream agent output live (tee to terminal + raw file)

4. `continue <job_id>`
- resume a paused job from `AWAITING_REVIEWER_APPROVAL`
- only valid when job status is `AWAITING_REVIEWER_APPROVAL`; raises error otherwise
- runs reviewer to completion
- `--verbose` / `-v`: same streaming behavior as `run`

5. `review`
- hybrid mode: record the configured reader's implementation context as a synthetic turn, then run the configured reviewer
- combines `submit` + synthetic reader + validations + reviewer in one command
- `--task` / `--task-file`: what the task was
- `--summary` / `--summary-file`: what the reader (interactive session) did
- `--reader`: which configured identity supplied the synthetic implementation context
- `--reviewer`: which adapter reviews (default: `codex`)
- `--wave-class`, `--check`, `--job-id`: same as `submit`
- `--verbose` / `-v`: print structured envelope output inline (findings, decision, evidence)
- `--no-diff`: omit git diff from reviewer prompt; use for design deliberation, questions, or non-code review where the diff would distract from the task content
- the configured reader identity is recorded; touched files are auto-detected from git, and no reader adapter is invoked
- designed for a configured implementer to supply context and a separately configured reviewer to review independently
- also supports design deliberation: pass a proposal via `--task-file` with `--no-diff` for non-code dialectic

Hybrid job creation writes the configured reader identity and a separate
job-level synthetic-reader execution-mode marker in the same durable
transaction. Normal execution and crash recovery consult that marker before
reader-adapter lookup, so a hybrid job remains synthetic even if interrupted
before its reader turn is materialized and regardless of the configured reader
identity. For unmarked historical jobs only, the supervisor retains the legacy
`claude-session` identity and completed-synthetic-turn fallbacks.

6. `status` / `render`
- inspect or regenerate the human-readable transcript

## Prompt Contract

Both agents must return normal prose plus a JSON envelope delimited by:

```text
BEGIN_AGENT_ENVELOPE
{ ... }
END_AGENT_ENVELOPE
```

Required keys:
- `job_id`
- `turn_id`
- `agent_role`
- `decision`
- `summary`
- `touched_files_claimed`
- `findings`
- `validations_claimed`
- `request_for_next_agent`

Candidate evidence authority is repo-tracked: governing task packets, live
candidate files, tests, and documentation, together with supplied receipts and
focused repo-local probes permitted by the active review contract. Provider-local
memory is not candidate evidence authority.

## Decisions

Supported decisions in v1:
- `GO`
- `NO_GO`
- `REQUEST_CHANGES`
- `QUESTION`
- `STALE`
- `ERROR`
- `SYNTHETIC` — used for hybrid review mode: the reader envelope is auto-generated (not from an agent) to indicate a synthetic pass-through

Supervisor behavior:
- `GO` => terminal success
- `QUESTION` => founder stop
- `NO_GO` => terminal no-go
- `REQUEST_CHANGES` => next reader round if rounds remain
- `STALE` => rerun reviewer
- `ERROR` => terminal failure
- `SYNTHETIC` => non-terminal; synthetic reader envelope in hybrid review (carries `"synthetic": true` flag)
- `PAUSED` => returned by `run` when `--pause-after-reader` is active; job enters `AWAITING_REVIEWER_APPROVAL`

## Job States

| State | Meaning |
|-------|---------|
| `READY_READER` | Job created or ready for next reader round |
| `READER_RUNNING` | Reader agent is executing |
| `AWAITING_REVIEWER_APPROVAL` | Ready for reviewer — set by explicit `--pause-after-reader` or by crash recovery |
| `REVIEWER_RUNNING` | Reviewer agent is executing |
| `AWAITING_FOUNDER` | Terminal `QUESTION` from agent; founder must decide |
| `DONE` | Terminal state (`GO`, `NO_GO`, or `ERROR`) |

## Crash Recovery

If the supervisor is interrupted mid-turn, the next `run` invocation detects incomplete state and recovers:
- `READER_RUNNING` with no completed reader turn: resets to previous round and reruns reader
- `READER_RUNNING` with completed reader turn: reruns validations (may have been incomplete) and advances to reviewer
- `REVIEWER_RUNNING` with completed reviewer turn: checks staleness (state_sha_start vs state_sha_end); if state changed during execution, marks turn stale and retries; otherwise applies the recorded decision without rerunning
- `REVIEWER_RUNNING` with no completed reviewer turn: resumes at reviewer

Before any recovered or normal reader dispatch, the supervisor checks the
durable synthetic-reader execution-mode marker. A marked job fails closed
before adapter lookup unless it can resume through its completed synthetic turn,
validations, or reviewer phase. Historical unmarked jobs retain the legacy
compatibility fallbacks described above.

In all cases, recovery sets `AWAITING_REVIEWER_APPROVAL` before entering the reviewer phase, which is the same state used by explicit `--pause-after-reader`. The `continue` command accepts any job in `AWAITING_REVIEWER_APPROVAL` regardless of how it got there (pause or recovery). Use `run` to trigger crash detection and recovery from `READER_RUNNING` or `REVIEWER_RUNNING` states.

## Verbose Output And Streaming

When `--verbose` / `-v` is used with `run`, `continue`, or `review`, the supervisor:
1. Prints `[bridge]` step events (round start, agent start/finish, validation results)
2. Prints structured envelope after each agent turn: decision, full summary, all findings with severity/file/evidence, touched files, and request_for_next_agent
3. Streams agent stdout/stderr live to the terminal via tee (output is simultaneously captured for the raw output file, including both stdout and stderr sections)

Without `--verbose`, agents run with fully buffered capture and no inline envelope display. In both modes, stderr is drained concurrently (thread-based) to prevent deadlock when agents write heavily to stderr, and is appended as a `[stderr]` section in the raw output file.

**Streaming limitations:** `claude --print` buffers all output until the response is complete — no incremental tokens appear during execution. Codex streams line-by-line. When the bridge is invoked from within the Claude Code Bash tool, all output appears only after the command finishes regardless of streaming. The streaming feature delivers its full value when the bridge is run from a standalone terminal shell.

## Git Truth And Staleness

The supervisor records actual changed files from git, not from agent claims.

Repo state hash is derived from:
- `HEAD`
- staged diff
- unstaged diff
- untracked files

Ignored for state hashing:
- `.agent_bus/`
- `.git/`
- `.scratch/`
- cache/venv noise

If repo state changes during reviewer execution, the review is stale and must be rerun.

## Validation Policy

Built-ins in v1:
- `git status --short`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged` when present

Plus any acceptance checks supplied at submission time.

**Validation whitelist:** Acceptance checks are executed via `shell=False` (subprocess with argv list) for security. Only commands in the `VALIDATION_WHITELIST` dict in `bridge_supervisor.py` are allowed. Unknown `--check` values are rejected at submit time (before the job is created) with a `BridgeError` listing known commands. As defense-in-depth, unknown commands encountered at run time are recorded as failed validations. All validation subprocesses run with `PYTHONHASHSEED=0` in the environment. To add a new validation command, add it to `VALIDATION_WHITELIST`.

## Adapter Contract

`.agent_bus/bridge_config.json` declares named adapters under `agents`.

The shipped configuration includes a `claude` adapter verified for Claude Code
CLI (`claude --print` with stdin piping) and a `codex` adapter using
`codex exec - --sandbox danger-full-access`. These are adapter implementation
examples, not role assignments: configured job context determines reader and
reviewer identities. Synthetic reader execution mode suppresses reader-adapter
lookup independently of that identity. The reviewer role contract (read-only,
no source edits) is enforced by the prompt, not by adapter naming or sandbox.

Each adapter defines:
- `cmd`
- `prompt_via_stdin`
- `timeout_s`
- optional `env`
- `mode`

Only `mode: live` is supported in v1.
Snapshot/worktree modes are deferred.

## Concurrency

Only one bridge supervisor process may run at a time per repo. Enforced via exclusive file lock on `.agent_bus/bridge.lock` (`fcntl.flock`). A second `run` invocation while a supervisor holds the lock will fail immediately.

## Out Of Scope

Bridge v1 does not include:
- background daemon mode
- watchman/file watching
- snapshots or worktrees
- dual-writer coordination
- cost accounting
- compliance/skeptic integration into the bridge runtime

Those are later upgrades only if v1 proves worth keeping.

Questions? Concerns? Thoughts? -- Think hard
