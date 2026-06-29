# never-behind-dev: signal (not silent-skip) when the primary worktree is behind dev with DIVERGENT LOCAL COMMITS

Date: 2026-06-28
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-dev-signal-2026-06-28
Phase-A-Lock: LOCKED
Purpose: Make the working-repo-behind-dev drift VISIBLE so it can be acted on (the founder's primary repo keeps drifting behind dev). The signal fires on the REAL remaining silent-drift path — GUARD-C, where the primary's feature-branch HEAD has divergent local commits and cannot fast-forward — NOT on a "behind + tracked-dirt" path (that path already ff-syncs and is out of scope; see reconciliation below).

## Bridge reviewer reconciliation (2026-06-28, round 1 REQUEST_CHANGES)

The bridge returned REQUEST_CHANGES with two blocking findings. Both are accepted as code truth; this rewrite resolves them by preferring current code over the stale packet wording (CLAUDE.md rule_5).

- **Finding 1 (DOC_ACCURACY, high) — premise was false.** The prior packet claimed `_sync_primary_worktree_to_base` "SILENTLY SKIPS when the primary has TRACKED dirt." Code truth: there is **no `if dirty: skip` branch**. When the primary is behind base with tracked dirt, the function stashes the tracked WIP (`_stash_primary_sync_tracked_wip`), runs `git merge --ff-only --no-overwrite-ignore`, then restores the non-overlapping WIP (overlapping WIP is left in an executor-owned stash and reported). This handling **landed in commit 6ffd899b** ("chore: preserve tracked WIP during primary ff-sync"). The behind+tracked-dirt scenario is therefore **already ff-synced**, not silently skipped. Per the rewrite guidance, that scenario is treated as already-implemented and **removed** from pending work items and acceptance criteria.
- **Finding 2 (DEFECT, critical) — work items targeted a nonexistent branch and would regress 3 tests.** The prior work items said to act "on the EXISTING silent-skip branch (behind + tracked dirt) … instead of skipping silently," and the prior acceptance criterion ("behind + tracked-dirty → no stash, no ff-sync performed") contradicted three shipped tests that assert `synced is True`: `test_sync_primary_restores_non_overlapping_tracked_wip`, `test_sync_primary_leaves_overlapping_tracked_wip_stashed`, and `test_sync_primary_ffs_with_untracked_files_present`. Implementing the old plan would have reversed commit 6ffd899b and failed those tests. The rewrite leaves every ff-sync path — and all three tests — **untouched**, and re-points the signal to the genuine invisible-drift path (GUARD-C divergent local commits).

The L4 fields derived from the 2026-06-28 TASKS.md tracker sync note (Class `L4_ENABLER`, `target_gate_id: G8`, `evidence_command`, `FOUNDER_OVERRIDE:never-behind-dev-signal-2026-06-28`, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`, indicators) are **premise-neutral and remain authoritative and unchanged**. The note's prose still describes the old "silently skips on tracked dirt" premise; this packet's corrected root cause supersedes that prose for the implementation (code truth over doc wording), while the note's machine fields continue to govern the L4 contract. The `evidence_command` (a presence grep for the literal token `behind_dev`) is satisfied identically regardless of which skip path carries the signal.

## Scope

Make the working-repo-behind-dev drift VISIBLE so it can be acted on. ROOT (corrected): `_sync_primary_worktree_to_base` (`mu/tools/executors/commit_executor.py`) is a PULL-ONLY post-merge helper that fast-forwards the founder's primary feature-branch checkout up to `origin/{base_branch}`. It already advances the primary in the behind+clean AND behind+tracked-dirt cases (the latter via stash → `git merge --ff-only` → restore, since commit 6ffd899b). The genuine remaining silent-drift path is **GUARD-C**: when the primary's HEAD is **not an ancestor** of `origin/{base_branch}` (the founder has divergent local commits on the feature branch), a fast-forward is impossible, so the helper correctly **`_skip`s** (it must never clobber those commits) — but it emits only a plain reason log with no structured signal and no greppable token, so the drift stays invisible across sessions.

CONCRETE SINGLE FIX (do exactly this, no alternative branches): in `_sync_primary_worktree_to_base`, on the **GUARD-C divergent-commits `_skip` path**, when the primary is genuinely behind base (`behind_count = git rev-list --count HEAD..origin/{base_branch}` is greater than 0), do NOT skip silently — **additively** (1) write a structured signal file named `behind_dev.json` into the bus observability dir (`agent_bus_path(repo_root, _active_bus_dir(), "observability")/behind_dev.json`) containing `{primary_path, base_branch, primary_branch, behind_count, skip_reason, timestamp}`, and (2) log a loud single-line WARNING containing the literal token `behind_dev`, naming the primary path and the behind-count. Then STILL skip — the sync must not merge, rebase, reset, or otherwise touch the divergent local commits or any WIP. Every fast-forward path (behind+clean, behind+tracked-dirt stash/restore) is UNCHANGED. Use the literal identifier `behind_dev` for both the file name and the warning token (so it is greppable). STRICT SCOPE: `_sync_primary_worktree_to_base` + its test only; no host semantics; no runtime/substrate/seed changes.

Files and surfaces in scope:

- `mu/tools/executors/commit_executor.py` — only `_sync_primary_worktree_to_base` (the GUARD-C divergent-commits `_skip` path within it).
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` — add one regression for the GUARD-C signal; do not modify the three existing ff-sync tests.
- TASKS.md — tracker-sync authority only (read-only here). The 2026-06-28 tracker sync note for wave `never-behind-dev-signal-2026-06-28` is the single source of truth for this packet's L4 fields; the packet derives its machine fields from it (see reconciliation above).

## Work items

1. In `_sync_primary_worktree_to_base` (`mu/tools/executors/commit_executor.py`), at the **GUARD-C divergent-commits skip** (primary HEAD is not an ancestor of `origin/{base_branch}`), compute `behind_count` as `git rev-list --count HEAD..origin/{base_branch}` (commits on base the primary lacks). When `behind_count > 0`, before returning the skip, write a structured signal file `behind_dev.json` into the bus observability dir — `agent_bus_path(repo_root, _active_bus_dir(), "observability")/behind_dev.json` — containing `{primary_path, base_branch, primary_branch, behind_count, skip_reason, timestamp}`. The write must be best-effort and fail-open (a write error must never raise into the post-merge pipeline; degrade to the existing skip).
2. In that same GUARD-C path, emit one loud single-line `WARNING` containing the literal token `behind_dev`, naming the primary path and the behind-count, so the drift is greppable in logs. Use the literal identifier `behind_dev` for both the file name and the warning token. After signalling, return the existing `_skip` (the divergent local commits are preserved untouched — no merge, rebase, reset, checkout, or stash).
3. Add ONE regression to the existing post-merge-cleanup test file (`mu/tests/tools/test_commit_executor_post_merge_cleanup.py`): set up a primary worktree on a feature branch with a divergent local commit while `origin/{base}` has advanced (so HEAD is not an ancestor and `behind_count > 0`), invoke the public seam `sync_primary_worktree_to_base`, and assert — (a) outcome `synced is False` / `skipped is True` and the divergent local commit is still at HEAD (no clobber); (b) `behind_dev.json` is written into the observability dir carrying `behind_count > 0` and the expected fields; (c) a single-line WARNING containing the token `behind_dev` was logged. Include a negative leg: behind + ancestor (a real fast-forward) → `synced is True`, NO `behind_dev.json`, NO `behind_dev` warning. Do NOT modify the three existing ff-sync tests.

## Constraints

- STRICT SCOPE: only `_sync_primary_worktree_to_base` and its test (`mu/tests/tools/test_commit_executor_post_merge_cleanup.py`) may change. No other function, executor, or surface.
- Do NOT modify or regress the three shipped ff-sync tests — `test_sync_primary_restores_non_overlapping_tracked_wip`, `test_sync_primary_leaves_overlapping_tracked_wip_stashed`, `test_sync_primary_ffs_with_untracked_files_present` — or any fast-forward path they cover. The behind+tracked-dirt handling (commit 6ffd899b) stays exactly as-is.
- The signal fires ONLY on the GUARD-C divergent-commits skip while genuinely behind (`behind_count > 0`). It must NOT fire on the non-drift skips: already-current, primary-on-base-branch (GUARD-A), sync-lock-held (GUARD-D), fetch-failed, worktree-unresolved, or any successful ff-sync.
- No host semantics added (Class: L4_ENABLER).
- No runtime/substrate/seed changes; MUST NOT touch runtime dirs (`mu/host/`, `rcx_pi/selfhost/`, seeds).
- The clean and the tracked-dirt fast-forward paths are UNCHANGED.
- NEVER clobber, merge, rebase, reset, checkout, or stash the divergent local commits, tracked WIP, or untracked WIP — only SIGNAL. The signal path must not mutate the primary worktree's working tree, index, or refs.
- No alternative branches or behavior beyond the single concrete fix (write `behind_dev.json` + WARNING on the GUARD-C divergent-commits skip, then skip as before).
- No L3-parity / JS mirror work — control-plane Python tooling only.

## Stop conditions

- STOP if the signal cannot be implemented without modifying anything beyond `_sync_primary_worktree_to_base` and its test (scope breach → re-scope narrow, do not widen).
- STOP if the change would alter any fast-forward path (behind+clean or behind+tracked-dirt) or would make any of the three existing ff-sync tests fail.
- STOP if the change would touch runtime dirs, the seed, or require new host semantics (violates L4_ENABLER class).
- STOP if the fix cannot avoid mutating/clobbering/stashing the divergent local commits or any tracked/untracked WIP on the primary worktree.
- STOP and surface as POLICY_BOUND if the bus observability dir (`agent_bus_path(repo_root, _active_bus_dir(), "observability")`) is unavailable in this context such that writing the signal would require a new capability (the signal write must stay best-effort/fail-open, never raising into the pipeline).

## Validation gates

- evidence_command: `grep -q behind_dev mu/tools/executors/commit_executor.py && grep -q behind_dev mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- evidence_command passes: `grep -q behind_dev mu/tools/executors/commit_executor.py && grep -q behind_dev mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (presence check only; non-re-entrant grep on a self-referential commit_executor wave — the binding proof is the pytest regression below plus full pytest in CI).
- Regression (behind + divergent local commits, GUARD-C): the outcome is `synced is False` / `skipped is True` and the divergent local commit remains at the primary's HEAD (no clobber, no merge, no rebase, no reset); `behind_dev.json` is written into the observability dir containing `{primary_path, base_branch, primary_branch, behind_count, skip_reason, timestamp}` with `behind_count > 0`; a single-line WARNING carrying the literal token `behind_dev` (primary path + behind-count) is logged.
- Regression (behind + ancestor, real fast-forward): the primary is ff-synced (`synced is True`); NO `behind_dev.json` is written and no `behind_dev` WARNING is emitted.
- The three shipped ff-sync tests still pass unchanged: `test_sync_primary_restores_non_overlapping_tracked_wip` (`synced is True`, `tracked_wip_restored is True`), `test_sync_primary_leaves_overlapping_tracked_wip_stashed` (`synced is True`), `test_sync_primary_ffs_with_untracked_files_present` (`synced is True`). The behind+tracked-dirt path is untouched.
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` passes in full.
- progress_proof_after holds: behind + divergent-local-commits → visible `behind_dev.json` signal + loud `behind_dev` WARNING; behind + clean and behind + tracked-dirt → ff-synced; divergent commits and WIP never clobbered.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-dev-signal-2026-06-28`.
- Governing packet: this file, `reports/control_plane/never-behind-dev-signal-2026-06-28_2026-06-28.md`.
- TASKS.md authority: the 2026-06-28 tracker sync note for wave `never-behind-dev-signal-2026-06-28` is canonical for this packet's L4 fields (Class `L4_ENABLER`, `target_gate_id: G8`, `evidence_command`, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`, `indicator_artifact_ref`/`indicator_collection_command`, `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`, `boot0_track_id: V1`, `boot0_progress_state: HOLD`). Those machine fields are premise-neutral and unchanged; this packet's corrected root cause supersedes the note's prose premise per code truth (CLAUDE.md rule_5).
- Code-truth references: commit 6ffd899b ("chore: preserve tracked WIP during primary ff-sync") landed the behind+tracked-dirt stash/ff/restore handling; the GUARD-C divergent-commits `_skip` in `_sync_primary_worktree_to_base` is the unsignaled drift path this wave targets.

FOUNDER_OVERRIDE:never-behind-dev-signal-2026-06-28
