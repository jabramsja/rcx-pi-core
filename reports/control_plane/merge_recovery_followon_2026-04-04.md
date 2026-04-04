# Merge Recovery Follow-On

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/merge-recovery-followon-2026-04-04]
Wave ID: merge-recovery-followon-2026-04-04

## Scope

Fix the commit-surface recovery gap exposed by live PR `#723`:

1. stop `merge_pr.sh` mergeability failures from being misclassified as
   `stale_continuation` just because those words appeared elsewhere in the raw
   stdout transcript
2. classify dirty/unmergeable PR merges as their own recovery case and attempt
   a bounded branch sync by merging the PR base branch into the feature branch
   and pushing that sync commit
3. keep post-commit continuation resumable when the feature branch head has
   advanced because of that sync commit
4. render the new recovery class in plain English in the dashboard

This is control-surface recovery hardening only. No runtime/substrate semantics
change.

## Changed surfaces

- `TASKS.md`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tests/tools/test_executor_dispatch.py`

## Proof points

1. `recovery_gate.py` now classifies `merge_pr.sh failed: ... not mergeable`
   as `pr_merge_conflict` instead of falling through to `stale_continuation` or
   `unknown_error`.
2. Tier 2 recovery now has a deterministic `pr_merge_conflict` fix that:
   checks the worktree is clean, asks GitHub for the PR base branch, fetches
   that base branch, merges it into the feature branch, and pushes the sync
   commit.
3. `commit_executor.py` continuation semantics were already designed to accept
   an old recorded commit SHA when it is an ancestor of the current branch head;
   `mu/tests/tools/test_executor_dispatch.py` now locks that behavior directly
   so recovery-driven branch sync does not strand the post-commit continuation.
4. `pipeline_dashboard.py` now renders `pr_merge_conflict` in plain English so
   the recovery pane says what happened without requiring internal code names.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_executor_dispatch.py -q --tb=short`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-surface only
