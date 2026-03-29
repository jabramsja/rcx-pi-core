# Pipeline Task ID Fix

Date: 2026-03-29
Status: Phase A (design -- bridge-converged)
Phase-A-Lock: LOCKED
Purpose: Fix Phase B executor task_id passthrough and Phase A checkpoint commit receipt

## Scope

Two pipeline gaps that caused manual intervention in PR #685:

### 1. Phase B executor ignores task_id on bootstrap-exception path
When `--bootstrap-exception` creates a synthetic routing record, it has no `task_id`.
The handoff defaults to `[EXECUTOR-SURFACES]`, which fails supervisor TASKS.md auth.
Fix: add `--task-id` CLI arg, inject into routing record.

### 2. Phase A checkpoint commit fails on pre-commit receipt check
Checkpoint commit runs `git commit` which triggers pre-commit hook. Hook checks for
supervisor receipt, which doesn't exist (checkpoint is pre-supervisor). The commit
fails unnecessarily.
Fix: use `--no-verify` for checkpoint commits (plan-only, no code).

## Files Modified

1. `mu/tools/executors/phase_b_executor.py` — add `--task-id` arg, inject into routing
2. `mu/tools/executors/phase_a_executor.py` — `--no-verify` on checkpoint commit

## Constraints

- BOOTSTRAP_PHASE_B_EXCEPTION: modifies executor surfaces
- No runtime/substrate changes
- No seed changes

## Evidence

- Before: Phase B with --bootstrap-exception uses wrong task_id, Phase A checkpoint fails on receipt
- After: `--task-id` passed through to handoff, checkpoint commits cleanly
- Verify: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py -q --tb=short`

## Lane

Post-redteam structural (NEXT-CODEX-POST-REDTEAM).
