# Commit Executor Main Repo Postmerge Ffsync 2026-06-04

Date: 2026-06-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-executor-main-repo-postmerge-ffsync-2026-06-04
Phase-A-Lock: LOCKED
Class: L4_ENABLER (pipeline tooling; no runtime/substrate dir, no host_semantics_delta)
Purpose: Stop the founder's PRIMARY main-repo checkout drifting behind dev after a wave merges. Verified root cause: the post-merge `git merge --ff-only origin/{base_branch}` already run inside `_run_post_commit_pipeline` targets the path from `_resolve_post_merge_verify_root` -- a worktree that is ALREADY ON base_branch -- so when the founder's main checkout rests on a FEATURE branch it is never the ff target and a stray base-branch worktree absorbs the ff instead; the main checkout drifts (observed: 69 commits behind dev). Fix: a fail-open `_sync_primary_worktree_to_base` helper invoked AFTER the PR merge that PULLS origin/{base_branch} into the PRIMARY working copy's current feature branch under strict guards. The full verified narrative is preserved verbatim in "Request from Post-Merge Supervisor" below.

## Scope

Files/directories in scope (ONLY these two; cite code by FUNCTION NAME, no file:line):

- `mu/tools/executors/commit_executor.py` -- add the new helper `_sync_primary_worktree_to_base(repo_root, base_branch, *, log)` plus its single call-site in `_run_post_commit_pipeline` (after the PR merge and after the existing verify-root ff).
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` -- add regression tests to this EXISTING file (it already drives real `git worktree add` operations).

No runtime/substrate dirs (`mu/host/`, `rcx_pi/selfhost/`). No host_semantics. No L3-parity surface. L4_ENABLER per TASKS.md.

- `reports/deferred/non_blocking/commit-executor-main-repo-postmerge-ffsync-2026-06-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (from the TASKS.md `[NEXT-CODEX-POST-REDTEAM]` entry for this wave, 2026-06-04):

1. Add `_sync_primary_worktree_to_base(repo_root, base_branch, *, log)` to `commit_executor.py`.
2. Identify the PRIMARY working copy via `git worktree list --porcelain` parsed by `_parse_worktree_list` -- the primary worktree is the FIRST non-bare entry (its git dir IS the common dir; confirm via `_git_common_dir`), NOT a linked worktree.
3. Read the primary worktree's current branch via `_worktree_head_branch`.
4. Apply ALL guards; on any miss, SKIP (log + return), never error:
   - GUARD-A: the primary worktree's branch is NOT base_branch/main/master (it is a feature branch) -- never touch a base-branch checkout.
   - GUARD-B: the primary worktree tree is CLEAN (`_dirty_worktree_paths` empty) -- never clobber founder WIP.
   - GUARD-C: the primary worktree HEAD is an ANCESTOR of origin/{base_branch} (a real fast-forward with no divergent local commits); if the feature branch has commits not in origin/{base_branch}, SKIP (the founder lands those via a PR).
   - GUARD-D: parallel-lane safety -- take a NON-BLOCKING file lock (lockfile under the common git dir) so concurrent lane waves do not race on the primary worktree's index; if the lock is held, SKIP (another wave is already syncing).
5. When all guards pass: `git fetch origin {base_branch}` then `git merge --ff-only origin/{base_branch}` in the primary worktree; log the sync (old -> new sha).
6. Wrap fail-open: the helper must NEVER raise out of `_run_post_commit_pipeline` and NEVER change the wave's Status; try/except, log the reason, SKIP on ANY error (missing worktree, lock contention, fetch failure, non-ff).
7. Invoke the helper at exactly ONE call-site in `_run_post_commit_pipeline`, AFTER the PR merge and the existing verify-root ff (its failure must never affect the already-merged PR).
8. Add regression tests to the existing `test_commit_executor_post_merge_cleanup.py`: (a) a primary worktree on a feature branch behind origin/base gets ff'd; (b) a dirty primary SKIPS (no clobber); (c) a primary with a divergent local commit SKIPS; (d) a primary ON base SKIPS; (e) the helper never raises. Mock the prune-dependent git helpers where the test would otherwise depend on git-version prune behavior (per the 2026-06-03 #37 env-dependent-test lesson).

## Constraints

What is NOT in scope / must NOT happen:

- PULL-ONLY invariant (mandatory, scoped to the NEW helper): `_sync_primary_worktree_to_base` NEVER pushes to base_branch, NEVER runs `git checkout` of base_branch, NEVER force/resets. It reaches the primary worktree's CURRENT feature branch ONLY via `git fetch origin {base_branch}` + `git merge --ff-only origin/{base_branch}`. All real merges to dev stay on the PR path (`gh pr merge`).
- The "primary worktree is never checked out to base" guarantee does NOT rest on the resolver's internals -- it rests on `repo_root != primary`. The pipeline ALWAYS runs in a LINKED worktree (founder rule, memory feedback_pipeline_worktree.md), so the executor's `repo_root` is the linked worktree, NOT the founder's primary checkout. The new helper independently identifies the PRIMARY as the FIRST non-bare worktree whose git dir IS the common dir (via `_parse_worktree_list` + `_git_common_dir`) -- a DIFFERENT worktree than `repo_root` -- and only ff-merges into it.
- Do NOT reinvent worktree discovery: reuse `_parse_worktree_list`, `_git_common_dir`, `_worktree_head_branch`, `_dirty_worktree_paths`, `_is_usable_worktree`, `_find_linked_worktree_for_branch`.
- Do NOT modify `_resolve_post_merge_verify_root` or the existing verify-root ff; the new helper is ADDITIVE and runs after it. CODE-TRUTH NOTE (resolves the no-primary-checkout/forbid-resolver tension): the existing resolver's fallback runs `git checkout --ignore-other-worktrees base_branch` in `repo_root` when repo_root is not already on base AND no usable linked base worktree exists. That checkout targets `repo_root` (the linked executor worktree), never the primary, GIVEN `repo_root != primary` (above). This wave neither introduces nor changes that pre-existing behavior. The contradictory case -- repo_root IS the founder's primary checkout (pipeline run in the main repo, against the founder rule), where the PRE-EXISTING resolver -- not this wave -- would `git checkout base_branch` in the primary -- is handled by Stop conditions, NOT by modifying the resolver.
- Touch ONLY the two in-scope files; no other executor surface, no other test file, no new file.
- No runtime/substrate dirs, no host_semantics, no L3-parity change (would reclassify out of L4_ENABLER).
- Cite code by FUNCTION NAME only; no file:line in the plan.
- Non-primary / single-worktree / main-already-current are clean SKIPs, not errors.

## Stop conditions

- STOP when the helper + single call-site + regression tests are implemented and the evidence command passes.
- STOP and request a founder decision if the fix would require pushing to base_branch, the NEW helper checking out base_branch in the primary worktree, force/reset, or any non-fail-open behavior (would violate the PULL-ONLY invariant).
- STOP and request a founder decision if satisfying the no-primary-checkout property would require modifying `_resolve_post_merge_verify_root` -- e.g. if the pipeline is run in the main repo so `repo_root` IS the founder's primary checkout, where the pre-existing resolver fallback would `git checkout base_branch` in the primary. Guarding that pre-existing resolver path is OUT of this additive wave's scope; do NOT silently widen to touch the resolver.
- STOP and reclassify if the change would touch runtime/substrate dirs or require host_semantics (no longer L4_ENABLER).
- Do NOT widen to other executor surfaces, other test files, or worktree-discovery rewrites.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py` passes.
- Regression tests assert all five scenarios: feature-branch-behind-base -> ff'd to origin/{base_branch}; dirty primary -> SKIP; divergent local commit -> SKIP; primary ON base -> SKIP; helper never raises on any error path.
- `_sync_primary_worktree_to_base` is invoked exactly once in `_run_post_commit_pipeline`, after the PR merge and the existing verify-root ff; its failure does not affect the already-merged PR or change the wave Status.
- PULL-ONLY proven by tests (scoped to the helper): `_sync_primary_worktree_to_base` performs no push, no `git checkout` of base, no force, and no reset on the primary worktree; it reaches the primary only via `git fetch` + `git merge --ff-only`.
- Diff confined to `commit_executor.py` + `test_commit_executor_post_merge_cleanup.py`.
- Indicator artifact produced: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id commit-executor-main-repo-postmerge-ffsync-2026-06-04 --output reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`.

## Grounding / Authorization

- TASKS.md authority: `[NEXT-CODEX-POST-REDTEAM]` tracker note (2026-06-04, commit-executor-main-repo-postmerge-ffsync-2026-06-04) -- #51, Class L4_ENABLER, target_gate_id G8, Packet = this file (`reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md`).
- FOUNDER_OVERRIDE:commit-executor-main-repo-postmerge-ffsync-2026-06-04 (wave-bound; mirrors the same-wave authority in TASKS.md so commit automation can derive the override mechanically).
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md -- control-surface L4_ENABLER pipeline bug fix; same-wave override derivable by `build_commit_handoff` for commit-gate + pre-push adjacency-cap clearance.
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES.
- indicator_artifact_ref: reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json.
- indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id commit-executor-main-repo-postmerge-ffsync-2026-06-04 --output reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json.
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- Governing packet: this file.

## Request from Post-Merge Supervisor

Make commit_executor keep the FOUNDER'S PRIMARY working copy (the main repo checkout) current with dev after a wave merges, so it stops drifting. ROOT CAUSE (verified): commit_executor's post-merge step already runs a PULL-ONLY `git merge --ff-only origin/{base_branch}` inside _run_post_commit_pipeline, but it targets the path returned by _resolve_post_merge_verify_root -- which is a worktree that is ALREADY ON base_branch (repo_root if it is on base, else a linked worktree on base, else it checks out base in repo_root). The founder's main checkout normally rests on a FEATURE branch, so it is never that target; a stray leftover worktree sitting on base absorbs the ff instead, and the main checkout drifts tens of commits behind dev. INVARIANT (mandatory, do NOT violate): this is PULL-ONLY -- bring origin/{base_branch} DOWN into the primary worktree's CURRENT feature branch. NEVER push to base_branch, NEVER `git checkout base_branch` in the primary worktree, NEVER force/reset. All real merges to dev still happen only via the PR path (gh pr merge). READ FIRST (mu/tools/executors/commit_executor.py): _run_post_commit_pipeline (the post-merge section where the existing `git merge --ff-only origin/{base_branch}` runs after the PR merge), _resolve_post_merge_verify_root, _find_linked_worktree_for_branch, _git_common_dir, _parse_worktree_list, _is_usable_worktree, _worktree_head_branch, and _dirty_worktree_paths (reuse these; do not reinvent worktree discovery). DELIVER: a NEW helper (e.g. _sync_primary_worktree_to_base(repo_root, base_branch, *, log)) invoked in _run_post_commit_pipeline AFTER the PR merge + the existing verify-root ff (its failure must never affect the already-merged PR). The helper: (1) identifies the PRIMARY working copy via `git worktree list --porcelain` parsed by _parse_worktree_list -- the primary worktree is the FIRST non-bare entry (its git dir IS the common dir; confirm via _git_common_dir), NOT a linked worktree; (2) reads the primary worktree's current branch via _worktree_head_branch; (3) fast-forwards ONLY when ALL guards hold, else SKIP (log + return): GUARD-A the primary worktree's branch is NOT base_branch/main/master (a feature branch) -- never touch a base-branch checkout; GUARD-B the primary worktree tree is CLEAN (_dirty_worktree_paths empty) -- never clobber founder WIP; GUARD-C the primary worktree HEAD is an ANCESTOR of origin/{base_branch} (i.e. a real fast-forward is possible with no divergent local commits) -- if the feature branch has commits not in origin/{base_branch}, SKIP (the founder will land those via a PR); GUARD-D parallel-lane safety: take a non-blocking FILE LOCK (e.g. a lockfile under the common git dir) so concurrent lane waves do not race on the primary worktree's index; if the lock is held, SKIP (another wave is already syncing); When all guards pass: `git fetch origin {base_branch}` then `git merge --ff-only origin/{base_branch}` in the primary worktree, log the sync (old->new sha). FAIL-OPEN everywhere: the helper must NEVER raise out of _run_post_commit_pipeline and never change the wave's Status -- wrap in try/except, log the reason, and skip on ANY error (missing worktree, lock contention, fetch failure, non-ff). Non-primary / single-worktree / main-already-current cases are all clean SKIPs. SCOPE: ONLY mu/tools/executors/commit_executor.py (the new helper + its one call-site in _run_post_commit_pipeline) + a regression test in the EXISTING mu/tests/tools/test_commit_executor_post_merge_cleanup.py (it already drives real `git worktree add` ops): a primary worktree on a feature branch behind origin/base gets ff'd; a dirty primary SKIPS (no clobber); a primary with a divergent local commit SKIPS; a primary ON base SKIPS; the helper never raises. Mock the prune-dependent git helpers where the test would otherwise depend on git-version prune behavior (per the 2026-06-03 #37 env-dependent-test lesson). L4_ENABLER: pipeline tooling, no runtime/substrate dir, no host_semantics. Cite code by FUNCTION NAME only; NO file:line in the plan.

Routed next-candidate:
commit-executor-main-repo-postmerge-ffsync-2026-06-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `commit-executor-main-repo-postmerge-ffsync-2026-06-04`
- Active packet: `reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md`
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md`
  - `reports/deferred/non_blocking/commit-executor-main-repo-postmerge-ffsync-2026-06-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `commit-executor-main-repo-postmerge-ffsync-2026-06-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/commit-executor-main-repo-postmerge-ffsync-2026-06-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-executor-main-repo-postmerge-ffsync-2026-06-04`
- Active packet: `reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `003aa929f8a5df79784856e829b57dfb41b39d9a4f90ddd640d47d91855afaef`
- Indicator artifact: `reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/commit_executor_main_repo_postmerge_ffsync_2026-06-04.md`
  - `reports/deferred/non_blocking/commit-executor-main-repo-postmerge-ffsync-2026-06-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/commit-executor-main-repo-postmerge-ffsync-2026-06-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
