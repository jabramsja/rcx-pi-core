# Wave Packet: step16-cascade-fix-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close `reports/deferred/blocking/commit_executor_step16_cascade_block_2026-04-17.md`
by adopting candidate #2 (skip-cleanup-on-verify-fail): soft-warn on dirty
post-merge verify instead of fail-closing step 15; advance to step 16 cleanup
regardless. Step 16 cleanup is wave-scoped (worktree + branch + wave-named
stash) and does NOT depend on main-repo dirty state.

## Scope

`mu/tools/executors/commit_executor.py` step-15 dirty-verify branch +
source-level regression test + archive the closed deferred.

**Files (4 total):**
- `mu/tools/executors/commit_executor.py` — step 15 dirty-verify now
  soft-warns + continues to step 16 instead of returning error; records
  warning in `result["post_merge_verify_warning"]` for ops visibility.
- `mu/tests/tools/test_executor_dispatch.py` — new
  `test_37a_post_merge_dirty_verify_is_warn_not_fail` verifies
  soft-warn semantics via source-level assertions.
- `reports/deferred/blocking/commit_executor_step16_cascade_block_2026-04-17.md`
  → archived as `_CLOSED_by_PR_PENDING.md`.
- `reports/control_plane/step16_cascade_fix_2026-04-17.md` — this packet.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
- **Evidence delta:**
  1. Step 15 soft-warns on dirty verify; step 16 wave-scoped cleanup now
     proceeds regardless of main-repo dirty state.
  2. Source-level regression test verifies fail-close path is gone +
     soft-warn log lines present + `post_merge_verify_warning` carried in
     result.
  3. 339/339 tests across test_executor_dispatch.py +
     test_commit_executor_post_merge_cleanup.py pass.
- **Indicator artifact:** `reports/l4_wave_indicators/step16-cascade-fix-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:step16-cascade-fix-2026-04-17
  (founder directed autonomous progression through all remaining hardening
  deferreds in session 2026-04-17 + "no need to ask unless there is a
  founder override that you can't figure out").

## Stop Conditions

- Abort if any pre-existing test regresses.
- Abort if L4 contract rejects.

## Closeout

On merge, step 16 cleans worktree + branch. Remaining open deferreds:
- `hybrid_recovery_inert_structural_gaps_2026-04-17.md` (3 sub-gaps)
- `pipeline_monitor_watcher_staleness_2026-04-17.md`
- `commit_executor_step15_commented_review_detection_2026-04-17.md`
