<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-03-07
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

Purpose: define the minimal working protocol for automated Claude <-> Codex collaboration inside RCX.

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
- hybrid mode: record a synthetic reader turn from the interactive Claude session, then run the reviewer
- combines `submit` + synthetic reader + validations + reviewer in one command
- `--task` / `--task-file`: what the task was
- `--summary` / `--summary-file`: what the reader (interactive session) did
- `--reviewer`: which adapter reviews (default: `codex`)
- `--wave-class`, `--check`, `--job-id`: same as `submit`
- `--verbose` / `-v`: print structured envelope output inline (findings, decision, evidence)
- `--no-diff`: omit git diff from reviewer prompt; use for design deliberation, questions, or non-code review where the diff would distract from the task content
- reader agent is recorded as `claude-session`; touched files auto-detected from git
- designed for the Option C workflow: Claude implements interactively, Codex reviews independently
- also supports design deliberation: pass a proposal via `--task-file` with `--no-diff` for non-code dialectic

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

## Decisions

Supported decisions in v1:
- `GO`
- `NO_GO`
- `REQUEST_CHANGES`
- `QUESTION`
- `STALE`
- `ERROR`

Supervisor behavior:
- `GO` => terminal success
- `QUESTION` => founder stop
- `NO_GO` => terminal no-go
- `REQUEST_CHANGES` => next reader round if rounds remain
- `STALE` => rerun reviewer
- `ERROR` => terminal failure
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
- `REVIEWER_RUNNING` with completed reviewer turn: applies the recorded decision without rerunning
- `REVIEWER_RUNNING` with no completed reviewer turn: resumes at reviewer

In all cases, recovery sets `AWAITING_REVIEWER_APPROVAL` before entering the reviewer phase, which is the same state used by explicit `--pause-after-reader`. The `continue` command accepts any job in `AWAITING_REVIEWER_APPROVAL` regardless of how it got there (pause or recovery). Use `run` to trigger crash detection and recovery from `READER_RUNNING` or `REVIEWER_RUNNING` states.

## Verbose Output And Streaming

When `--verbose` / `-v` is used with `run`, `continue`, or `review`, the supervisor:
1. Prints `[bridge]` step events (round start, agent start/finish, validation results)
2. Prints structured envelope after each agent turn: decision, full summary, all findings with severity/file/evidence, touched files, and request_for_next_agent
3. Streams agent stdout/stderr live to the terminal via tee (output is simultaneously captured for the raw output file)

Without `--verbose`, agents run with fully buffered capture and no inline envelope display.

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

**Shell execution:** Built-in and user-supplied acceptance checks run via `shell=True` (subprocess) to support pipes, redirects, and compound commands. Sanitize check commands before passing via `--check`.

## Adapter Contract

`.agent_bus/bridge_config.json` declares named adapters under `agents`.

The `claude` adapter is verified for Claude Code CLI (`claude --print` with stdin piping). The `codex` adapter uses `codex exec - --sandbox danger-full-access` (full unrestricted sandbox — filesystem write, network, and process execution). This is the most permissive Codex sandbox mode; it is required for the reviewer to run tests, execute validation commands, and search the web for evidence. The reviewer role contract (read-only, no source edits) is enforced by the prompt, not by the sandbox. Claude is the sole implementer; Codex reviews unless Claude explicitly delegates implementation in the task.

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
