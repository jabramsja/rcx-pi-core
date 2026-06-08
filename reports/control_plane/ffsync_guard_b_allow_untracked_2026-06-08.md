# Ffsync Guard B Allow Untracked

Date: 2026-06-08
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ffsync-guard-b-allow-untracked-2026-06-08
Phase-A-Lock: UNLOCKED
Purpose: Fix the #51 main-repo auto-ff-sync so it actually syncs after every merge (dispatcher AND standalone). ROOT CAUSE (verified empirically by reproducing _sync_primary_worktree_to_base on the live main repo): GUARD-B used _dirty_worktree_paths (tracked | UNTRACKED), so the auto-sync SKIPPED with 'is dirty; not clobbering WIP' whenever the primary held ANY untracked file -- a deferred report, handoff, or scratch artifact -- i.e. almost always, so the founder's main repo kept drifting behind dev. A `git merge --ff-only` cannot silently clobber untracked files (git aborts with 'untracked working tree files would be overwritten' on a path collision) or ignored files (--no-overwrite-ignore already on the merge), so GUARD-B must block ONLY on TRACKED dirt. FIX (applied): GUARD-B now uses _tracked_dirty_paths(primary). PROVEN: the fixed helper ff'd the live main repo addf2151 -> 0b079ed0 despite 3 untracked files present; 30 post-merge-cleanup tests pass incl. a new regression (test_sync_primary_ffs_with_untracked_files_present). Scope = mu/tools/executors/commit_executor.py + mu/tests/tools/test_commit_executor_post_merge_cleanup.py. L4_ENABLER: pipeline tooling only; no runtime/substrate dir; no host_semantics.

## Scope

ffsync GUARD-B allow-untracked (L4_ENABLER): #51's _sync_primary_worktree_to_base GUARD-B used _dirty_worktree_paths (tracked|untracked) and skipped the main-repo auto-ff-sync whenever an untracked deferred-report/handoff/scratch file sat in the primary -- the cause of the founder's repeated main-repo drift. Now blocks only on _tracked_dirty_paths; untracked is safe (ff-only aborts on collision; --no-overwrite-ignore for ignored). Proven: fixed helper ff'd the live main repo despite untracked files; +1 regression test. Scope = commit_executor.py + test_commit_executor_post_merge_cleanup.py.

## Request from Post-Merge Supervisor

Fix the #51 main-repo auto-ff-sync so it actually syncs after every merge (dispatcher AND standalone). ROOT CAUSE (verified empirically by reproducing _sync_primary_worktree_to_base on the live main repo): GUARD-B used _dirty_worktree_paths (tracked | UNTRACKED), so the auto-sync SKIPPED with 'is dirty; not clobbering WIP' whenever the primary held ANY untracked file -- a deferred report, handoff, or scratch artifact -- i.e. almost always, so the founder's main repo kept drifting behind dev. A `git merge --ff-only` cannot silently clobber untracked files (git aborts with 'untracked working tree files would be overwritten' on a path collision) or ignored files (--no-overwrite-ignore already on the merge), so GUARD-B must block ONLY on TRACKED dirt. FIX (applied): GUARD-B now uses _tracked_dirty_paths(primary). PROVEN: the fixed helper ff'd the live main repo addf2151 -> 0b079ed0 despite 3 untracked files present; 30 post-merge-cleanup tests pass incl. a new regression (test_sync_primary_ffs_with_untracked_files_present). Scope = mu/tools/executors/commit_executor.py + mu/tests/tools/test_commit_executor_post_merge_cleanup.py. L4_ENABLER: pipeline tooling only; no runtime/substrate dir; no host_semantics.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ffsync-guard-b-allow-untracked-2026-06-08`
- Active packet: `reports/control_plane/ffsync_guard_b_allow_untracked_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8af1f10263e658a1656c7746ea30b49036b42b6ad2cc121ed2d389153f8bfd75`
- Indicator artifact: `reports/l4_wave_indicators/ffsync-guard-b-allow-untracked-2026-06-08.json`
- Evidence command: `grep -q 'has tracked WIP; not clobbering' mu/tools/executors/commit_executor.py && grep -q 'test_sync_primary_ffs_with_untracked_files_present' mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: GUARD-B in _sync_primary_worktree_to_base now uses _tracked_dirty_paths(primary) (was _dirty_worktree_paths = tracked|untracked), so the main-repo auto-ff-sync no longer skips on harmless untracked files. Verified empirically: the fixed helper ff'd the live main repo addf2151 -> 0b079ed0 with 3 untracked files present; 30 post-merge-cleanup tests pass incl. a new regression (test_sync_primary_ffs_with_untracked_files_present asserting untracked-present -> synced=True + untracked preserved) and the dirty-skip test updated to TRACKED dirt..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ffsync-guard-b-allow-untracked-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/ffsync_guard_b_allow_untracked_2026-06-08.md`
  - `reports/l4_wave_indicators/ffsync-guard-b-allow-untracked-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
