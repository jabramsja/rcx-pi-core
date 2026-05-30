# Commit-Outcome Pager Emission False-Error After Worktree Removal — RESOLVED

Date: 2026-05-29
Status: RESOLVED
Closed by wave: commit-outcome-pager-fix-2026-05-29
Original finding: reports/deferred/blocking/agent-defaults-opus-4-8-2026-05-29_commit-outcome-pager-false-error.md
Original severity: blocking (silent dispatcher recovery cascade on an already-merged wave)
Class: L4_ENABLER
FOUNDER_OVERRIDE:commit-outcome-pager-fix-2026-05-29

## What was wrong

After `commit_executor.py` Step 16b removed the wave worktree, a second pager
emit (`commit_outcome`) re-resolved the pager module from the now-deleted
worktree `__file__` path and raised `FileNotFoundError`. The outcome-emission
`except` then unconditionally rewrote a terminal-success result to
`status: "error", step: "commit_outcome_pager"`. On the dispatcher path that
`error` was classified `"failed"`, escaping the non-retryable guard and firing
`attempt_recovery` against a branch that no longer existed — a cry-wolf failure
that could mask a real terminal failure.

## Fix landed (this wave)

- Part 1 — `mu/tools/executors/executor_common.py:713`: register
  `sys.modules["pipeline_agent_pager"] = module` BEFORE `exec_module(module)`,
  mirroring the sibling `meta_bridge_supervisor` loader in the same file. A later
  emit now resolves from the `sys.modules` cache and never re-touches the
  filesystem, decoupling emission from worktree lifetime.
- Part 2 — `mu/tools/executors/commit_executor.py:10607-10623`: the
  outcome-emission `except` is now non-fatal for terminal-success verdicts. When
  `result["status"]` is `success` or `held`, the pager failure is recorded as a
  non-fatal `warnings[]` entry plus a `commit_outcome_pager_warning` field and the
  verdict is preserved. A non-terminal-success status still flips to
  `status: "error", step: "commit_outcome_pager"` so a real failure stays loud.
- Regression coverage — `mu/tests/tools/test_commit_outcome_pager_lifetime.py`:
  (1) a second emit succeeds via the `sys.modules` cache after the source path is
  made unavailable (asserts the disk loader ran exactly once); (2) a side-channel
  outcome-pager failure preserves `success`/`held`; (3) a non-terminal-success
  status still flips to error with the original failure context preserved.

## Evidence

`PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_growth_caps.py
mu/tests/tools/test_commit_outcome_pager_lifetime.py` → 10 passed.

## Non-Goals honored

No runtime substrate (`rcx_pi/selfhost/`, `mu/host/`), seed, scheduler, registry,
loader, JS parity, binary/checksum/integrity, or `role_agents` /
`bridge_agent_defaults` config changes. Does not reopen the closed
`[PIPELINE-AGENT-PAGER]` parent task.
