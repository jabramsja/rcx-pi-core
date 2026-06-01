# Step14 Midpoll Conflict Recheck 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: step14-midpoll-conflict-recheck-2026-06-01
Phase-A-Lock: LOCKED
Purpose: Close the verified mid-poll conflict race in commit_executor's Step-14 CI wait. Observed 2026-06-01: with two concurrent dispatcher lanes, the second lane's PR went mergeable=CONFLICTING/DIRTY DURING Step-14 because the FIRST lane merged mid-wait (both lanes wrote TASKS.md tracker notes). The Step-14-START autoresolve guard had already confirmed the PR mergeable, so `_wait_for_pr_ci` was entered clean; the conflict appeared AFTER entry, while `_wait_for_pr_ci` was still in its FIRST wait -- `_wait_for_required_checks_to_register`, the poll loop that waits for the required checks to appear. Because GitHub silently skips `pull_request` workflows on a CONFLICTING/DIRTY PR (no merge ref is computable), the required checks then never register, so that registration wait spins with no chance of success and the lane burns the full CI-wait ceiling. The existing conflict autoresolve runs only at Step-14-START (before `_wait_for_pr_ci`) and at the Step-16-merge late-conflict-retry, so a PR that becomes CONFLICTING DURING the registration wait is never re-resolved.

NARROW fix (retargeted so the re-check fires DURING the doomed wait, addressing the bridge finding that the prior design placed it AFTER):

(a) Correct injection site. Inside `_wait_for_pr_ci` the waits run in sequence: FIRST `_wait_for_required_checks_to_register` (the poll loop that waits for the required checks to appear), then the `gh pr checks --watch` ceiling, then `_wait_for_required_checks_to_pass`, and only LAST `_wait_for_expected_pr_check_surface_to_pass`. The doomed mid-poll wait is the FIRST of these -- the registration wait -- because on a CONFLICTING/DIRTY PR the checks never register. The prior design placed the re-check in the LAST function (`_wait_for_expected_pr_check_surface_to_pass`), which is reached only after registration + watch + pass already succeed -- i.e., after the doomed wait would already have burned its ceiling -- so it could never fire during the stall. This revision moves the mid-poll re-check into `_wait_for_required_checks_to_register`, the only Python poll loop that runs during the stated stall.

(b) Step-14-only gating. `_wait_for_pr_ci` is reached from four call sites -- Step-15 remediation, Step-14, Step-15 pre-merge, and Step-15 late auto-resolve. It today receives the head/wave branch (as `target_branch`) but NOT the base_branch that `_try_auto_resolve_pr_conflict` requires, and `_wait_for_required_checks_to_register` receives neither base nor head. To confine the mid-poll re-check to Step-14 without broadening the other three call sites, thread an OPTIONAL, default-disabled mid-poll autoresolve context (the base_branch, plus the head/wave branch_name already carried as `target_branch`) from `_wait_for_pr_ci` into `_wait_for_required_checks_to_register`. ONLY the Step-14 `_wait_for_pr_ci` call site populates it -- it already has base_branch in scope, the same value the Step-14-START guard passes to `_try_auto_resolve_pr_conflict`; the Step-15 remediation, Step-15 pre-merge, and Step-15 late-auto-resolve call sites leave it unset, so the mid-poll re-check (and its fail-closed return) is inert for them and the registration loop behaves exactly as today.

(c) Mid-poll mechanics + fail-closed return. Gated on the context, each iteration of the registration-wait loop (while it still sees no required checks registered) RE-CHECKs the existing `_check_pr_conflict_state`. On a fresh transition to CONFLICTING/DIRTY since the wait began, RE-FIRE the existing `_try_auto_resolve_pr_conflict` ONCE per detected transition (guarded against repeated re-fires within the same wait). On resolved=true (action no_action / clean_merge / tasks_md_resolved) the autoresolve's base-merge repush re-triggers the previously-skipped workflows, so the required checks register and the loop returns normally -- the subsequent `gh pr checks --watch` then runs against the refreshed, non-conflicting head. On resolved=false (action=aborted -- i.e. a non-TASKS.md conflict, a non-tracker-note TASKS.md conflict, or a fetch/merge/push failure) the loop MUST FAIL CLOSED: surface, via `_wait_for_pr_ci`, the SAME structured error envelope the Step-14-START autoresolve guard already emits (status=error, step=wait_ci, failure_class=pr_conflicting, auto_resolve_action carried through from the helper, plus the existing manual-recovery errors text) and STOP -- it must NOT spin to the registration deadline or proceed into the watch ceiling. REUSE the existing `_check_pr_conflict_state` + `_try_auto_resolve_pr_conflict` helpers -- do NOT reinvent conflict detection or resolution, and do NOT broaden beyond this mid-poll re-check.

## Scope

In scope (files):
- `mu/tools/executors/commit_executor.py` -- specifically and only:
  - `_wait_for_required_checks_to_register` -- the required-checks registration-wait poll loop; add the per-iteration mid-poll re-check here, gated on the presence of the threaded autoresolve context. This is the loop that runs DURING the stall; the prior surface-pass placement ran only after it.
  - `_wait_for_pr_ci` -- add the OPTIONAL, default-disabled mid-poll autoresolve context parameter (base_branch + head branch_name) and convert a mid-poll resolved=false into the same structured `pr_conflicting` fail-closed envelope the Step-14-START guard emits.
  - The Step-14 `_wait_for_pr_ci` call site -- the ONLY site that populates the new context (base_branch is already in scope there). The Step-15 remediation, Step-15 pre-merge, and Step-15 late-auto-resolve `_wait_for_pr_ci` call sites are NOT modified and pass no context.
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py` -- existing regression-test file (add cases; no new file).

Two bounded changes, tooling-only (L4_ENABLER, no runtime dir): (1) thread a Step-14-only, default-disabled mid-poll autoresolve context through `_wait_for_pr_ci` into `_wait_for_required_checks_to_register`; gated on that context, the registration-wait loop re-checks `_check_pr_conflict_state` each iteration and, on a mid-poll CONFLICTING/DIRTY transition, re-fires the existing `_try_auto_resolve_pr_conflict` exactly once per transition -- resuming the wait (checks then register) on resolved=true, or returning the same structured `pr_conflicting` fail-closed envelope on resolved=false. Reuse the existing helpers; no new conflict logic. (2) Regression cases ADDED TO THE EXISTING file test_commit_executor_step14_autoresolve.py (keeps the test-file count flat -- no growth-cap bump): assert both the resolved=true resume path and the resolved=false fail-closed path. Cite code by function name only; no file:line references in the packet.

## Work items

Bounded tasks for this packet under the OPEN [NEXT-CODEX-POST-REDTEAM] phase, grounded in the same-wave tracker note's evidence_delta:

1. **Step-14-only mid-poll re-check threading (commit_executor).** Add an OPTIONAL, default-disabled mid-poll autoresolve context (carrying `base_branch` + the head/wave `branch_name`) to `_wait_for_pr_ci` and thread it into `_wait_for_required_checks_to_register`. Populate it ONLY at the Step-14 `_wait_for_pr_ci` call site, where `base_branch` is already in scope (the same value the Step-14-START guard passes to `_try_auto_resolve_pr_conflict`); leave the Step-15 remediation, Step-15 pre-merge, and Step-15 late-auto-resolve call sites unset (the mid-poll re-check and its fail-closed return are inert for those three -- no behavior change). This threading is mandatory because `_wait_for_pr_ci` carries the head branch as `target_branch` but not the base_branch, and `_wait_for_required_checks_to_register` carries neither.
2. **Step-14 mid-poll re-check mechanics (commit_executor).** Gated on the context being present, each poll iteration of `_wait_for_required_checks_to_register` (while no required checks have registered yet) calls the existing `_check_pr_conflict_state`. On a fresh transition to CONFLICTING/DIRTY since the wait began, re-fire the existing `_try_auto_resolve_pr_conflict` ONCE per detected transition (guard so it cannot re-fire repeatedly within the same wait). On resolved=true, the base-merge repush re-triggers the skipped workflows so the required checks register and the loop returns normally. Reuse both existing helpers; introduce no new conflict-detection or conflict-resolution logic.
3. **Fail-closed on mid-poll resolved=false (commit_executor).** When the mid-poll `_try_auto_resolve_pr_conflict` returns resolved=false (action=aborted), the registration wait must NOT continue. Surface, via `_wait_for_pr_ci`, the SAME structured error the Step-14-START autoresolve guard returns: `status=error`, `step=wait_ci`, `failure_class=pr_conflicting`, `auto_resolve_action` carried through from the helper, plus the existing manual-recovery `errors` text. This re-uses the existing Step-14-START contract rather than inventing a new error shape, and is reachable only when the Step-14 context is present (so the three Step-15 call sites are unaffected).
4. **Regression cases (existing file).** ADD cases to `mu/tests/tools/test_commit_executor_step14_autoresolve.py` asserting BOTH: (a) a PR that becomes CONFLICTING mid-registration-wait with a tracker-note-only conflict triggers exactly one autoresolve re-fire and the registration wait then proceeds (checks register); and (b) a PR that becomes CONFLICTING mid-registration-wait where `_try_auto_resolve_pr_conflict` returns resolved=false/aborted causes the wait to FAIL CLOSED with the structured `pr_conflicting` envelope (failure_class=pr_conflicting) and NOT continue to the registration deadline or the watch ceiling. No new test file; no growth-cap bump.

## Constraints

What is NOT in scope:
- Do NOT reinvent conflict detection or resolution. Reuse `_check_pr_conflict_state` and `_try_auto_resolve_pr_conflict` only.
- Do NOT broaden beyond the Step-14 mid-poll re-check. The mid-poll re-check and its fail-closed return MUST be gated to fire ONLY when the Step-14 `_wait_for_pr_ci` call site populates the autoresolve context. Leave the three non-Step-14 `_wait_for_pr_ci` call sites (Step-15 remediation, Step-15 pre-merge, Step-15 late auto-resolve) behaviorally unchanged -- they pass no context. Leave the Step-14-START autoresolve, the `gh pr checks --watch` ceiling, the `_wait_for_required_checks_to_pass` and `_wait_for_expected_pr_check_surface_to_pass` waits, and the Step-16-merge late-conflict-retry unchanged. No changes to other commit_executor steps.
- Do NOT re-fire autoresolve more than once per detected transition within a single registration wait (must be guarded / idempotent per transition).
- Do NOT, on a mid-poll resolved=false (aborted), silently continue the registration wait -- it MUST fail closed with the same structured `pr_conflicting` envelope used by the Step-14-START guard. Do NOT invent a new error shape; reuse the existing one (failure_class=pr_conflicting, auto_resolve_action carried through).
- Do NOT touch runtime dirs (`rcx_pi/selfhost/`, `mu/host/`, seeds, `mu/programs/`). This is a tooling-only L4_ENABLER.
- Do NOT add a new test file or bump any growth cap.
- Do NOT auto-resolve anything beyond a TASKS.md tracker-note-only conflict; substantive code conflicts and push failures take the fail-closed path above (they are exactly the resolved=false case).
- No file:line references in the packet; cite code by function name. No manual git operations -- commit through `commit_executor.py`.

## Stop conditions

Halt the wave and report (do not silently proceed) if any of the following holds:
- The fix would require NEW conflict-detection or resolution logic, or a new helper, rather than reusing `_check_pr_conflict_state` + `_try_auto_resolve_pr_conflict`.
- The Step-14-only autoresolve context cannot be threaded through `_wait_for_pr_ci` into `_wait_for_required_checks_to_register` without changing the behavior of the three non-Step-14 call sites (Step-15 remediation, Step-15 pre-merge, Step-15 late auto-resolve). If a Step-14-only gate cannot be expressed, halt rather than broaden.
- The mid-poll resolved=false path cannot reuse the existing Step-14-START `pr_conflicting` error envelope and would instead require a new/divergent error shape.
- Implementing the mid-poll re-check forces a change to any runtime dir (would break the L4_ENABLER class), or forces a new test file / growth-cap bump.
- A guard ensuring at-most-once re-fire per detected transition cannot be expressed without restructuring unrelated registration-wait logic.
- Reproduction shows the doomed wait is NOT the registration wait but a conflict that surfaces strictly AFTER the required checks register (i.e., inside the `gh pr checks --watch` subprocess or the later `_wait_for_required_checks_to_pass`/`_wait_for_expected_pr_check_surface_to_pass` waits). That is a distinct window this narrow packet does not restructure -- classify and report rather than broadening the change beyond `_wait_for_required_checks_to_register`.
- The observed conflict is anything other than a TASKS.md tracker-note-only conflict (e.g., a substantive code conflict) -- this is the resolved=false fail-closed path; if it additionally requires a founder decision beyond fail-closing, classify POLICY_BOUND and defer to founder rather than auto-resolving.
- The evidence gate `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py` cannot be made to pass within the narrow change set.
- Phase boundary: do NOT begin Phase B implementation until this packet is bridge-converged and Phase-A-Lock is LOCKED.

## Acceptance criteria

- A mid-poll autoresolve context (base_branch + head/wave branch_name) is threaded from `_wait_for_pr_ci` into `_wait_for_required_checks_to_register`, defaults to disabled, and is populated ONLY at the Step-14 `_wait_for_pr_ci` call site. The Step-15 remediation, Step-15 pre-merge, and Step-15 late-auto-resolve call sites pass no context and are behaviorally unchanged (the mid-poll re-check is inert for them).
- Gated on that context, `_wait_for_required_checks_to_register` calls `_check_pr_conflict_state` on each poll iteration while no required checks have registered.
- On a mid-poll transition to CONFLICTING/DIRTY, `_try_auto_resolve_pr_conflict` is re-fired exactly once per transition (guarded against repeated re-fires within the same wait); on resolved=true, the base-merge repush re-triggers the skipped workflows so the required checks register and the loop returns normally.
- On a mid-poll resolved=false (action=aborted), the registration wait FAILS CLOSED: it returns, via `_wait_for_pr_ci`, the same structured envelope as the Step-14-START guard (status=error, step=wait_ci, failure_class=pr_conflicting, auto_resolve_action carried through) and does NOT continue to the registration deadline or the watch ceiling.
- No new conflict-detection/resolution logic is introduced; only the two named helpers are reused, and the resolved=false envelope reuses the existing Step-14-START `pr_conflicting` shape.
- Regression cases are added to the EXISTING `mu/tests/tools/test_commit_executor_step14_autoresolve.py` proving BOTH: (a) PR becomes CONFLICTING mid-registration-wait (tracker-note-only) -> exactly one autoresolve re-fire -> registration proceeds; and (b) PR becomes CONFLICTING mid-registration-wait with autoresolve resolved=false/aborted -> structured `pr_conflicting` fail-closed return -> wait does NOT continue. No new test file; no growth-cap bump.
- Evidence gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- No runtime dir is touched (L4_ENABLER); the L4 contract is satisfied with target_gate_id G8 plus the evidence_command and evidence_delta recorded in the same-wave tracker note.
- L3 parity: not applicable -- `commit_executor.py` is Python pipeline tooling under `mu/tools/executors/`, not structural-VM projection behavior, so no JS substrate mirror is required.

## Grounding / Authorization

TASKS.md authority: `[NEXT-CODEX-POST-REDTEAM]` -- UNPARKED 2026-03-28, founder-authorized; Sequence Phase A -> Phase B -> Phase C -> Phase D; Current phase OPEN (remaining structural/pipeline work proceeds via separate bounded packets such as this one).
Tracked packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` (the parent [NEXT-CODEX-POST-REDTEAM] queue).
governing packet: this file -- `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`.
Packet: `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`
Same-wave tracker note: TASKS.md tracker sync note (2026-06-01, step14-midpoll-conflict-recheck-2026-06-01) -- Class L4_ENABLER; target_gate_id G8; evidence_command `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`; indicator_artifact_ref `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`.
FOUNDER_OVERRIDE:step14-midpoll-conflict-recheck-2026-06-01
Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance), so commit automation can derive the same-wave override mechanically.
primary_blocker_class: INTEGRATION; primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION; bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD.

## Originating request (Post-Merge Supervisor)

Close the verified mid-poll conflict race in commit_executor's Step-14 CI wait. Observed 2026-06-01: with two concurrent dispatcher lanes, the second lane's PR went mergeable=CONFLICTING/DIRTY DURING its Step-14 check-surface poll because the FIRST lane merged mid-poll (both lanes wrote TASKS.md tracker notes). The existing conflict autoresolve runs only at Step-14-START (before polling CI) and at the Step-16-merge late-conflict-retry, so a PR that becomes CONFLICTING DURING the poll is never re-resolved -- the second lane sat in a doomed poll for the full commit_ci_watch ceiling, because GitHub silently skips pull_request workflows on a CONFLICTING PR so the expected checks never register. NARROW fix: in the Step-14 check-surface wait loop (the function that waits for the expected PR check surface to register/pass), each poll iteration RE-CHECK the existing _check_pr_conflict_state; if the PR has transitioned to CONFLICTING/DIRTY since the poll began, RE-FIRE the existing _try_auto_resolve_pr_conflict (which merges base + resolves a TASKS.md tracker-note-only conflict + repushes) ONCE per detected transition (guard against repeated re-fires within the same poll), then continue polling against the refreshed head. REUSE the existing _check_pr_conflict_state + _try_auto_resolve_pr_conflict helpers -- do NOT reinvent conflict detection or resolution, and do NOT broaden beyond this mid-poll re-check.

Routed next-candidate:
step14-midpoll-conflict-recheck-2026-06-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `step14-midpoll-conflict-recheck-2026-06-01`
- Active packet: `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`
  - `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `step14-midpoll-conflict-recheck-2026-06-01`
- Active packet: `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `19184faac305ee36556f76bacb8d4cc9c954860c968e850ab4d6b7d3da922d28`
- Indicator artifact: `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step14_midpoll_conflict_recheck_2026-06-01.md`
  - `reports/l4_wave_indicators/step14-midpoll-conflict-recheck-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
