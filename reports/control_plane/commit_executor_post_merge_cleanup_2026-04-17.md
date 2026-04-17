# Wave Packet: commit-executor-post-merge-cleanup-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close the root-cause gap documented at
`reports/deferred/blocking/commit_executor_missing_post_merge_cleanup_2026-04-17.md`.
`mu/tools/executors/commit_executor.py` had zero post-merge cleanup — after
`gh pr merge` succeeded (step 15 `ensure_review_clear_and_merge`), local
branch refs, linked worktrees, and wave-scoped stashes accumulated across
every merged wave. Verified empirically 2026-04-17: one developer machine
accumulated 11 hours of untouched debt (4 merged local branches, 5 stashes,
1 wip branch, 1 orphan worktree) before manual cleanup.

## Scope

Control-surface only. No runtime, substrate, host, or projection changes.

**Files touched (2):**
- `mu/tools/executors/commit_executor.py` — adds module-level helper
  `_post_merge_cleanup(cleanup_root, repo_root, target_branch, base_branch,
  wave_id, log)` (~110 lines) and a call site inside
  `_run_post_commit_pipeline` after the step-15 try/except. Helper is
  best-effort: failures are logged and swallowed; the merge already
  succeeded and cleanup must never regress the pipeline.
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` — 7 new tests
  (happy path, wrong-branch skip, missing wave branch, nonexistent worktree
  path, no-matching-stashes, worktree-before-branch order invariant, empty
  wave_id short-circuit).

**Files added (tracker / indicator only):**
- `reports/control_plane/commit_executor_post_merge_cleanup_2026-04-17.md`
- `reports/l4_wave_indicators/commit-executor-post-merge-cleanup-2026-04-17.json`

**Files NOT touched:** `mu/host/**`, `rcx_pi/selfhost/**`, any kernel /
projection / seed / substrate file. Pre-push-fast ratchets (host semantics,
authority inventory, anti-theater, bootstrap purity) must remain at baseline.

## Step 16 Design

Runs from `verify_root` (the main repo post-merge ff-only state — the path
`_resolve_post_merge_verify_root` already computes and validates at
step 15).

1. **Safety gate**: confirm `cleanup_root` is on `base_branch`. If not,
   skip all destructive work with a warning.
2. **16b (worktree first)**: if `repo_root.resolve() != cleanup_root.resolve()`
   and the path exists, `git worktree remove --force`. Removing BEFORE
   the branch delete is required — `git branch -D <X>` refuses when X
   is checked out in any linked worktree.
3. **16a (branch)**: `git branch -D target_branch` (now unlocked).
4. **16c (stashes)**: list stashes, filter descriptions containing
   `wave_id`, drop in descending-index order so remaining refs stay valid.

All three sub-steps catch `subprocess.CalledProcessError` +
`TimeoutExpired` individually and record warnings in the outcome dict
rather than raising. Pipeline always appends `"post_merge_cleanup"` to
`steps_completed` and returns normally.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_commit_executor_receipt.py`
- **Evidence delta:**
  1. Adds authoritative post-merge cleanup to the pipeline's terminal
     step so linked worktrees / local branches / wave stashes no longer
     leak across merged waves.
  2. Closes the blocking-deferred root-cause entry at
     `reports/deferred/blocking/commit_executor_missing_post_merge_cleanup_2026-04-17.md`.
  3. 7 new tests exercise happy path + 6 edge cases; existing 44 commit
     executor receipt tests continue to pass (51/51 together).
- **Indicator artifact:** `reports/l4_wave_indicators/commit-executor-post-merge-cleanup-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:commit-executor-post-merge-cleanup-2026-04-17
  (user authorized this session via "do all 3" directing the three
  follow-ups — worktree removal, commit_executor fix, TASKS tracking —
  to be executed now rather than filed indefinitely)

## Verification Plan

Pre-push-fast (step 11 in commit_executor) runs automatically:
- audit_fast.sh: host semantics ratchet, authority inventory ratchet,
  anti-theater ratchet, doc consistency, test theater, JS parity.
- enforce_l4_execution_contract.py: classification, tracker note format,
  non-structural adjacency cap (founder override declared).
- Targeted pytest on staged test files.

Post-merge (step 15 → step 16 self-applies): the wave itself exercises
the new cleanup step — the PR worktree and local branch created for this
wave are the exact subjects the new step removes.

## Stop Conditions

- Abort if pre-push-fast detects a ratchet baseline regression.
- Abort if the 7 new tests regress.
- Abort if any existing commit_executor test breaks (verified 51/51
  passing locally before push).

## Closeout

On merge, close the blocking-deferred entry `commit_executor_missing_post_merge_cleanup_2026-04-17.md`
by moving it to `reports/deferred/archive/`. The cleanup step self-applies
to its own wave: after merge, the local branch `jabramsja/commit-executor-post-merge-cleanup-2026-04-17`
and the worktree `/private/tmp/workingrcx_commit_executor_post_merge_cleanup_2026_04_17`
are removed automatically by step 16.
