# Step14 Surfacewait Recheck Reorder 2026-06-02

Date: 2026-06-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: step14-periteration-recheck-2026-06-01
Class: L4_ENABLER
target_gate_id: G8
Phase-A-Lock: LOCKED

Purpose: ONE single-function change in `mu/tools/executors/commit_executor.py`, function `_wait_for_expected_pr_check_surface_to_pass`: move the EXISTING Step-14 mid-poll conflict re-check ahead of the `status=="failed"` early-return (it currently runs AFTER the `status=="passed"`, `status=="failed"`, and timeout early-returns), AND make its `resolved=true` "keep polling" outcome explicit so it survives the move. Background: the prior wave (`step14-midpoll-conflict-recheck-2026-06-01`, "#30") added the recheck block (`if midpoll_autoresolve is not None: ... _check_pr_conflict_state -> _try_auto_resolve_pr_conflict -> on unresolved set midpoll_conflict_aborted`) at the BOTTOM of the surface-pass poll loop. A concurrent-merge CANCELLED required check (which `_summarize_pr_check_surface` classifies as failed) therefore hits the `status=="failed"` early-return FIRST and is mis-reported as a CI failure, never reaching the conflict re-check. The naive fix -- relocating the block verbatim above the `status=="failed"` return -- is INSUFFICIENT (this is the bridge REQUEST_CHANGES finding): the block only `return`s on the UNRESOLVED conflict path; on `resolved=true` it deliberately falls through to "keep polling," which works today ONLY because no `return` sits below it. Once the block moves above the failed/timeout returns, that same `resolved=true` fall-through lands on the relocated `status=="failed"` return and re-emits the SAME stale failed snapshot -- the bug is not fixed. So the change is a relocation PLUS the minimal loop-control needed to make the resolved-conflict case re-poll explicitly (a per-iteration re-poll marker guarding the failed-return) instead of relying on fall-through, with the timeout/deadline check still evaluated every iteration so the wait still terminates at the deadline. No new helpers, caller plumbing, or conflict-detection/resolution logic. Origin: PR #1059 bot P2 finding #2. Cite code by function name only; no file:line.

## Scope

In scope -- one bounded single-function change, tooling-only (L4_ENABLER, no runtime dir):

- `mu/tools/executors/commit_executor.py`, function `_wait_for_expected_pr_check_surface_to_pass` ONLY:
  - Relocate the EXISTING mid-poll conflict re-check so it runs BEFORE the `status=="failed"` early-return and AFTER the `status=="passed"` return.
  - Add the minimal loop control so the `resolved=true` conflict case re-polls explicitly (a per-iteration re-poll marker that skips the `status=="failed"` return for that iteration) instead of falling through into it. The conflict helpers (`_check_pr_conflict_state`, `_try_auto_resolve_pr_conflict`) and the unresolved-path `midpoll_conflict_aborted` envelope are reused unchanged.
  - Keep the timeout/deadline check evaluated on every iteration (including the resolved-conflict iteration) so the wait still terminates at the deadline.
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py`: ADD one regression test to the EXISTING file (test-file count stays flat).

Cite code by function name only; no file:line.

- `reports/deferred/non_blocking/step14-periteration-recheck-2026-06-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks. The same-wave TASKS.md tracker note authorizes the wave but does NOT prove these are landed; the bridge re-read of current code confirms the block still sits at the loop bottom (after the failed/timeout early-returns) and that its `resolved=true` outcome is an implicit fall-through, so both items remain pending:

1. In `_wait_for_expected_pr_check_surface_to_pass`, relocate the mid-poll conflict re-check (`_check_pr_conflict_state` -> on a fresh conflicting transition `_try_auto_resolve_pr_conflict` -> on unresolved set `midpoll_conflict_aborted` and return) to run BEFORE the `status=="failed"` early-return and AFTER the `status=="passed"` return, AND convert its `resolved=true` "keep polling" outcome from an implicit fall-through into an explicit re-poll (a per-iteration marker guarding the `status=="failed"` return) so a successfully auto-resolved concurrent-merge conflict re-polls a fresh surface instead of returning the stale failed snapshot. Keep the timeout check evaluated every iteration.
2. ADD a regression test to the existing `mu/tests/tools/test_commit_executor_step14_autoresolve.py` proving the surface-pass wait, on a concurrent-merge CANCELLED-as-failed surface, (a) re-fires auto-resolve and RE-POLLS when the conflict is resolvable (returning the subsequent surface, not a plain failed), and (b) fails closed with the `pr_conflicting` / `midpoll_conflict_aborted` envelope when it is not -- while a non-conflict real-CI-failure surface still returns failed.

## Constraints

What is NOT in scope:

- Do NOT touch `_wait_for_required_checks_to_pass` (separate wave).
- Do NOT add a conflict re-check before the `status=="passed"` return (a passed surface = green CI = no concurrent-merge cancellation; handled by the Step-16 merge). The passed-return path stays recheck-free.
- Do NOT add new helpers, caller plumbing, or new conflict-detection/resolution logic. Reuse `_check_pr_conflict_state` / `_try_auto_resolve_pr_conflict` and the `midpoll_conflict_aborted` envelope unchanged. The ONLY additions are the relocation and a one-iteration re-poll marker guarding the failed-return; everything else is sequencing within this single function.
- Do NOT change passed-surface behavior, the non-conflict real-CI-failure return, non-Step-14 (`midpoll_autoresolve is None`) caller behavior, or the deadline bound (the timeout check must still be evaluated every iteration).
- Do NOT create new test files; the regression test is ADDED to the existing autoresolve test file (test-file count stays flat).
- Do NOT touch runtime/substrate dirs (this is L4_ENABLER, tooling-only).

## Stop conditions

1. **Premise-invalid (primary uncertainty):** If the existing mid-poll conflict re-check block (`if midpoll_autoresolve is not None: ...`) is NOT present in `_wait_for_expected_pr_check_surface_to_pass` positioned AFTER the `status=="failed"` early-return, or its `resolved=true` path is NOT an implicit fall-through (i.e. it already returns or already re-polls explicitly) as this packet assumes, STOP and re-scope -- the premise is invalid.
2. **Scope breach:** If the fix requires touching `_wait_for_required_checks_to_pass`, adding or altering helpers, caller plumbing, or conflict-detection/resolution logic, or modifying the `status=="passed"` return path, STOP -- that exceeds scope. (The relocation and the one-iteration re-poll marker guarding the failed-return are IN scope and are not a breach.)
3. **Change larger than relocation + re-poll marker:** If making the resolvable concurrent-merge case re-poll (instead of returning a plain failed surface) cannot be achieved by (a) relocating the block above the failed-return and (b) an explicit per-iteration re-poll marker guarding that return -- i.e. it needs new conflict logic, new helpers, or caller changes -- STOP and report rather than expanding the change.
4. **Behavior drift:** If the change alters passed-surface behavior, the non-conflict real-CI-failure return, non-Step-14 (`midpoll_autoresolve is None`) caller behavior, or the deadline bound (the timeout check must remain evaluated every iteration so the wait still terminates at the deadline), STOP.
5. **Push/merge block:** Do NOT push or merge. Hand to the commit pipeline (`commit_executor.py`) only after Phase B convergence + pre-commit supervisor receipt. No manual git operations.

## Acceptance criteria

1. `_wait_for_expected_pr_check_surface_to_pass` runs the mid-poll conflict re-check BEFORE the `status=="failed"` early-return and AFTER the `status=="passed"` return; on a fresh conflicting transition it re-fires auto-resolve; on `resolved=true` it re-polls a fresh surface (the wait does NOT return a plain failed surface for that iteration); on `resolved=false` it returns the `midpoll_conflict_aborted` envelope.
2. The `status=="passed"` return path stays first and recheck-free; a non-conflict real-CI-failure surface still returns failed; non-Step-14 callers (`midpoll_autoresolve is None`) are unaffected; `_wait_for_required_checks_to_pass` is unchanged.
3. The deadline still bounds the wait -- the timeout check is evaluated every iteration, including the resolved-conflict iteration. No new helpers, caller plumbing, or conflict-detection/resolution logic; the only additions are the relocation and a one-iteration re-poll marker guarding the failed-return (single-function change plus one added test).
4. The new regression test proves: (a) a resolvable concurrent-merge CANCELLED-as-failed surface re-fires auto-resolve and re-polls (returning the subsequent surface, not a plain failed); (b) an unresolvable one fails closed with the `pr_conflicting` / `midpoll_conflict_aborted` envelope; (c) a non-conflict failed surface still returns failed.
5. Validation gate green (evidence_command): `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
6. Indicator artifact collected: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id step14-periteration-recheck-2026-06-01 --output reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`.

## Grounding / Authorization

- **TASKS.md authorization:** Authorized by the same-wave tracker note for `step14-periteration-recheck-2026-06-01` in `TASKS.md` (Tracker sync note, 2026-06-02): "**NEXT-CODEX-POST-REDTEAM -- Step-14 surface-wait conflict recheck reorder (PR #1059 P2 #2; single-function, surface-pass only).**" That note names this file as its `Packet:` and carries the FOUNDER_OVERRIDE below.
- **Authorization: standing pipeline-bug-fix authorization** per memory `feedback_autonomous_executor_fix.md` -- this is a bounded control-plane (`commit_executor`) bug fix; the same-wave override is mechanically derivable by `build_commit_handoff` for commit-gate + pre-push adjacency-cap clearance.
- **FOUNDER_OVERRIDE:step14-periteration-recheck-2026-06-01**
- **Governing packet (this plan):** `reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md`.
- **Related governing packets / refs:**
  - Prior wave that added the block being reordered ("#30"): `step14-midpoll-conflict-recheck-2026-06-01`, packet `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`.
  - Queue parent task `[NEXT-CODEX-POST-REDTEAM]`, tracked packet `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
  - Origin bot finding: PR #1059 P2 #2.
- **L4 contract fields (mirroring the authorized tracker note):**
  - Class: L4_ENABLER; target_gate_id: G8.
  - evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
  - evidence_delta: (1) `_wait_for_expected_pr_check_surface_to_pass` re-checks conflict BEFORE the failed-surface early-return AND re-polls explicitly on `resolved=true` (the prior implicit fall-through is made an explicit re-poll marker so it survives the relocation), with the timeout check still evaluated every iteration; (2) new regression test covering the resolvable concurrent-merge CANCELLED-as-failed surface (re-polls, no plain failed), the unresolvable one (`midpoll_conflict_aborted` envelope), and the non-conflict real-CI-failure path (still failed); (3) single-function loop-control change -- no new helpers/plumbing/conflict logic, `_wait_for_required_checks_to_pass` untouched, passed-return recheck-free.
  - primary_blocker_class: INTEGRATION; primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
  - indicator_artifact_ref: `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`.
  - indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id step14-periteration-recheck-2026-06-01 --output reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`.
  - bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD.

## Request from Post-Merge Supervisor

ONE single-function change in commit_executor.py: reorder the EXISTING Step-14 mid-poll conflict-recheck block inside _wait_for_expected_pr_check_surface_to_pass so it runs BEFORE the `status=="failed"` early-return (it currently runs AFTER it). Background: #30 added the recheck block (`if midpoll_autoresolve is not None: ... _check_pr_conflict_state -> _try_auto_resolve_pr_conflict -> on unresolved set midpoll_conflict_aborted`) in the surface-pass poll loop, but placed it after the `status=="failed"` early-return, so a concurrent-merge CANCELLED required check (which _summarize_pr_check_surface classifies as failed) returns a failed surface WITHOUT the recheck and is mis-reported as a CI failure. THE ENTIRE FIX is moving that existing block to run before the `status=="failed"` early-return (after the `status=="passed"` return). HARD SCOPE LIMITS: do NOT touch _wait_for_required_checks_to_pass (out of scope -- separate wave). Do NOT add a conflict recheck before the `status=="passed"` return (a passed surface = green CI = no concurrent-merge cancellation; handled by the Step-16 merge). Do NOT add new helpers, caller plumbing, or new conflict logic -- reuse the EXISTING block verbatim, only reordered. Single-function edit.

Routed next-candidate:
step14-periteration-recheck-2026-06-01

### Phase A reconciliation (bridge REQUEST_CHANGES, relocation-sufficiency finding)

The supervisor request's literal "reuse the EXISTING block verbatim, only reordered" is insufficient, and the plan above refines it accordingly (code truth over request wording). The existing block only `return`s on the UNRESOLVED conflict path; its `resolved=true` outcome is an implicit fall-through to "keep polling" that works ONLY because no `return` currently sits below it. Relocating the block verbatim above the `status=="failed"` return makes that same fall-through land on the relocated failed-return and re-emit the stale failed snapshot -- the concurrent-merge mis-report is NOT fixed. The plan therefore keeps the change single-function with no new helpers/plumbing/conflict logic, but adds the minimal loop-control (an explicit per-iteration re-poll marker guarding the failed-return) so the resolved-conflict case re-polls, and keeps the timeout check evaluated every iteration so the deadline bound is unchanged. All other HARD SCOPE LIMITS (no `_wait_for_required_checks_to_pass`, no recheck before the passed-return, no new conflict logic) are preserved.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `step14-periteration-recheck-2026-06-01`
- Active packet: `reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md`
- Indicator artifact: `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md`
  - `reports/deferred/non_blocking/step14-periteration-recheck-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `step14-periteration-recheck-2026-06-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/step14-periteration-recheck-2026-06-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `step14-periteration-recheck-2026-06-01`
- Active packet: `reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `286199c4a759a0436406b356ffbdbd2184401134a46e006b4ce6f4b4da0db039`
- Indicator artifact: `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step14_surfacewait_recheck_reorder_2026-06-02.md`
  - `reports/deferred/non_blocking/step14-periteration-recheck-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/step14-periteration-recheck-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
