# BLOCKING: commit_executor step 16 cascade-block in multi-wave sessions

**Date filed**: 2026-04-17
**Observed on**: PR #784 (phase-b-severity-floor-fix-2026-04-17) step 16 failure
**Severity**: BLOCKING (worktree cleanup can be suppressed indefinitely when main repo has unrelated dirty state)

## Symptom

commit_executor step 16 (`_post_merge_cleanup`, added in PR #782) runs a post-merge
verify check on the "cleanup_root" which is typically the main repo's dev worktree.
Before cleaning up the wave's own worktree/branch/stashes, it asserts the main repo
is clean via `git status --short`. If ANY dirty file exists — even if the dirt is
content from a DIFFERENT parallel wave or from stale session planning — step 16
errors with `Post-merge working tree is dirty at <path>: ...` and aborts cleanup.
The wave's worktree + branch remain, requiring manual cleanup downstream.

## Root cause (file:line)

- `mu/tools/executors/commit_executor.py::_post_merge_cleanup` (approximate; exact
  line range depends on the PR #782 merge) — status check is all-or-nothing. Any
  dirty file → failure, regardless of whether it's wave-owned or unrelated.
- The scope invariant ("clean main repo") is too strict for parallel multi-wave
  sessions where Wave A's transient main-repo dirty state (e.g. from session
  planning, or shadow-edits during the wave) can block Wave B's step 16.

## Reproduction (verified 2026-04-17)

Wave B (PR #784, phase-b-severity-floor-fix-2026-04-17):
1. Wave B's commit_executor (PID 50243) completed steps 1-14 cleanly in its own
   worktree `/private/tmp/workingrcx_phase_b_severity_floor_fix_2026_04_17`.
2. Step 15 merged PR #784 (state=MERGED on GitHub).
3. Step 16 ran `_post_merge_cleanup` on the main repo (cleanup_root).
4. Main repo was dirty with Wave A content (parallel wave running concurrently):
   ```
   M mu/tools/observability/_pane_processes.sh
    M mu/tools/observability/pipeline_status.sh
   ?? reports/deferred/archive/commit_executor_missing_post_merge_cleanup_2026-04-17_CLOSED_by_PR782.md
   ?? reports/deferred/archive/main_repo_worktree_branch_stash_debt_2026-04-17.md
   ?? reports/deferred/blocking/pipeline_monitor_watcher_staleness_2026-04-17.md
   ```
5. Step 16 errored: `Error: Post-merge working tree is dirty at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX`.
6. Wave B's worktree + branch NOT cleaned up. Manual removal required post-hoc.

## Structural fix candidates

1. **Scope the dirty check to wave-owned files**: step 16 should only fail if the
   dirty files overlap with the CURRENT wave's files_to_stage + force_add_files.
   Unrelated dirty content (parallel wave, session planning) should be warned
   but not blocking.

2. **Skip-cleanup-on-verify-fail mode**: if status check fails, log a warning and
   STILL proceed with worktree + branch removal (those are wave-scoped operations
   that don't depend on main repo state). Only abort the stash-cleanup step.

3. **Separate verify from cleanup**: move the main-repo dirty check out of step 16
   entirely. It's not essential to cleanup — worktree removal is orthogonal to
   main repo state. Put verify in a separate warn-only step.

## Acceptance criteria for the fix wave

- Pick candidate #2 (skip-cleanup-on-verify-fail) — preserves the verify signal
  for ops visibility but doesn't block cleanup.
- Regression test in `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  (already exists from PR #782): add case where cleanup_root is dirty, assert
  worktree + branch still removed with warning logged.
- No runtime/substrate/host/projection/seed touches. L4_ENABLER class.
