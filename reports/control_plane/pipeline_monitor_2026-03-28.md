# Pipeline Monitor — Real-Time Executor Observability

**Date:** 2026-03-28
**Task:** [PIPELINE-TEST-RUN]
**Lane:** hooks/agents/bridge control-surface
**Phase-A-Lock:** UNLOCKED

## Problem

During pipeline runs, the operator must manually poll 5+ commands to understand
current state: `ps`, `tail`, `cat .agent_bus/*.json`, `gh pr checks`, bridge.db.
When a stage stalls (e.g., connector non-response), diagnosis takes minutes to
hours because there's no live view of what's happening.

## Goal

A `tools/pipeline_monitor.sh` script that launches a tmux session with 4 panes
showing real-time pipeline state. The operator runs it before invoking an executor,
and every stage is visible as it happens.

## Design

### Pane Layout

```
┌─────────────────────────┬─────────────────────────┐
│ EXECUTOR OUTPUT         │ PIPELINE STATE           │
│ (tail -f of executor    │ (.agent_bus/executors/   │
│  stdout log)            │  *.json + bridge state)  │
│                         │                          │
├─────────────────────────┼──────────────────────────┤
│ PROCESS TREE            │ PR / CI / REVIEW STATUS  │
│ (live process tree of   │ (gh pr checks + latest   │
│  executor + children)   │  review SHA + connector) │
└─────────────────────────┴──────────────────────────┘
```

### Pane 1: Executor Output (top-left)
- `tail -f` on the executor's stdout log
- Auto-detect log path from `.agent_bus/executors/` or `.scratch/phase_b_*.stdout.log`
- Falls back to watching `.scratch/` for newest `*.stdout.log`

### Pane 2: Pipeline State (top-right)
- `watch -n5` refreshing:
  - Current executor state from `.agent_bus/executors/commit_executor_*.json` (status, steps_completed, pr_number)
  - Phase B handoff state from `.agent_bus/executors/phase_b_handoff.json` (wave_id, decision)
  - Latest pre-commit receipt from `.agent_bus/meta/pre_commit_receipt.json` (decision, timestamp)
  - Post-merge routing from `.agent_bus/meta/post_merge_routing.json` (decision, task)
  - Bridge lock status from `.agent_bus/meta/meta_bridge.lock` (holder, pid)

### Pane 3: Process Tree (bottom-left)
- `watch -n5` refreshing:
  - Find executor PID via `pgrep -f "executor_dispatch\|commit_executor\|phase_b_executor\|phase_a_executor"`
  - Show process tree: PID, elapsed time, command
  - Show child processes (implementer, Codex, bridge_supervisor, agents)
  - Flag stale processes (>300s with no output growth)

### Pane 4: PR/CI/Review Status (bottom-right)
- `watch -n15` refreshing:
  - Latest PR number from executor state
  - CI check status via `gh pr checks <pr>`
  - Latest connector review SHA + timestamp
  - Pending `@codex review` requests
  - Falls back to "No active PR" when no PR exists yet

### CLI Interface

```bash
# Start monitoring
tools/pipeline_monitor.sh start

# Start with specific log to tail
tools/pipeline_monitor.sh start --log /tmp/phase_b_output.txt

# Stop monitoring (kill tmux session)
tools/pipeline_monitor.sh stop

# Attach to existing session
tools/pipeline_monitor.sh attach
```

### Implementation

Single bash script. Dependencies: `tmux`, `jq`, `gh` (all already available).
No Python. No new packages. No executor surface changes.

Each pane runs a self-contained watch/tail command. The script:
1. Creates a tmux session named `rcx-pipeline`
2. Splits into 4 panes
3. Sends the appropriate command to each pane
4. Attaches (or detaches if `--detach` flag)

### Helper Scripts (internal to the monitor)

The `watch` commands in panes 2-4 call small inline functions or a thin
`tools/pipeline_status.sh` helper that reads the JSON state files and formats
a compact summary. This helper is also usable standalone:

```bash
# One-shot status check
tools/pipeline_status.sh
```

Output:
```
PIPELINE STATUS (2026-03-28 12:34:56)
Executor: commit_executor (pipeline-hardening-2026-03-28)
  Step: 6/15 (build_and_run_supervisor)
  PR: #676 | CI: pending | Branch: jabramsja/pipeline-hardening-2026-03-28
Supervisor: COMMIT_GO (receipt: 2026-03-28T04:28:...)
Bridge: idle (no lock)
Processes: 3 active (PID 25879 → 25883 → 26001)
Review: waiting for connector on bc38bd2 (requested 17:37Z, 45s ago)
```

## Scope

- `tools/pipeline_monitor.sh` — tmux launcher (~80 lines)
- `tools/pipeline_status.sh` — one-shot status helper (~60 lines)
- No executor changes. No Python changes. No test changes needed.
- Category: Governance tooling (no host semantics, no kernel impact)

## Constraints

- Read-only: the monitor NEVER modifies state, only reads it
- No new dependencies beyond tmux + jq + gh
- Must not interfere with running executors
- Must handle "no active pipeline" gracefully (show "idle" state)
- Must handle missing JSON files (executor not started yet)

## Validation

- Manual: run `tools/pipeline_monitor.sh start`, invoke an executor in another
  terminal, verify all 4 panes show live data
- `tools/pipeline_status.sh` when no executor running → shows "idle"
- `tools/pipeline_status.sh` when executor running → shows step/state
