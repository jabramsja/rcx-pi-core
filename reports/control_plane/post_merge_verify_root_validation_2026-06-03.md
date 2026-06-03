# Post Merge Verify Root Validation 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-verify-root-validation-2026-06-03
Phase-A-Lock: LOCKED
Purpose: Harden commit_executor's post-merge verification so a STALE/missing linked base-branch worktree cannot turn an ALREADY-SUCCESSFUL merge into a Status: error AND cannot trigger a spurious post-merge recovery cascade. READ FIRST: `_resolve_post_merge_verify_root(repo_root, base_branch, *, log)` and `_find_linked_worktree_for_branch` in mu/tools/executors/commit_executor.py. BUG: `_resolve_post_merge_verify_root` calls `_find_linked_worktree_for_branch(repo_root, base_branch)` and, when it returns a worktree != repo_root, logs 'using linked <base> worktree for verification' and RETURNS it WITHOUT verifying that the worktree path still exists and is a live git worktree. When that linked worktree is stale/removed (observed: a nightly-ci-repair worktree at /private/tmp/rcx-nightly-ci-repair whose dir is gone), the downstream post-merge verify runs git there and fails `fatal: not a git repository`. Because the verify runs AFTER the merge, the PR is ALREADY MERGED, so this is non-fatal to the merge but: (a) in the standalone path it surfaces as Status: error (PR #1064/#1065 fix-forwards 2026-06-02), and (b) in the DISPATCHER path the recovery_gate MISCLASSIFIES the failure -- first pr_conflicting tier-2 (retry commit_executor, re-hits the bug) then unknown_error tier-3 (spawns a wasted tier-3 claude diagnose agent) -- a SPURIOUS post-merge recovery cascade on an already-merged PR (observed 2026-06-03 on #32 / PR #1070 MERGED). PRECISE, BOUNDED FIX: in `_resolve_post_merge_verify_root`, after obtaining branch_worktree from `_find_linked_worktree_for_branch`, VALIDATE it is usable -- the worktree dir exists AND a cheap git probe in it succeeds (e.g. `git -C <branch_worktree> rev-parse --is-inside-work-tree` / `--git-dir` returns 0) -- BEFORE logging/returning it. If it is NOT usable (missing dir / not a git repo / stale), fall through to the EXISTING fallback (`git checkout base_branch` in repo_root, return repo_root) instead of returning the dead path. Keep the happy paths UNCHANGED: current branch == base_branch returns repo_root; a VALID linked worktree is still used + logged. HARD SCOPE: ONLY `_resolve_post_merge_verify_root` (plus a tiny private validation helper if cleaner); do NOT change the post-merge-verify caller's error/warning handling, `_find_linked_worktree_for_branch`, the recovery_gate, or any other step -- the worktree-validation fix removes the failure trigger, so the recovery misclassification cannot fire (no recovery_gate change needed). ADD THE REGRESSION TEST to the EXISTING mu/tests/tools/test_commit_executor_post_merge_cleanup.py (do NOT create a new test file -- growth cap): given a linked base-branch worktree path that does not exist / is not a git repo, `_resolve_post_merge_verify_root` falls back to repo_root (does not return the stale path); and a VALID linked worktree is still returned.

## Scope

Files/directories in scope:
- `mu/tools/executors/commit_executor.py` -- ONLY `_resolve_post_merge_verify_root` (plus, if it reads cleaner, one tiny private validation helper). No other function or pipeline step.
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` -- EXISTING test file; add the regression coverage here. No new test file (growth cap).

L4 class L4_ENABLER, target_gate_id G8: no runtime/substrate dir is touched.

One bounded commit_executor robustness fix (L4_ENABLER, no runtime dir): make `_resolve_post_merge_verify_root` validate the linked base-branch worktree returned by `_find_linked_worktree_for_branch` (dir exists AND a cheap `git -C <wt> rev-parse` probe succeeds) before using it; if stale/missing/not-a-git-repo, fall through to the existing `git checkout base_branch` + repo_root fallback. Prevents a stale nightly-ci-repair worktree from (a) turning an already-merged PR's post-merge verify into Status: error (standalone, PR #1064/#1065) and (b) triggering a spurious dispatcher recovery cascade (pr_conflicting tier-2 -> unknown_error tier-3 claude agent) on an already-merged PR (#32 / PR #1070, 2026-06-03). Happy paths unchanged; only this function touched; no recovery_gate change (removing the failure trigger is sufficient). Regression test added to the EXISTING test_commit_executor_post_merge_cleanup.py (stale worktree -> repo_root fallback; valid worktree -> still used). Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`. Cite code by function name only; no file:line.

- `reports/deferred/non_blocking/post-merge-verify-root-validation-2026-06-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

From the `[NEXT-CODEX-POST-REDTEAM]` tracker note for this wave (TASKS.md, `post-merge-verify-root-validation-2026-06-03`):

1. In `_resolve_post_merge_verify_root`, after obtaining `branch_worktree` from `_find_linked_worktree_for_branch(repo_root, base_branch)`, VALIDATE it BEFORE the existing 'using linked <base> worktree for verification' log/return: the worktree dir must exist AND a cheap git probe in it must succeed (e.g. `git -C <branch_worktree> rev-parse --is-inside-work-tree` / `--git-dir` returns 0).
2. If the linked worktree is NOT usable (missing dir / not a git repo / stale), fall through to the EXISTING fallback (`git checkout base_branch` in `repo_root`, return `repo_root`) instead of logging and returning the dead path.
3. Keep the happy paths UNCHANGED: current branch == base_branch returns `repo_root`; a VALID linked worktree is still used + logged with the existing message.
4. OPTIONAL: extract the dir-exists + git-probe check into one tiny private validation helper in commit_executor only if it reads cleaner. Keep it private; do not export or reuse elsewhere.
5. Add regression coverage to the EXISTING `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`: (a) a linked base-branch worktree path that does not exist / is not a git repo -> `_resolve_post_merge_verify_root` falls back to `repo_root` (does NOT return the stale path); (b) a VALID linked worktree is still returned.

## Constraints

What is NOT in scope (do not touch):
- `_find_linked_worktree_for_branch` -- unchanged.
- The post-merge-verify caller's error/warning handling -- unchanged.
- `recovery_gate` and its tier classification -- unchanged. Removing the failure trigger is sufficient, so the pr_conflicting tier-2 -> unknown_error tier-3 misclassification cannot fire; no recovery_gate change is needed.
- Any other commit_executor step, and any runtime/substrate dir (L4_ENABLER must not touch runtime dirs).
- No new test file (growth cap) -- extend the existing `test_commit_executor_post_merge_cleanup.py`.
- No file:line citations in this packet or in new code comments; cite by function name (doc-governance).

## Stop conditions

- STOP after `_resolve_post_merge_verify_root` (and at most one tiny private helper) is changed and the regression coverage is added to the existing test file. Do not expand to adjacent functions, the caller, or the dispatcher.
- STOP and re-plan if the fix appears to require touching `_find_linked_worktree_for_branch`, the caller's error handling, or `recovery_gate` -- that signals the bounded scope is wrong; widening is forbidden here.
- STOP if a new test file would be needed (growth-cap violation) -- fold the coverage into the existing file instead.
- Phase A only: do NOT commit/push/merge from this packet. Implementation proceeds under Phase B per the pipeline after bridge convergence.

## Acceptance criteria

- `_resolve_post_merge_verify_root` validates the linked worktree (dir exists + git probe succeeds) before logging/returning it; a stale/missing/not-a-git-repo worktree falls through to the existing `git checkout base_branch` + `repo_root` path.
- Both happy paths are behavior-preserving: current-branch == base returns `repo_root`; a VALID linked worktree is still used and logged with the existing message.
- Regression test in the EXISTING `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` covers both: stale/dead linked worktree -> `repo_root` fallback (stale path NOT returned); valid linked worktree -> still returned.
- Only `_resolve_post_merge_verify_root` (plus an optional tiny private helper) changed in `commit_executor.py`; `_find_linked_worktree_for_branch`, the caller, and `recovery_gate` are untouched.
- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- L4 evidence: target_gate_id G8; indicator collected via the wave's `collect_l4_wave_indicators.py` command (see Grounding / Authorization).

## Grounding / Authorization

- Task: `[NEXT-CODEX-POST-REDTEAM]` -- TASKS.md tracker note `(2026-06-03, post-merge-verify-root-validation-2026-06-03)`.
- Governing packet: this file (`reports/control_plane/post_merge_verify_root_validation_2026-06-03.md`).
- Class: L4_ENABLER. target_gate_id: G8. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES.
- indicator_artifact_ref: `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`.
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id post-merge-verify-root-validation-2026-06-03 --output reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`.
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- FOUNDER_OVERRIDE:post-merge-verify-root-validation-2026-06-03
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (control-surface L4_ENABLER pipeline bug-fix; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance). The wave-bound `FOUNDER_OVERRIDE:post-merge-verify-root-validation-2026-06-03` above lets commit automation derive the same-wave override mechanically.

## Request from Post-Merge Supervisor

Harden commit_executor's post-merge verification so a STALE/missing linked base-branch worktree cannot turn an ALREADY-SUCCESSFUL merge into a Status: error AND cannot trigger a spurious post-merge recovery cascade. READ FIRST: `_resolve_post_merge_verify_root(repo_root, base_branch, *, log)` and `_find_linked_worktree_for_branch` in mu/tools/executors/commit_executor.py. BUG: `_resolve_post_merge_verify_root` calls `_find_linked_worktree_for_branch(repo_root, base_branch)` and, when it returns a worktree != repo_root, logs 'using linked <base> worktree for verification' and RETURNS it WITHOUT verifying that the worktree path still exists and is a live git worktree. When that linked worktree is stale/removed (observed: a nightly-ci-repair worktree at /private/tmp/rcx-nightly-ci-repair whose dir is gone), the downstream post-merge verify runs git there and fails `fatal: not a git repository`. Because the verify runs AFTER the merge, the PR is ALREADY MERGED, so this is non-fatal to the merge but: (a) in the standalone path it surfaces as Status: error (PR #1064/#1065 fix-forwards 2026-06-02), and (b) in the DISPATCHER path the recovery_gate MISCLASSIFIES the failure -- first pr_conflicting tier-2 (retry commit_executor, re-hits the bug) then unknown_error tier-3 (spawns a wasted tier-3 claude diagnose agent) -- a SPURIOUS post-merge recovery cascade on an already-merged PR (observed 2026-06-03 on #32 / PR #1070 MERGED). PRECISE, BOUNDED FIX: in `_resolve_post_merge_verify_root`, after obtaining branch_worktree from `_find_linked_worktree_for_branch`, VALIDATE it is usable -- the worktree dir exists AND a cheap git probe in it succeeds (e.g. `git -C <branch_worktree> rev-parse --is-inside-work-tree` / `--git-dir` returns 0) -- BEFORE logging/returning it. If it is NOT usable (missing dir / not a git repo / stale), fall through to the EXISTING fallback (`git checkout base_branch` in repo_root, return repo_root) instead of returning the dead path. Keep the happy paths UNCHANGED: current branch == base_branch returns repo_root; a VALID linked worktree is still used + logged. HARD SCOPE: ONLY `_resolve_post_merge_verify_root` (plus a tiny private validation helper if cleaner); do NOT change the post-merge-verify caller's error/warning handling, `_find_linked_worktree_for_branch`, the recovery_gate, or any other step -- the worktree-validation fix removes the failure trigger, so the recovery misclassification cannot fire (no recovery_gate change needed). ADD THE REGRESSION TEST to the EXISTING mu/tests/tools/test_commit_executor_post_merge_cleanup.py (do NOT create a new test file -- growth cap): given a linked base-branch worktree path that does not exist / is not a git repo, `_resolve_post_merge_verify_root` falls back to repo_root (does not return the stale path); and a VALID linked worktree is still returned.

Routed next-candidate:
post-merge-verify-root-validation-2026-06-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `post-merge-verify-root-validation-2026-06-03`
- Active packet: `reports/control_plane/post_merge_verify_root_validation_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/post_merge_verify_root_validation_2026-06-03.md`
  - `reports/deferred/non_blocking/post-merge-verify-root-validation-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `post-merge-verify-root-validation-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/post-merge-verify-root-validation-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-verify-root-validation-2026-06-03`
- Active packet: `reports/control_plane/post_merge_verify_root_validation_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c3102588208a3bdc918dfb91b96b0e49856ae01d6a459645006edd999094bab3`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/post_merge_verify_root_validation_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/post_merge_verify_root_validation_2026-06-03.md`
  - `reports/deferred/non_blocking/post-merge-verify-root-validation-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/post-merge-verify-root-validation-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
