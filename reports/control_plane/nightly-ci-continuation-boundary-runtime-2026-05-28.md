# Nightly CI Continuation Boundary Runtime Repair 2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: nightly-ci-continuation-boundary-runtime-2026-05-28
Class: L4_STRUCTURAL
Category: production Mu runtime continuation-boundary and CI duration repair
Lane: /mu structural runtime and nightly CI repair
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Repair the failed `Slow Tests (Nightly)` run without weakening tests by moving outer callers back to the public bounded return-meta driver and reducing same-process JS continuation proof cost while preserving fail-closed continuation binding.

## Direct Failure Evidence

- GitHub Actions run `26592481022` for workflow `Slow Tests (Nightly)` on `dev` at `4bd106bb64e5b324fc55669f94eca823176e8b57` completed `failure` on 2026-05-28.
- The job log at `/tmp/rcx-nightly-26592481022.current.log` reported `8 failed, 809 passed in 2211.11s (0:36:51)`.
- The first slow-tests command in `.github/workflows/slow_tests.yml` ran `python -m pytest -m "slow and not l4_expensive" -v -n auto --dist worksteal --timeout=300 2>&1`; the later `l4_expensive` command did not run because the first command failed.
- The failed tests were:
  - `tests/structural/test_gate5_meta_circular_parity.py::test_gate5_run_mu_structural_matches_bridge_nonlinear_semantics`
  - `tests/structural/test_gate5_meta_circular_parity.py::test_gate5_run_mu_structural_records_projection_id_via_bridge_path`
  - `tests/parity/test_js_parity_automated.py::TestHemisphereRoutingPropertyFuzzer::test_valid_engine_result_routing_parity`
  - `tests/parity/test_boot1_shadow_parity.py::TestBoot1CrossSubstrateParity::test_paxos_boot1_cross_substrate`
  - `tests/parity/test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity::test_engine_pipeline_paxos_parity`
  - `tests/parity/test_js_parity_automated.py::TestDifferentialReplayAuditR3::test_generated_hemisphere_replay`
  - `tests/parity/test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity::test_full_pipeline_with_routing_parity`
  - `tests/parity/test_boot1_shadow_parity.py::TestBoot1FourWayParity::test_paxos_freeze_four_way`
- The log shows two Python failures as `ValueError: SECURITY: continuation_state kernel_state is not bound to supplied projections/input`.
- The log shows two Hypothesis deadline failures at about 43.5 seconds against a 30 second deadline.
- The log shows four JS JSON API subprocess timeouts after 120 seconds on paxos `run_engine_pipeline` or `run_engine_with_routing` requests.

## Root-Cause Evidence

- Python source evidence: `mu/host/python/rcx_pi/selfhost/step_mu.py` re-entered public `step_kernel_mu(... continuation_state=..., return_packet=True)` from `run_mu_structural`, while direct `step_kernel_mu(... return_meta=True)` succeeds on the same nonlinear Gate 5 inputs. That public re-entry path trips the existing continuation binding guard.
- JS routing source evidence: `mu/host/js/engine/routing.js` re-entered public `stepKernel(... continuationState: packet.continuation, returnPacket: true)` inside `runHemisphereRouting` and `runMetabolizationCycle`, instead of using the bounded public `returnMeta` driver that owns continuation progress internally.
- JS profile evidence from the failed SHA tied the remaining paxos cost to `_stepKernelCore` under `runAlgorithmWithBridge` / `serviceBoundaryEffect`, with top self time in `isValidMu`, `record`, `canonicalize`, and `muCopy`; repeated continuation proof hashing was on that path.
- Same-session timing on the failed SHA measured:
  - `js_hemisphere_seconds=7.964619`
  - `js_paxos_pipeline_boot1_False_seconds=29.452705`
  - `js_paxos_pipeline_boot1_True_seconds=28.823547`
  - `js_paxos_with_routing_seconds=42.524262`
- Same-session timing after the repair in this worktree measured:
  - `postfix_py_hemisphere_seconds=0.731943`
  - `postfix_js_hemisphere_seconds=1.078237`
  - `postfix_py_paxos_pipeline_seconds=8.441682`
  - `postfix_js_paxos_pipeline_boot1_false_seconds=15.464723`
  - `postfix_js_paxos_pipeline_boot1_true_seconds=15.348119`
  - `postfix_js_paxos_with_routing_seconds=16.699945`
- The exact eight failed nightly selectors now pass locally under the nightly xdist shape with `8 passed in 50.26s`.

## Scope

Implementation scope:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - In `run_mu_structural`, stop manually re-entering `step_kernel_mu()` with caller-owned continuation state. Use public `return_meta=True` so the kernel driver owns its self-returned continuation sequence.
- `mu/host/js/engine/routing.js`
  - In `runHemisphereRouting` and `runMetabolizationCycle`, replace explicit public packet re-entry loops with bounded public `returnMeta: true` calls carrying `validationMode: 'algorithm_runtime'` and `KERNEL_DRIVER_BOUNDARY_WATCHDOG`.
- `mu/host/js/engine/kernel.js`
  - Preserve public continuation binding checks while allowing same-process internal continuation proofs to avoid repeated hash proof recomputation when object identity proves the exact continuation, domain input, normalized input, projection authority, and watchdog cap.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - Update the JS routing source-shape lock so the outer routing/metabolization callers cannot regress to public `returnPacket` / `continuationState` loops.

Same-wave control artifacts:

- `reports/control_plane/nightly-ci-continuation-boundary-runtime-2026-05-28.md`
- `reports/l4_wave_indicators/nightly-ci-continuation-boundary-runtime-2026-05-28.json`
- `TASKS.md` only for the required same-wave tracker note.

Out of scope:

- Skipping, xfail-ing, deleting, or weakening any nightly, parity, structural, or L4 test.
- GitHub workflow, branch-protection, required-check, or seven-check PR surface changes.
- Ratchet baseline edits.
- Seed content, Stage0 VM semantics, scheduler/registry/loader/checksum/TLV paths, or broad N3 closure.
- `run_review.py` as an operator path.

## Work Items

1. Route this packet through dispatcher-owned Phase B, pre-commit supervisor, and commit executor. Do not use `run_review.py`.
2. Keep the implementation limited to the four implementation files listed above unless Phase B proves a blocking same-wave need.
3. Preserve public direct packet-resume security for external callers and prove public `returnPacket` does not expose the internal proof object.
4. Preserve fail-closed algorithm-runtime rejection for forged, mismatched, or caller-invented continuation state.
5. Run focused tests for the eight failed nightly selectors, routing boundary lock, metabolize-cycle behavior, and JS continuation security subset.
6. Run host-semantics and host-authority ratchets with no increases.
7. Run strict L4 contract for the staged package as `L4_STRUCTURAL`.

## Constraints

- Do not weaken test evidence to reduce runtime.
- Do not remove the continuation security binding guards. Any fast path must be restricted to same-process internal proof identity and must not be available through public `returnPacket` output.
- Do not move new semantic authority into Python or JavaScript helpers. The changes must keep driver ownership and validation boundaries explicit.
- Do not claim the nightly workflow is fixed until GitHub Actions reruns this workflow on the repaired branch or after merge.
- Do not claim broad CI duration closure. This wave repairs the reproduced nightly failures and one proven runtime hot path.

## Stop Conditions

- Stop if public `returnPacket` exposes internal continuation proof data.
- Stop if forged or mismatched continuation tests fail to reject.
- Stop if exact failed nightly selectors still exceed their deadlines/timeouts after the repair.
- Stop if host-semantics or host-authority ratchets increase.
- Stop if Phase B requires widening beyond the scoped runtime files without a separate bounded packet.
- Stop if the dispatcher/Phase B/commit path breaks; any bounded manual recovery must include a same-wave mechanical fix or a precise next-wave automation packet.

## Acceptance Criteria

- Exact failed nightly selector subset passes under nightly xdist shape:
  `PYTHONHASHSEED=0 python3 -m pytest -q -n auto --dist worksteal <eight failed selectors> --tb=short`.
- Focused behavior/source gates pass:
  `PYTHONHASHSEED=0 python3 -m pytest -q tests/structural/test_gate5_meta_circular_parity.py::test_gate5_run_mu_structural_matches_bridge_nonlinear_semantics tests/structural/test_gate5_meta_circular_parity.py::test_gate5_run_mu_structural_records_projection_id_via_bridge_path mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_routing_continuation_driver_uses_bounded_return_meta --tb=short`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_metabolize_cycle_gate.py --tb=short` passes.
- JS continuation security subset passes, including public packet proof confinement and forged continuation rejection.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` passes with no increases.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` passes with no unaccepted authority increase.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id nightly-ci-continuation-boundary-runtime-2026-05-28 --wave-class L4_STRUCTURAL` passes.
- Commit handoff is generated by Phase B/commit executor with touched files and receipt evidence.

## Proof Limit

Local evidence proves the reproduced failing selectors pass and the profiled continuation-boundary hot path is reduced in this worktree. It does not prove GitHub nightly is green until the scheduled workflow or a manual workflow run executes on the repaired code.

FOUNDER_OVERRIDE:nightly-ci-continuation-boundary-runtime-2026-05-28

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `nightly-ci-continuation-boundary-runtime-2026-05-28`
- Active packet: `reports/control_plane/nightly-ci-continuation-boundary-runtime-2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/nightly-ci-continuation-boundary-runtime-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/engine/kernel.js`
  - `mu/host/js/engine/routing.js`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/docs/test_l4_current_state_truth.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `reports/control_plane/nightly-ci-continuation-boundary-runtime-2026-05-28.md`
  - `reports/deferred/non_blocking/nightly-ci-continuation-boundary-runtime-2026-05-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/nightly-ci-continuation-boundary-runtime-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
