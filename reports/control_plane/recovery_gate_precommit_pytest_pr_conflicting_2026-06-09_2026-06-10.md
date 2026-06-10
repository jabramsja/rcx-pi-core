# Recovery Gate Precommit Pytest Pr Conflicting 2026-06-09 2026-06-10

Date: 2026-06-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-gate-precommit-pytest-pr-conflicting-2026-06-09
Phase-A-Lock: LOCKED
Purpose: GOAL: Fix recovery_gate.classify_failure misclassifying a pre-commit gate (commit_executor Step 8, run_pre_commit_script) targeted-pytest failure as PR_CONFLICTING when the failing test's output contains a merge-state substring. The misclassification strands the wave because fix_pr_conflicting then finds no PR (missing_pr_number). This is the exact #40 bug, already fixed for the pre-push step, recurring at the symmetric pre-commit step.

## Scope

In-scope files/directories (tooling-only L4_ENABLER change; no runtime dirs):

- `mu/tools/executors/recovery_gate.py` -- broaden the local-gate pytest-failure guard (`_looks_like_pre_push_pytest_failure`) so `classify_failure` also recognizes the pre-commit pytest step (`run_pre_commit_script`), not only `run_pre_push_script`, while keeping the existing pytest-indicator requirement.
- `mu/tests/tools/test_recovery_gate.py` -- add the regression coverage asserting the new and the unchanged classifications.

No other file is in scope. The change is narrow and symmetric to the landed #40 pre-push fix.

- `reports/deferred/non_blocking/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `mu/tools/executors/recovery_gate.py`, rename `_looks_like_pre_push_pytest_failure` to a local-gate name and broaden its step check to accept `run_pre_commit_script` OR `run_pre_push_script` (preserve the existing "pre-push-fast failed" signal and the pytest-indicator requirement). The guard, not `commit_executor.py`, is the single edit point.
2. Confirm `classify_failure` routes a `run_pre_commit_script` targeted-pytest failure whose output contains a merge-state substring (e.g. `mergeStateStatus=DIRTY`) to `TEST_FAILURE` before the broad merge-state `PR_CONFLICTING` branch is reached.
3. In `mu/tests/tools/test_recovery_gate.py`, add a regression test asserting: (a) a Step-8 `run_pre_commit_script` pytest failure carrying a merge-state substring classifies `TEST_FAILURE`; (b) the existing `run_pre_push_script` pytest-failure case still classifies `TEST_FAILURE`; (c) a genuine non-local-gate PR conflict (no pytest indicator) still classifies `PR_CONFLICTING`.

## Constraints

What is NOT in scope:

- MUST NOT touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers`.
- No masking: no retry/skip/xfail, and do not weaken or delete existing classification tests.
- Do NOT broaden the merge-state reclassification to arbitrary non-pytest pre-commit failures. Scope strictly to the pytest-bearing local gates (`run_pre_commit_script`, `run_pre_push_script`).
- Genuine PR conflicts on non-local-gate steps (no pytest indicator) must keep classifying `PR_CONFLICTING` unchanged.
- No changes to `commit_executor.py` or any other executor surface; only the guard predicate and its tests change.

## Stop conditions

- STOP if the guard change cannot be made without editing a runtime dir -- that would break the L4_ENABLER class; escalate instead of proceeding.
- STOP if achieving the reclassification requires weakening, deleting, or xfail-ing any existing classification test -- masking is forbidden.
- STOP if current `recovery_gate.py` already recognizes `run_pre_commit_script` in the local-gate guard (work already landed): record a no-op proof and do not re-implement.
- STOP if broadening the guard would reclassify a genuine non-pytest pre-commit PR conflict -- narrow the predicate before continuing.
- Phase A stop: lock this plan only after bridge convergence; do NOT implement in Phase A.

## Acceptance criteria

- `evidence_command` passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py`.
- A `run_pre_commit_script` (Step 8) targeted-pytest failure whose output contains a merge-state substring classifies `TEST_FAILURE` (progress_proof_after), not `PR_CONFLICTING`; the wave no longer strands via `fix_pr_conflicting` -> `missing_pr_number`.
- The existing `run_pre_push_script` pytest-failure case is unchanged (still `TEST_FAILURE`).
- A genuine non-local-gate PR conflict (no pytest indicator) is unchanged (still `PR_CONFLICTING`).
- A new regression test in `mu/tests/tools/test_recovery_gate.py` asserts all three cases above.
- `python3 -m py_compile mu/tools/executors/recovery_gate.py` and `git diff --check` are clean; no runtime dir is touched.

## Grounding / Authorization

- TASKS.md tracker note (2026-06-10) authorizes this wave under `[NEXT-CODEX-POST-REDTEAM]`: Class `L4_ENABLER`, `target_gate_id` G8, Packet `reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md`.
- progress_proof_before: a Step-8 `run_pre_commit_script` targeted-pytest failure whose output contains a merge-state substring classifies as `PR_CONFLICTING` and strands (`fix_pr_conflicting` finds no PR).
- progress_proof_after: the same Step-8 pre-commit pytest failure classifies as `TEST_FAILURE`; genuine non-local-gate PR conflicts still classify `PR_CONFLICTING`.
- Governing packet: this file. The Post-Merge Supervisor request reproduced below is the upstream source; the auto-derived L4 fields footer is the single source of truth for the machine fields.
- Authorization: standing pipeline-bug-fix authorization for this control-plane recovery_gate misclassification (symmetric to the landed #40 pre-push fix). The wave-bound machine-readable override below lets commit automation derive the same-wave override mechanically.
- FOUNDER_OVERRIDE:recovery-gate-precommit-pytest-pr-conflicting-2026-06-09

## Request from Post-Merge Supervisor

GOAL: Fix recovery_gate.classify_failure misclassifying a pre-commit gate (commit_executor Step 8, run_pre_commit_script) targeted-pytest failure as PR_CONFLICTING when the failing test's output contains a merge-state substring. The misclassification strands the wave because fix_pr_conflicting then finds no PR (missing_pr_number). This is the exact #40 bug, already fixed for the pre-push step, recurring at the symmetric pre-commit step.

CONTEXT (reproduced this session): classify_failure routes a failing test to TEST_FAILURE only when _looks_like_pre_push_pytest_failure returns True, which requires the step to be run_pre_push_script (or a "pre-push-fast failed" signal) PLUS a pytest indicator. commit_executor Step 8 (run_pre_commit_script) is a pre-commit-doc-check plus targeted pytest gate -- it runs pytest under a step name the guard does NOT recognize. So a Step-8 targeted-test failure whose output contains a merge-state substring (e.g. mergeStateStatus=DIRTY, as the post-merge-verify-root regression asserts) falls through the guard into the broad merge-state PR_CONFLICTING branch, and the wave strands. Reproduced: an identical failure result classifies PR_CONFLICTING at step run_pre_commit_script but TEST_FAILURE at step run_pre_push_script.

REQUIRED FIX (narrow, symmetric to #40): broaden the local-gate pytest-failure guard so it also recognizes the pre-commit pytest step (run_pre_commit_script), not only the pre-push step. For example, rename _looks_like_pre_push_pytest_failure to a local-gate name and accept run_pre_commit_script OR run_pre_push_script, keeping the existing pytest-indicator requirement. A pre-commit targeted-pytest failure whose content mentions a merge-state string must classify TEST_FAILURE (a test to fix), not PR_CONFLICTING. A genuine PR conflict on a NON-local-gate step (no pytest indicator) must still classify PR_CONFLICTING unchanged. Add a regression test asserting the Step-8 (run_pre_commit_script) pytest failure with a merge-state substring classifies TEST_FAILURE, and that the existing pre-push case and a genuine non-local-gate PR conflict are unchanged.

This is an L4_ENABLER tooling-only change (recovery_gate.py plus its tests): it MUST NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). No masking (no retry/skip/xfail; do not weaken existing classification tests). Scope conservatively to the pytest-bearing local gates; do not broaden the merge-state reclassification to arbitrary non-pytest pre-commit failures.

Routed next-candidate:
recovery-gate-precommit-pytest-pr-conflicting-2026-06-09

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-gate-precommit-pytest-pr-conflicting-2026-06-09 --output reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `recovery-gate-precommit-pytest-pr-conflicting-2026-06-09`
- Active packet: `reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-gate-precommit-pytest-pr-conflicting-2026-06-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-gate-precommit-pytest-pr-conflicting-2026-06-09`
- Active packet: `reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `08a84a747fa48778710281d2ee6d40cd641a0ff41e289965bbda025bdf43f5f9`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_gate_precommit_pytest_pr_conflicting_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-precommit-pytest-pr-conflicting-2026-06-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
