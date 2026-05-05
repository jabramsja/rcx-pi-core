# Mu Preproduction Red-Team

Date: 2026-05-04
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent queue: [NEXT-CODEX-POST-REDTEAM]
Wave ID: mu-preproduction-redteam-2026-05-04
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
Authorization: TASKS.md:394-401 authorizes the founder-unparked parent queue and the immediate pre-production work order.
Governing packet: reports/control_plane/mu_preproduction_redteam_2026-05-04.md
FOUNDER_OVERRIDE:mu-preproduction-redteam-2026-05-04

## Purpose

Run a full code-truth red-team of `/mu` before production-forward movement.
This is a production gate, not a documentation sweep.

## Scope

Files and directories in scope:

- `mu/host/python/`
- `mu/host/js/`
- `mu/tools/compilers/`
- Stage0, lowering, and runtime execution paths under `mu/`
- seed JSON programs and registry/load paths under `mu/programs/` and related
  loader surfaces
- `/mu` parity, structural, L4, and runtime tests
- `/mu` tooling that claims to enforce runtime, parity, Stage0, seed, or
  production gates
- `/mu` docs that make current-state, production, Stage0, parity, or L4 claims

- `reports/deferred/non_blocking/mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Inventory production-critical `/mu` execution paths named by the current
   TASKS.md work order: Python, JavaScript, Stage0/lowering/runtime paths,
   seeds/registries, tests, tooling, and docs.
2. Compare Python and JavaScript authority for every current production or
   parity claim.
3. Red-team Stage0, lowering, seed execution, host-boundary, and fail-closed
   behavior for host-smuggling, bypasses, dead gates, or proof-class mismatch.
4. Red-team tests for theater: source-lock-only checks claiming behavioral
   proof, smoke tests that do not exercise the live path, and parity gates that
   do not prove both substrates.
5. Red-team tooling and docs for production claims that are not backed by code
   and tests.
6. Write blockers to `reports/deferred/blocking/` and non-blockers to
   `reports/deferred/non_blocking/` with direct file:line or command evidence.
7. If a bounded fix is obvious and low-risk, implement it only when it does not
   compromise the audit; otherwise route the finding into the correct deferred
   lane for a follow-up implementation packet.
8. Do not relist already-landed parent-queue work as unresolved: TASKS.md:398
   records that the Phase A structural gap sweep and the first bounded
   engine-state/scheduler reduction already landed as code truth.

## Constraints

- Do not accept documentation as proof of runtime behavior.
- Do not treat green broad checks as closure unless the check exercises the
  claimed live path with the right proof class.
- Do not move production forward while red-team blockers remain unresolved.
- Do not collapse non-blockers into blockers or blockers into non-blockers
  without severity and production-risk evidence.
- Do not treat this packet as authorization to redo, reopen, or reimplement
  already-landed `[NEXT-CODEX-POST-REDTEAM]` seed, fixture, structural-test, or
  scheduler-parity items.
- Do not widen beyond the `/mu` production-preparation audit surfaces named by
  TASKS.md:401.

## Stop Conditions

Stop and report immediately if:

1. A production-critical runtime path is missing behavioral proof on a claimed
   live substrate.
2. Python/JavaScript parity authority diverges for a production claim.
3. Stage0/lowering/seed execution relies on hidden host semantics that the
   current docs or gates claim have been reduced.
4. A test or tool claims a production gate but can pass without exercising the
   claimed invariant.

## Acceptance Criteria

- Every required audit surface is either inspected or explicitly listed as
  blocked with why it could not be inspected.
- Findings include concrete file:line or command evidence.
- Blockers are written under `reports/deferred/blocking/`.
- Non-blockers are written under `reports/deferred/non_blocking/`.
- TASKS/report indexes identify whether production-forward movement is blocked.
- Validation includes targeted runtime/parity/test commands selected from the
  findings, docs consistency, and L4/current-state checks where claims touch L4,
  Stage0, or production state.
- Acceptance does not require implementing or relisting code already marked
  landed by TASKS.md:398; this packet accepts only the pre-production red-team
  audit and routed finding artifacts.

## Grounding / Authorization

- `TASKS.md:394-398` grounds this packet in the founder-authorized
  `[NEXT-CODEX-POST-REDTEAM]` parent queue and records current code truth for
  landed Phase A and engine-state/scheduler work.
- `TASKS.md:399-401` defines the immediate work order:
  `[MU-PREPRODUCTION-REDTEAM] NEXT after [DEFERRED-FINDINGS-SWEEP] lands`.
- `TASKS.md:401` names this file as the governing packet and requires blockers
  under `reports/deferred/blocking/` and non-blockers under
  `reports/deferred/non_blocking/`.
- The original audit authorization carried
  `FOUNDER_OVERRIDE:mu-preproduction-redteam-2026-05-04` as tracker/L4 evidence.
  Phase B/commit supervisor packages must treat this implementation package as
  a control-surface `L4_ENABLER` repair unless a future bounded packet includes
  executable runtime delta and L4 gate evidence.

## Phase B Stop Result

Production-forward movement is blocked.

The audit hit stop condition 4: a production-preparation gate can pass without
enforcing the claimed test-theater invariant. The redteam startup guard runs
`python3 tools/checks/check_gate_behavioral_pairs.py` without
`--fail-on-theater`; the checker therefore exits green while reporting
`theater_risk` methods. Strict reproduction with
`python3 tools/checks/check_gate_behavioral_pairs.py --fail-on-theater` exits
`1` with `FAIL: 85 theater_risk method(s) found`.

Blocker packet:
`reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`.

No runtime code fix was applied in this audit packet.

## Pipeline Repair Addendum

After Phase B bridge convergence, the pre-commit supervisor rejected the
generated package because `founder_override_token` was present while
`wave_class` was `L4_STRUCTURAL`. This wave now includes a mechanical repair:
Phase B filters structural tracker tokens out of supervisor packages, and
recovery treats this schema rejection as a retryable Phase B package-truth gap
only after the source filter exists.

Bridge Round 3 found that the same staged package still claimed
`L4_STRUCTURAL` even though it had no runtime/substrate changed files and no
`mu/tests/l4_gates/` evidence. The implementation package is therefore
classified as `L4_ENABLER`: it repairs production-prep gate enforcement and
pipeline package truth without claiming runtime structural movement.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `mu-preproduction-redteam-2026-05-04`
- Active packet: `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
- Indicator artifact: `reports/l4_wave_indicators/mu-preproduction-redteam-2026-05-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/session/founder_session_guard.sh`
  - `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
  - `reports/deferred/README.md`
  - `reports/deferred/blocking/README.md`
  - `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  - `reports/deferred/non_blocking/mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/mu-preproduction-redteam-2026-05-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `mu-preproduction-redteam-2026-05-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `mu-preproduction-redteam-2026-05-04`
- Active packet: `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8c21464456aad353fc09893e7dadfea9cea4efe8a36939c32ed753a12313bd43`
- Indicator artifact: `reports/l4_wave_indicators/mu-preproduction-redteam-2026-05-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/mu_preproduction_redteam_2026-05-04.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/mu-preproduction-redteam-2026-05-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/session/founder_session_guard.sh`
  - `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
  - `reports/deferred/README.md`
  - `reports/deferred/blocking/README.md`
  - `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  - `reports/deferred/non_blocking/mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/mu-preproduction-redteam-2026-05-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
