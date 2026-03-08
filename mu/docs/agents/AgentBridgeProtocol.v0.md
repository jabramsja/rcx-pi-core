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
- prompt reviewer
- stop on `GO`, `NO_GO`, or `QUESTION`
- rerender transcript after each turn

4. `status` / `render`
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

The `claude` adapter is verified for Claude Code CLI (`claude --print` with stdin piping). The `codex` adapter remains a placeholder — verify your local Codex CLI invocation before use.

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
