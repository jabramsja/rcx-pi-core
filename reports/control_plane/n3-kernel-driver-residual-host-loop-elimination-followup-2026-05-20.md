# N3-Kernel-Driver-Residual-Host-Loop-Elimination-Followup-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20
Class: L4_STRUCTURAL
Category: /mu structural host-semantics reduction
Target gate: G8
Phase-A-Lock: LOCKED
Source authorization: `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]`
line 606, the residual split from
`reports/control_plane/n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20_2026-05-20.md`,
`FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`,
and same-wave
`FOUNDER_OVERRIDE:n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20`

## Purpose

Plan the remaining structural step after the bounded fuel-loop narrowing wave.
The current implementation makes supplied Mu linked-list fuel own progress in
both kernel drivers, but the no-fuel compatibility path still needs a host loop
watchdog. This packet must decide whether that residual loop can be eliminated
without moving authority into a helper, recursion, host iterator abstraction, or
substrate-specific behavior.

## Scope: files/directories in scope

Phase A is limited to deciding and locking the residual no-fuel kernel-driver
loop plan. The in-scope files and evidence surfaces are:

- `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
- `TASKS.md` lines 604-606 for current `[NEXT-CODEX-POST-REDTEAM]`
  authorization grounding only
- `mu/host/js/engine/kernel.js::_stepKernelCore`
- `mu/host/python/rcx_pi/selfhost/step_mu.py::step_kernel_mu`
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/docs/test_l4_current_state_truth.py`
- `mu/tests/parity/test_exhaustion_parity.py`
- `mu/host/js/eval_step.js`
- `mu/tools/checks/check_host_semantics_ratchet.py`
- `tools/checks/check_host_authority_inventory_ratchet.py`
- `tools/checks/enforce_l4_execution_contract.py`

## Work items

1. Reconstruct the current residual contract for supplied fuel, empty fuel,
   retained no-fuel compatibility, and watchdog exhaustion in both target
   kernel drivers, using only the in-scope target functions and focused tests.
2. Decide whether legacy no-fuel callers can be moved to explicit Mu linked-list
   fuel at the public boundary without breaking Python/JS accepted inputs,
   metadata fields, failure modes, or `KernelRunResult` parity.
3. If no-fuel compatibility must remain, decide whether implicit compatibility
   fuel can be represented as existing Mu data without host-counted construction
   becoming the semantic progress owner.
4. Lock the smallest implementation path that either removes both residual
   kernel-driver `@host_iteration` sites or stops with an explicit smaller
   implementation packet, residual proof limits, and focused failing gates.
5. Lock the focused parity/structural test plan across
   `test_kernel_run_result_contract.py`, `test_marker_truth_asymmetry_gate.py`,
   `test_p7w5_outer_loop_boundary_gate.py`, `test_l4_current_state_truth.py`,
   and `test_exhaustion_parity.py`, including the gate that fails if
   `maxSteps` / `max_steps` again becomes semantic progress authority.
6. Lock the evidence plan for `node mu/host/js/eval_step.js`, host-semantics
   ratchet, host-authority inventory ratchet, and L4 execution-contract checks,
   with expected no baseline edits, no unaccepted authority increase, and either
   true marker reduction or detector-visible proof that implementation must
   remain deferred.

## Constraints: not in scope

- No Phase B runtime, test, tracker, indicator, commit, push, PR, or closeout
  edit is authorized by this packet while `Phase-A-Lock` remains `UNLOCKED`.
- Do not relist the predecessor wave's landed supplied-fuel progress ownership
  as unresolved work; this follow-up is only for the residual no-fuel host loop.
- Do not edit ratchet baselines or accept marker movement as structural
  reduction.
- Do not add host authority through a helper, recursion signal, array method,
  host iterator abstraction, substrate-specific primitive, or inventory split.
- Do not change seed, registry, Stage0, scheduler, loader, binary, checksum,
  integrity-chain, Claude, broad tooling, or unrelated docs surfaces.

## Stop conditions

- The proposed fix moves the loop into a new helper, recursion, array method,
  iterator abstraction, or substrate-specific primitive without reducing host
  authority.
- Python and JavaScript would diverge in accepted inputs, fuel behavior,
  metadata fields, or failure modes.
- Host-authority inventory would require a new unreviewed split allowance.
- The wave cannot prove marker elimination as structural reduction rather than
  marker movement.

## Acceptance criteria

- Either both residual `@host_iteration` kernel-driver sites are eliminated with
  no new authority site, or Phase A produces a smaller locked implementation
  packet with explicit residual gates and proof limits.
- Ratchet evidence distinguishes real marker reduction from marker movement.
- Host-authority inventory evidence shows no unaccepted total or authority-site
  increase.
- Python/JS focused parity proves identical KernelRunResult behavior for
  supplied fuel, empty fuel, no-fuel compatibility if retained, and watchdog
  exhaustion.

## Phase B stop result

Bridge Round 2 rejected the marker-only recovery because both target drivers
still had the omitted-fuel host watchdog loops:

- Python still executes `while (not caller_supplied_fuel) or (fuel_cursor is
  not None):` and returns historical `max_steps_exhausted` metadata for
  no-fuel compatibility.
- JavaScript still executes `while (!callerSuppliedFuel || fuelCursor !==
  null)` and returns matching `max_steps_exhausted` metadata for no-fuel
  compatibility.
- Supplied Python `kernel_fuel` and JavaScript `kernelFuel` still consume one
  Mu linked-list node per kernel step and report remaining fuel metadata.
- Explicit `kernel_fuel=None` / `kernelFuel: null` still means empty supplied
  fuel and reports `fuel_exhausted` before a step.
- Neither target driver constructs compatibility fuel from `max_steps` /
  `maxSteps`, preserving the Bridge Round 1 repair without claiming structural
  elimination.

The stop condition applies: preserving omitted no-fuel compatibility while
removing the host loop would require either host-counted compatibility fuel,
recursion, a helper/iterator abstraction, or a behavior change at the public
boundary. The Phase B-local repair therefore restores the two residual
`@host_iteration` markers, restores ratchet scan minima to the unchanged
baseline, and strengthens focused gates so marker-only deletion fails while the
loops remain. Net host-semantics marker delta for this candidate is `0`, not
`-2`; residual no-fuel loop elimination remains deferred to a smaller design
packet that can change the public boundary or encode compatibility progress as
real Mu data without moving host authority.

## Grounding / Authorization

- `TASKS.md` line 606 authorizes this queued Phase A follow-up under
  `[NEXT-CODEX-POST-REDTEAM]`.
- This file is the governing Phase A packet:
  `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`.
- The governing predecessor packet is
  `reports/control_plane/n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20_2026-05-20.md`;
  `TASKS.md` line 605 binds this residual follow-up packet as that wave's
  residual split.
- Source founder authorization is
  `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- Same-wave founder authorization is
  `FOUNDER_OVERRIDE:n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20`.
- This packet is not Phase B authorization. It must be locked by Phase A and
  paired with a detector-visible `TASKS.md` tracker entry before implementation.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
- Commit status: `phase_b_bridge_round_2_blocked`
- Tracker note sha256: `bridge_round_2_marker_truth_stop`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_kernel_run_result_contract.py mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py::TestMarkerTruthAsymmetryGate::test_js_active_kernel_core_loop_is_mu_fuel_governed_with_watchdog mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestPythonOuterLoopBoundary::test_step_kernel_mu_has_fuel_governed_watchdog_loop mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_active_kernel_core_has_fuel_governed_watchdog_loop mu/tests/docs/test_l4_current_state_truth.py::test_stage0_vm_docs_match_shadow_path_wiring_and_l4_boundary --tb=short`.
- Evidence delta: (1) Bridge Round 2 marker-only blocker is repaired by restoring honest residual `@host_iteration` markers while the no-fuel host loops remain. (2) Focused gates cover Python/JS target loop shape, supplied-fuel metadata parity, omitted no-fuel metadata parity, and fail on marker deletion without loop removal. (3) Indicator artifact binds the wave to reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json with net_host_semantic_delta=0.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/engine/kernel.js`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/docs/test_l4_current_state_truth.py`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json`
  - Pre-existing outside-scope staged index entry left untouched:
    `reports/deferred/non_blocking/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20_bridge_nonblockers.md`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/engine/kernel.js`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/docs/test_l4_current_state_truth.py`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
