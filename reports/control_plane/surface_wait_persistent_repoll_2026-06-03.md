# Surface Wait Persistent Repoll 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: surface-wait-persistent-repoll-2026-06-03
Phase-A-Lock: LOCKED
Purpose: Make commit_executor's Step-14 expected-check-surface wait PERSISTENTLY re-poll for the refreshed CI surface after a mid-poll conflict auto-resolve, instead of skipping the failed early-return for only ONE iteration. READ FIRST: `_wait_for_expected_pr_check_surface_to_pass` in mu/tools/executors/commit_executor.py -- the `repoll_after_midpoll_resolve` flag, the `_check_pr_conflict_state`/`_try_auto_resolve_pr_conflict` mid-poll block, the `midpoll_prev_conflicting` edge-guard, the `if snapshot['status']=='failed' and not repoll_after_midpoll_resolve: return snapshot` early-return, and the per-iteration deadline check. BUG: `repoll_after_midpoll_resolve` is a ONE-ITERATION marker -- reset False at the top of each loop iteration, set True only on a FRESH conflict->successful-resolve transition (edge-guarded by midpoll_prev_conflicting). After a successful resolve, the base-merge repush RE-TRIGGERS the previously-skipped pull_request workflows, but those workflows take TIME to RE-REGISTER. The resolve iteration skips the failed early-return (one re-poll); but on the NEXT iteration currently_conflicting is False (resolve worked) so repoll_after_midpoll_resolve stays False, and if the surface is STILL 'failed' (re-triggered workflows not yet re-registered) the wait RETURNS failed -- a FALSE CI failure on a PR whose conflict was already resolved. PRECISE FIX: after a successful mid-poll resolve, PERSIST an 'awaiting refreshed surface' state ACROSS iterations (not one-shot) so a 'failed'/stale surface is treated as non-terminal until the re-registered required workflows appear in the surface OR a bounded post-resolve window elapses -- while KEEPING the existing per-iteration deadline check so the wait still terminates at COMMIT_CI_VERIFY_TIMEOUT_S. Concretely: replace the one-iteration `repoll_after_midpoll_resolve` with a persistent marker (e.g. an `awaiting_refreshed_surface_until` timestamp set on resolve, or a boolean that stays set until the surface shows the expected/refreshed required-check set) gating the `status=='failed'` early-return across iterations. Keep the resolved=false fail-closed path (snapshot midpoll_conflict_aborted -> _wait_for_pr_ci pr_conflicting envelope) UNCHANGED, and keep the deadline/timeout early-returns UNCHANGED. SCOPE: primarily modifies `_wait_for_expected_pr_check_surface_to_pass` in commit_executor.py (may add a small supporting state variable/helper as needed); adds a regression test to the EXISTING mu/tests/tools/test_commit_executor_step14_autoresolve.py (do NOT create a new test file -- growth cap). L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by function name only; no file:line in the plan. REGRESSION TEST (existing test_commit_executor_step14_autoresolve.py): simulate a mid-poll conflict that auto-resolves, then the surface remains 'failed' for MULTIPLE iterations (re-registering workflows) before going green -- assert the wait does NOT return a false failure on the post-resolve iterations (it persistently re-polls until green or deadline), and still returns failed/timed_out if the deadline passes without green.

## Scope

Files/directories in scope (and ONLY these):
- `mu/tools/executors/commit_executor.py` -- the single function `_wait_for_expected_pr_check_surface_to_pass` (plus, only if needed, one small supporting state variable/helper local to that wait path).
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py` -- the EXISTING Step-14 auto-resolve test file; the regression case is added here (no new test file -- growth cap).

One bounded commit_executor surface-wait robustness fix (L4_ENABLER, no runtime dir): in `_wait_for_expected_pr_check_surface_to_pass`, make the post-mid-poll-resolve repoll PERSISTENT across iterations (currently a one-iteration `repoll_after_midpoll_resolve` marker) so a 'failed'/stale surface after a successful conflict resolve is treated as 'awaiting refreshed surface' (non-terminal) until the re-triggered required workflows re-register OR a bounded window / the existing deadline elapses -- preventing a FALSE CI failure when the re-triggered pull_request workflows take more than one poll iteration to refresh (the residual parallel-lane race edge after #30/#31). Keep the resolved=false fail-closed path + the deadline/timeout early-returns unchanged. Primarily modifies that one function (+ a small supporting state var if needed); regression test added to the EXISTING test_commit_executor_step14_autoresolve.py. Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`. Cite code by function name only; no file:line.

- `reports/deferred/non_blocking/surface-wait-persistent-repoll-2026-06-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks for this wave (derived from the governing packet and the TASKS.md tracker note for `surface-wait-persistent-repoll-2026-06-03`):

1. In `_wait_for_expected_pr_check_surface_to_pass`, replace the one-iteration `repoll_after_midpoll_resolve` marker with a PERSISTENT awaiting-refreshed-surface state (e.g. an `awaiting_refreshed_surface_until` timestamp, or a boolean that stays set until the expected/refreshed required-check set appears) that gates the `if snapshot['status']=='failed'` early-return ACROSS loop iterations rather than for a single iteration.
2. Set that persistent state on the FRESH conflict->successful-resolve transition (the existing edge-guarded `midpoll_prev_conflicting` path through the `_check_pr_conflict_state`/`_try_auto_resolve_pr_conflict` mid-poll block); do not alter how that transition is detected.
3. While the awaiting state is active, treat a 'failed'/stale surface as NON-TERMINAL: keep re-polling until the re-registered required workflows appear in the surface (expected/refreshed required-check set present) OR the bounded post-resolve window / deadline elapses, at which point the state clears.
4. Preserve the per-iteration deadline check unchanged so the wait still terminates at COMMIT_CI_VERIFY_TIMEOUT_S and returns the existing failed/timed_out snapshot when the deadline passes without green.
5. Leave the resolved=false fail-closed path UNCHANGED (snapshot `midpoll_conflict_aborted` -> `_wait_for_pr_ci` `pr_conflicting` envelope) and leave all deadline/timeout early-returns UNCHANGED.
6. Add a regression case to the EXISTING `mu/tests/tools/test_commit_executor_step14_autoresolve.py` (no new file): simulate a mid-poll conflict that auto-resolves, then the surface stays 'failed' for MULTIPLE iterations (re-registering workflows) before going green; assert the wait does NOT return a false failure on the post-resolve iterations and DOES still return failed/timed_out if the deadline passes without green.

## Constraints

What is NOT in scope:
- Do NOT create any new file. The regression test goes into the existing `test_commit_executor_step14_autoresolve.py`; do not add a new test file or a new source module (growth cap).
- L4_ENABLER, tooling only: MUST NOT touch any runtime/substrate dir (`rcx_pi/selfhost/`, `mu/` runtime/projection surfaces). This wave changes executor tooling and its existing test only.
- Do NOT change the resolved=false fail-closed envelope (`midpoll_conflict_aborted` -> `_wait_for_pr_ci` `pr_conflicting`) or the deadline/timeout early-return semantics.
- Do NOT modify commit_executor functions other than `_wait_for_expected_pr_check_surface_to_pass` (a single small supporting state variable/helper local to that wait path is permitted; broader refactors are not).
- Do NOT alter happy-path surface-wait behavior (green-on-first-pass and ordinary non-conflict polling must be unchanged).
- Cite code by function name only; no file:line in the plan or in commit messages for this wave.
- No L3/JS parity obligation: this is Python executor tooling with no projection-semantics change, so no `mu/host/js/eval_step.js` mirror is required (and none may be added under this L4_ENABLER scope).

## Stop conditions

- STOP once the single-function change in `_wait_for_expected_pr_check_surface_to_pass` plus the regression case in the existing test land and the validation gate passes; do not expand into adjacent cleanup.
- STOP and escalate if the fix appears to require touching a runtime/substrate dir -- that would break the L4_ENABLER class boundary.
- STOP and re-scope if the fix appears to require a NEW test file or a NEW module (growth cap) rather than the existing test file plus the one function.
- STOP and escalate if the fix would change the resolved=false fail-closed path or the deadline/timeout early-return semantics -- those must remain byte-for-byte behaviorally unchanged.
- STOP after the packet rewrite for THIS turn: this task is the Phase A packet rewrite only; the implementation itself is performed in Phase B, not here.

## Acceptance criteria

- `_wait_for_expected_pr_check_surface_to_pass` no longer returns a false CI failure when, after a successful mid-poll conflict resolve, the surface remains 'failed'/stale for more than one poll iteration while the re-triggered pull_request workflows re-register.
- The awaiting-refreshed-surface state persists across iterations (it is NOT reset to one-shot each iteration) and is bounded by the existing deadline / COMMIT_CI_VERIFY_TIMEOUT_S.
- The resolved=false fail-closed path and all deadline/timeout early-returns remain unchanged, demonstrated by the pre-existing cases in `test_commit_executor_step14_autoresolve.py` continuing to pass.
- The existing `test_commit_executor_step14_autoresolve.py` gains a regression case that asserts BOTH: (a) no false failure on the post-resolve iterations (persistent re-poll until green), and (b) the wait still returns failed/timed_out when the deadline passes without green.
- Validation gate is green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- No new files added; no runtime/substrate dir touched (L4_ENABLER boundary preserved).

## Grounding / Authorization

- Task: `[NEXT-CODEX-POST-REDTEAM]` -- wave `surface-wait-persistent-repoll-2026-06-03`.
- Governing packet: this file (`reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md`); the `## Request from Post-Merge Supervisor` section below is the routed source request.
- TASKS.md authorization: the tracker sync note `(2026-06-03, surface-wait-persistent-repoll-2026-06-03)` in `TASKS.md` authorizes this wave with the following machine-enforced L4 fields:
  - Class: `L4_ENABLER`. target_gate_id: `G8`.
  - evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
  - primary_blocker_class: `INTEGRATION`. primary_invariant_id: `INV_TYPED_FAIL_CLOSED_OUTCOMES`.
  - indicator_artifact_ref: `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`.
  - indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id surface-wait-persistent-repoll-2026-06-03 --output reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`.
  - bootstrap_endgame_policy: `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`. boot0_track_id: `V1`. boot0_progress_state: `HOLD`.
- FOUNDER_OVERRIDE:surface-wait-persistent-repoll-2026-06-03
- Authorization: standing pipeline-bug-fix authorization per memory `feedback_autonomous_executor_fix.md`. This control-plane L4_ENABLER packet carries the wave-bound `FOUNDER_OVERRIDE:surface-wait-persistent-repoll-2026-06-03` above so commit automation (`build_commit_handoff`) can derive the same-wave override mechanically for commit-gate + pre-push adjacency-cap clearance; it matches the same-wave `FOUNDER_OVERRIDE` on the governing TASKS.md tracker note.

## Request from Post-Merge Supervisor

Make commit_executor's Step-14 expected-check-surface wait PERSISTENTLY re-poll for the refreshed CI surface after a mid-poll conflict auto-resolve, instead of skipping the failed early-return for only ONE iteration. READ FIRST: `_wait_for_expected_pr_check_surface_to_pass` in mu/tools/executors/commit_executor.py -- the `repoll_after_midpoll_resolve` flag, the `_check_pr_conflict_state`/`_try_auto_resolve_pr_conflict` mid-poll block, the `midpoll_prev_conflicting` edge-guard, the `if snapshot['status']=='failed' and not repoll_after_midpoll_resolve: return snapshot` early-return, and the per-iteration deadline check. BUG: `repoll_after_midpoll_resolve` is a ONE-ITERATION marker -- reset False at the top of each loop iteration, set True only on a FRESH conflict->successful-resolve transition (edge-guarded by midpoll_prev_conflicting). After a successful resolve, the base-merge repush RE-TRIGGERS the previously-skipped pull_request workflows, but those workflows take TIME to RE-REGISTER. The resolve iteration skips the failed early-return (one re-poll); but on the NEXT iteration currently_conflicting is False (resolve worked) so repoll_after_midpoll_resolve stays False, and if the surface is STILL 'failed' (re-triggered workflows not yet re-registered) the wait RETURNS failed -- a FALSE CI failure on a PR whose conflict was already resolved. PRECISE FIX: after a successful mid-poll resolve, PERSIST an 'awaiting refreshed surface' state ACROSS iterations (not one-shot) so a 'failed'/stale surface is treated as non-terminal until the re-registered required workflows appear in the surface OR a bounded post-resolve window elapses -- while KEEPING the existing per-iteration deadline check so the wait still terminates at COMMIT_CI_VERIFY_TIMEOUT_S. Concretely: replace the one-iteration `repoll_after_midpoll_resolve` with a persistent marker (e.g. an `awaiting_refreshed_surface_until` timestamp set on resolve, or a boolean that stays set until the surface shows the expected/refreshed required-check set) gating the `status=='failed'` early-return across iterations. Keep the resolved=false fail-closed path (snapshot midpoll_conflict_aborted -> _wait_for_pr_ci pr_conflicting envelope) UNCHANGED, and keep the deadline/timeout early-returns UNCHANGED. SCOPE: primarily modifies `_wait_for_expected_pr_check_surface_to_pass` in commit_executor.py (may add a small supporting state variable/helper as needed); adds a regression test to the EXISTING mu/tests/tools/test_commit_executor_step14_autoresolve.py (do NOT create a new test file -- growth cap). L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by function name only; no file:line in the plan. REGRESSION TEST (existing test_commit_executor_step14_autoresolve.py): simulate a mid-poll conflict that auto-resolves, then the surface remains 'failed' for MULTIPLE iterations (re-registering workflows) before going green -- assert the wait does NOT return a false failure on the post-resolve iterations (it persistently re-polls until green or deadline), and still returns failed/timed_out if the deadline passes without green.

Routed next-candidate:
surface-wait-persistent-repoll-2026-06-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `surface-wait-persistent-repoll-2026-06-03`
- Active packet: `reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md`
  - `reports/deferred/non_blocking/surface-wait-persistent-repoll-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `surface-wait-persistent-repoll-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/surface-wait-persistent-repoll-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `surface-wait-persistent-repoll-2026-06-03`
- Active packet: `reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a12910000f0b4f77e759fe05c720d74166279099c5004431246e631306dc73de`
- Indicator artifact: `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/surface_wait_persistent_repoll_2026-06-03.md`
  - `reports/deferred/non_blocking/surface-wait-persistent-repoll-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/surface-wait-persistent-repoll-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
