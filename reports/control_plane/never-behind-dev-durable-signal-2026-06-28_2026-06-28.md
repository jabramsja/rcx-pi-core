# never-behind-dev: durable behind_dev signal on the divergent-commit skip (primary bus) + clear-on-resync

Date: 2026-06-28
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-dev-durable-signal-2026-06-28
Phase-A-Lock: LOCKED

Purpose: Make a working-repo-behind-dev drift VISIBLE + DURABLE so it actually surfaces (the founder's primary repo keeps drifting behind dev).

ROOT CAUSE (corrected against current code -- the prior "behind + tracked-dirt silently skips" premise was FALSE and is withdrawn). In `commit_executor.py::_sync_primary_worktree_to_base` (the post-merge PULL-ONLY primary-sync helper):
- behind + tracked dirt does NOT silently skip. When the primary is behind `origin/{base}` and carries uncommitted tracked WIP, the helper isolates the WIP (`_stash_primary_sync_tracked_wip`), runs `git merge --ff-only --no-overwrite-ignore`, then restores non-overlapping WIP (overlapping WIP is left in a reported executor stash) and sets `synced=True` (commit_executor.py ~4690-4814). This is proven by the existing PASSING tests `test_sync_primary_restores_non_overlapping_tracked_wip` and `test_sync_primary_leaves_overlapping_tracked_wip_stashed`. A "behind + tracked-dirty -> signal + skip + WIP untouched" behavior would contradict those tests; it is NOT pursued.
- the GENUINE silent-drift path is GUARD-C (commit_executor.py ~4669-4682): when the primary HEAD is NOT an ancestor of `origin/{base}` (divergent LOCAL COMMITS), the helper returns `_skip("primary worktree HEAD is not an ancestor ... divergent local commits; founder lands those via a PR")`. The skip is correct (PULL-ONLY never force-syncs divergent commits), but it leaves the primary behind dev with only a transient `Step 15b ... skipped` log line and NO durable signal, so the drift accumulates invisibly. This is the path the founder hits when the primary's feature branch holds committed local work that is not yet in dev.

CONCRETE SINGLE FIX (do exactly these, no alternatives): (1) at the GUARD-C divergent-commits skip, ADDITIONALLY write a structured signal file `behind_dev.json` + log a loud WARNING containing the literal token `behind_dev` (primary path, base ref, behind-count, divergent/ahead-count, reason, timestamp); the skip DECISION is unchanged. (2) Write it to the DURABLE FOUNDER-PRIMARY BUS, not the transient lane bus: in the linked-worktree post-merge path `_run_post_commit_pipeline` passes the temporary lane as `repo_root` and Step 16 can REMOVE that worktree, so writing under `agent_bus_path(repo_root, ...)` loses the alert -- write `behind_dev.json` under the PRIMARY worktree's durable `.agent_bus` (the `primary` path the helper already resolves at the top of the function, distinct from `repo_root`/the lane). (3) CLEAR a stale signal whenever the helper confirms the primary is current with `origin/{base}` -- either a successful ff (the `synced=True` path, which is reached by BOTH the clean ff and the tracked-dirty stash/ff/restore path) OR already-current (`old_sha == new_sha`) -- remove any existing `behind_dev.json` so the signal does not go stale after the founder lands the divergent commits via a PR. The clean+ancestor ff and the tracked-dirty stash/ff/restore behaviors stay UNCHANGED; NEVER clobber WIP. Use the literal identifier `behind_dev` (file name + warning token). STRICT: `_sync_primary_worktree_to_base` + its test only; no host semantics.

## Scope

Add a durable, self-clearing `behind_dev` signal to the ONE genuine silent-drift path in the post-merge primary-sync helper (the GUARD-C divergent-local-commits skip), write it to the durable primary bus (never the transient lane), and clear it on resync -- without changing any sync/skip DECISION and without clobbering WIP.

Files and surfaces in scope:

- `mu/tools/executors/commit_executor.py` -- IMPLEMENTATION TARGET. The single function `_sync_primary_worktree_to_base` (the post-merge primary-sync helper, reached from the `_run_post_commit_pipeline` post-merge call site; public test seam `sync_primary_worktree_to_base`). This is the only runtime-tooling surface edited. The signal write/clear and any tiny nested helper live INSIDE this function (alongside the existing nested `_skip`).
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` -- IMPLEMENTATION TARGET (regressions). The existing post-merge-cleanup test module; the new `behind_dev` regressions are added here. The existing tracked-dirty tests (`test_sync_primary_restores_non_overlapping_tracked_wip`, `test_sync_primary_leaves_overlapping_tracked_wip_stashed`) must remain green unchanged.
- TASKS.md -- tracker-sync authority (no code edit). The 2026-06-28 tracker sync note for wave `never-behind-dev-durable-signal-2026-06-28` is the source for this packet's L4 fields. Where its prose says "behind+dirty silently skipped," the code (and the existing passing tests) override it: the real drift path is the GUARD-C divergent-commits skip (rule_5: code truth > stale doc wording).

## Work items

Behavioral changes to `_sync_primary_worktree_to_base` (do exactly these, no alternatives), plus the regression coverage that proves them:

1. Signal on the GENUINE drift skip (GUARD-C divergent local commits). At the GUARD-C return -- primary HEAD is not an ancestor of `origin/{base}` (divergent local commits) -- ADDITIONALLY write a structured `behind_dev.json` signal and log a loud WARNING containing the literal token `behind_dev`. Signal fields: primary path; base ref (`origin/{base}`); behind-count (commits in `origin/{base}` not reachable from the primary HEAD, e.g. `git rev-list --count HEAD..origin/{base}`); divergent/ahead-count (local commits not in `origin/{base}`); reason (`divergent_local_commits`); timestamp. The skip DECISION is unchanged -- the founder still lands the divergent commits via a PR.
2. Write to the DURABLE primary bus, not the transient lane bus. `_run_post_commit_pipeline` passes the temporary lane as `repo_root`, and Step 16 can remove that worktree -- so writing under `agent_bus_path(repo_root, ...)` loses the alert. Resolve and write `behind_dev.json` under the PRIMARY worktree's durable `.agent_bus` (the `primary` path the helper already computes as the sync target), never the transient lane / `repo_root`.
3. Clear-on-resync. When the helper confirms the primary is current with `origin/{base}`, remove any existing `behind_dev.json`: (a) on a successful ff (`synced=True`) -- this single point covers BOTH the clean ff AND the tracked-dirty stash/ff/restore path; and (b) on already-current (`old_sha == new_sha`). This keeps the signal from going stale after the founder resolves the divergence (via a PR that makes the primary HEAD an ancestor, then ff; or by advancing the primary to dev tip).
4. Add regressions in `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`:
   - (a) WRITE: primary behind + divergent local commits (GUARD-C miss) -> helper SKIPS (not an ancestor; no ff), and `behind_dev.json` is written under the PRIMARY worktree's durable `.agent_bus` (NOT the lane/`repo_root`) with the documented fields; primary HEAD and WIP untouched.
   - (b) CLEAR-ON-FF: primary behind + clean + ancestor -> ff-synced AND any prior `behind_dev.json` removed.
   - (c) NO-REGRESSION (tracked-dirty): primary behind + tracked dirt -> still stashes/ff/restores (`synced=True`, WIP preserved) AND any prior `behind_dev.json` removed; NO `behind_dev.json` is written on this path (it is not drift). This directly guards against the withdrawn false premise.
   - (d) CLEAR-ON-ALREADY-CURRENT: primary already at `origin/{base}` tip with a stale `behind_dev.json` present -> helper skips (already current) AND the stale `behind_dev.json` is removed.

## Constraints

- STRICT surface: edit `_sync_primary_worktree_to_base` and its test only. No other functions, files, or executor surfaces. Any nested helper lives inside this function (like `_skip`).
- No host semantics added (L4_ENABLER; commit_executor is pipeline tooling, not runtime/substrate -- must not touch runtime dirs).
- Do NOT change any sync/skip DECISION. GUARD-C still skips; the tracked-dirty stash/ff/restore path still syncs (existing tests stay green); the clean+ancestor ff still syncs; already-current still skips. This wave only ADDS a signal write on the GUARD-C skip and a signal clear on the resync paths.
- The withdrawn premise is forbidden: there is NO "behind + tracked-dirty silent skip." Do NOT write `behind_dev.json` on the tracked-dirty path (it ff-syncs; a signal there is a false positive and would regress `test_sync_primary_restores_non_overlapping_tracked_wip`).
- NEVER clobber WIP / tracked working-tree changes on any path.
- Do NOT write the signal to the transient lane bus (`agent_bus_path(repo_root, ...)`) -- durable primary `.agent_bus` only.
- No false positives on transient / not-behind skips: do NOT write `behind_dev.json` on the on-base (GUARD-A), detached-HEAD, lock-held (GUARD-D), fetch-failed, or already-current skips.
- Out of scope (noted same-class follow-ups, NOT this wave): signaling on the ff-only-merge-failure skip (e.g. `--no-overwrite-ignore` aborting to protect locally-ignored founder WIP) and on the WIP-isolation overlap/stash-error skips. These also leave the primary behind, but are deferred to keep this wave minimal and the regression set tight.
- Out of scope: optimization, runtime/substrate/seed/parity edits, and any change to the post-merge flow beyond the signal write/clear.

## Stop conditions

- DONE when: the evidence_command passes (`grep -q behind_dev` in both target files), the new regressions (a)-(d) are green, the existing tracked-dirty tests remain green, `python3 -m py_compile mu/tools/executors/commit_executor.py` is clean, and the bridge converges (GO) with a pre-commit supervisor receipt.
- ABORT / re-scope when: a required change would touch any surface other than `_sync_primary_worktree_to_base` + its test, would alter any sync/skip DECISION (GUARD-C skip, tracked-dirty sync, clean ff, already-current skip), would risk clobbering WIP, or would add host semantics. Stop and re-scope rather than widen.

## Validation gates

- evidence_command: `grep -q behind_dev mu/tools/executors/commit_executor.py && grep -q behind_dev mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- behind + divergent local commits (GUARD-C miss): the helper still SKIPS (no ff; primary HEAD and WIP untouched) AND `behind_dev.json` is written under the PRIMARY worktree's durable `.agent_bus` (not the transient lane/`repo_root`), carrying primary path + base ref + behind-count + divergent/ahead-count + reason + timestamp; a WARNING containing the literal `behind_dev` is logged.
- behind + clean + ancestor: the primary is fast-forward-synced AND any prior `behind_dev.json` is removed (clear-on-resync); no stale signal remains.
- behind + tracked dirt: UNCHANGED -- still stashes/ff/restores (non-overlapping WIP restored, overlapping left in the reported executor stash, `synced=True`), and on that successful ff any prior `behind_dev.json` is removed; NO signal is written on this path. The existing tracked-dirty tests remain green.
- already-current (`old_sha == new_sha`) with a stale `behind_dev.json` present: the helper skips (already current) AND removes the stale signal.
- No `behind_dev.json` is written on transient / not-behind skips (on-base, detached, lock-held, fetch-failed, already-current).
- evidence_command passes and regressions (a)-(d) are green; no host semantics introduced; only `_sync_primary_worktree_to_base` + its test changed.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-dev-durable-signal-2026-06-28`.
- Governing packet: this file, `reports/control_plane/never-behind-dev-durable-signal-2026-06-28_2026-06-28.md`.
- TASKS.md authority: the 2026-06-28 tracker sync note for wave `never-behind-dev-durable-signal-2026-06-28` (TASKS.md) is canonical for this packet's L4 fields -- Class `L4_ENABLER`, `target_gate_id: G8`, `evidence_command` as above, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`, indicator artifact `reports/l4_wave_indicators/never-behind-dev-durable-signal-2026-06-28.json`. The note's `progress_proof_before` prose ("behind+dirty silently skipped") is superseded by current code truth (the tracked-dirty path ff-syncs; the genuine drift path is the GUARD-C divergent-commits skip), per rule_5; the L4 classification and evidence_command are unaffected by this correction.
- Bridge revision: this packet was rewritten to resolve the bridge REQUEST_CHANGES finding that the original root cause was false (behind+tracked-dirty SYNCS via stash/ff/restore and would regress `test_sync_primary_restores_non_overlapping_tracked_wip`). The signal trigger is re-targeted to the code-verified GUARD-C divergent-commits skip; no other findings were raised.

FOUNDER_OVERRIDE:never-behind-dev-durable-signal-2026-06-28
