# Phase A Checkpoint Commit

Date: 2026-03-29
Status: Phase A (design -- bridge-converged)
Phase-A-Lock: LOCKED
Purpose: Fix Phase A to Phase B transition gap by adding checkpoint commit after plan lock

## Scope

Close the chicken-and-egg blocker documented in
`reports/deferred/blocking/phase_a_to_phase_b_transition_gap_2026-03-28.md`.

Phase A executor currently locks the plan locally but does not commit it.
Phase B and the post-merge supervisor require the locked plan in git-tracked
state. This blocks all non-BOOTSTRAP_PHASE_B_EXCEPTION Phase B flows.

## Fix: Phase A Checkpoint Commit (Option A from blocker report)

After `lock_plan()` succeeds in `run_phase_a()`, the executor will:

1. Stage the locked plan file: `git add <plan_path>`
2. Commit with a checkpoint message: `chore: Phase A lock — <plan_name>`
3. Return the commit SHA in the result dict

This is a lightweight checkpoint — no PR, no merge, no push, no CI wait.
The subsequent Phase B + commit executor flow handles the full pipeline
including push and PR creation.

## Files to Modify

1. `mu/tools/executors/phase_a_executor.py` — Add checkpoint commit after
   `lock_plan()` in `run_phase_a()`. ~20 LOC.

## Constraints

- No changes to Phase B executor or commit executor
- No changes to pre-commit supervisor validation
- No new dependencies
- Checkpoint commit uses `git commit` directly (not commit_executor — that
  would be circular since commit_executor is for the Phase B handoff)
- Commits on whatever branch is current — branch creation is NOT part of
  the checkpoint. The commit_executor's Step 2 (ensure_feature_branch)
  handles branching when the full pipeline runs after Phase B.

## BOOTSTRAP_PHASE_B_EXCEPTION

This wave modifies executor surfaces (phase_a_executor.py). Claude implements
directly. All other mechanical steps (agents, bridge, commit executor) apply.

## Evidence

- Before: Phase A locks plan locally, Phase B blocked on untracked lock
- After: Phase A commits locked plan, Phase B sees LOCKED in git
- Verify: `git log --oneline -1` after Phase A shows checkpoint commit
- Test: existing phase_a_executor tests + new test for checkpoint behavior

## Lane

Post-red-team structural (NEXT-CODEX-POST-REDTEAM Phase A).
