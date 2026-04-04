# Post-Commit Round-Trip

Date: 2026-04-04
Status: In progress
Task: [PIPELINE-RECOVERY/post-commit-roundtrip-2026-04-04]
Wave ID: post-commit-roundtrip-2026-04-04

## Scope

1. keep the baked-in executor fallback config aligned with the checked-in live
   `executor_config.json`
2. route that fix through the real `commit` executor instead of a manual
   commit/push/merge path
3. use the merged result as the base for the next end-to-end recovery proof

## Why this wave exists

The control plane already depends on long-running Phase A / Phase B / commit
surfaces. If a linked worktree or partial local config falls back to stale
baked-in defaults, the live pipeline can silently run with older budgets and
backend choices than the repo-tracked operational config claims.

## Changed surfaces

- `mu/tools/executors/executor_common.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `CHANGELOG.md`
- `TASKS.md`

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q`

## Invariant tuple

- runtime/substrate delta: none
- host semantics delta: none
- scope class: control-surface reliability only
