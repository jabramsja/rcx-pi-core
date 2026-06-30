# NR-1 nightly hemisphere engine-result numeral routing

Date: 2026-06-29
Status: Phase B (pre-supervisor pending, bridge-converged)
Task: [NR-1]
Wave ID: nightly-nr1-hemisphere-numeral-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Repair the nightly production hemisphere regression by routing engine_result counter fields in StructuralNumbers numeral form across the Python and JavaScript hemisphere boundaries, decoding only at host-facing response surfaces.

## Scope

Urgent nightly regression repair for hemisphere routing only. Carry engine_result counters and any host-int routing payload fields as StructuralNumbers numerals before they reach hemisphere projections, preserve host-facing decode behavior, and mirror the behavior in JavaScript. TASKS.md is the tracker-sync authority for this launched wave.

Files and surfaces in scope:

- mu/host/python/rcx_pi/selfhost/engine_pipeline.py (MODIFY) -- hemisphere routing boundary must route production engine_result fields in structural numeral form and preserve fail-closed validation.
- mu/host/js/engine/routing.js (MODIFY) -- mirror the Python hemisphere numeral-routing behavior for the JS JSON API and engine routing path.
- mu/tests/engine/test_hemisphere_adversarial.py (MODIFY IF NEEDED) -- lock the host-int value and tau_step regression on the Python production boundary.
- mu/tests/parity/test_hemisphere_routing.py (MODIFY IF NEEDED) -- keep direct hemisphere projection tests aligned with numeral engine_result inputs without weakening routing invariants.
- mu/tests/parity/test_js_parity_automated.py (MODIFY IF NEEDED) -- add or update the cross-substrate host-int hemisphere vector so Python and JS prove parity on the failing nightly shape.
- mu/tests/l4_gates/test_metabolize_cycle_gate.py (MODIFY) -- L4 gate evidence for host-int hemisphere numeral routing across Python and JS boundaries.
- reports/l4_wave_indicators/nightly-nr1-hemisphere-numeral-2026-06-29.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- live NOW authorization anchor plus tracker-sync authority. The `[NR-1]` NOW item authorizes the active L4_STRUCTURAL wave; the 2026-06-29 tracker sync note for wave `nightly-nr1-hemisphere-numeral-2026-06-29` is the single source of truth for this packet's L4 fields; the packet derives from both surfaces.

## Work items

1. Reproduce the Python and JS host-int hemisphere failures from current dev before editing.
2. Find the narrowest shared conversion boundary that turns production engine_result host integers into StructuralNumbers numerals before hemisphere matcher var sites see them.
3. Preserve existing non-dict and wrong-shape fail-closed behavior; do not make hemisphere projections accept arbitrary host objects.
4. Mirror the Python behavior in JS so run_hemisphere_routing JSON API and engine-with-routing paths agree.
5. Add or update regression coverage for the exact failing host-int value and tau_step shape, including JS parity.
6. Run the configured evidence command, collect the L4 indicator artifact, and leave commit, push, and merge to the pipeline.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor. Do not manually commit this wave.
- No new host semantic primitive, host arithmetic semantic shortcut, host-only routing rule, or matcher relaxation.
- Do not change hemisphere key authority or projection ordering.
- Keep recurrence, boot1, and workload-contract reconciliation out of this wave except for shared helper reuse that is required by the hemisphere boundary.
- Do not weaken JS parity, seed integrity, reserved-field validation, or invalid-shape rejection tests.
- Do not edit Claude-owned files.

## Stop conditions

- Halt if the only passing fix teaches the matcher or hemisphere projections to accept raw host ints directly.
- Halt if Python and JS require divergent semantics for the same host-int hemisphere vector.
- Halt if non-dict or malformed engine_result values stop failing closed.
- Halt if recurrence or boot1 repair becomes necessary to prove hemisphere routing; split that into NR-2 or NR-4.
- Do not commit without pipeline-produced handoff, review, evidence, and indicator artifact.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/engine/test_hemisphere_adversarial.py mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/parity/test_js_parity_automated.py && python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md mu/host/python/rcx_pi/selfhost/engine_pipeline.py mu/host/js/engine/routing.js mu/tests/engine/test_hemisphere_adversarial.py mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/parity/test_js_parity_automated.py mu/tools/executors/executor_config.json reports/control_plane/nightly-nr1-hemisphere-numeral-2026-06-29_2026-06-29.md reports/l4_wave_indicators/nightly-nr1-hemisphere-numeral-2026-06-29.json --wave-id nightly-nr1-hemisphere-numeral-2026-06-29 --wave-class L4_STRUCTURAL`
- Slow-kernel guard-tests (`run_mu`, `run_mu_structural`, `node`) carry an in-function `# SPEED_OK: <reason>` annotation so they stay out of the green-gate speed lane.

## Post-Commit Pre-Push AST Repair

During commit executor Step 11, pre-push AST police rejected the JS NR-1 implementation because `mu/host/js/engine/routing.js` used `WeakSet` for path-local cycle detection in the engine_result structuralization walk. The same-wave repair replaces that `WeakSet` with an explicit deterministic active-path array and stack mismatch fail-closed check. No new AST_OK_JS marker was added.

Focused repair evidence:

- `bash tools/checks/linters/ast_police_js.sh mu/host/js` passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_hemisphere_adversarial.py mu/tests/l4_gates/test_metabolize_cycle_gate.py --tb=short` passed `82` tests.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short` passed `311` tests.

## Post-Commit Pre-Push Source-Lock Repair

The next pre-push retry exposed two non-semantic control/source-lock issues:

- `mu/tools/executors/executor_config.json` must keep the shipped pager default `route` at `both`; Codex orchestration is selected by bus-local orchestrator state for the active lane, not by narrowing the tracked default.
- `mu/host/js/engine/routing.js` could not contain `while (` inside `runHemisphereRouting` under the JS routing continuation source-lock gate. The same traversal and integer structuralization loops were rewritten as bounded `for` loops while preserving the deterministic active-path cycle check.

Focused repair evidence:

- `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_pipeline_agent_pager.py::test_executor_config_default_pager_route_is_both tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_routing_continuation_drivers_use_bounded_return_meta --tb=short` passed `2` tests.
- `bash tools/checks/linters/ast_police_js.sh mu/host/js` passed.

## Bot-Remediation Numeric Boundary Repair

PR bot review flagged that JS would promote integer-valued floats, while Python promotes only exact `int` leaves. The actionable boundary is narrower: after JSON parsing, JavaScript cannot distinguish token text `3` from `3.0`; both arrive as the same `number`. The final JS contract therefore keeps NR-1's required raw host-int JSON path while failing closed on fractional and unsafe numeric leaves:

- safe integer `number` leaves convert to StructuralNumbers for hemisphere routing;
- non-integer numeric leaves raise `input.invalid_type`;
- unsafe integer numeric leaves raise `input.invalid_type`.

The first automated remediation kept all JS numeric leaves raw and reproduced a pre-push regression: `tests/l4_gates/test_metabolize_cycle_gate.py::TestHemisphereNumeralRoutingGate::test_js_boundary_routes_host_int_value_and_tau_step_at_json_api` failed with `Got: ["route_hemisphere"]`. The same-wave repair restores safe-integer conversion and makes the fractional/unsafe-number fail-closed behavior explicit.

Focused repair evidence:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_metabolize_cycle_gate.py::TestHemisphereNumeralRoutingGate --tb=short` passed `3` tests.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity::test_hemisphere_routing_parity --tb=short` passed `1` test.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py::TestHemisphereRoutingPropertyFuzzer::test_valid_engine_result_routing_parity --tb=short` passed `1` test.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_routing_continuation_drivers_use_bounded_return_meta --tb=short` passed `1` test.
- `bash tools/checks/linters/ast_police_js.sh mu/host/js` passed.

## Acceptance criteria

- The direct Python host-int value and tau_step hemisphere repro returns a five-key hemisphere dict with exactly one populated expected target.
- The JS run_hemisphere_routing JSON API returns success=true for the same host-int hemisphere vector and is content-equal to Python.
- mu/tests/engine/test_hemisphere_adversarial.py passes serially.
- mu/tests/l4_gates/test_metabolize_cycle_gate.py passes serially.
- The existing JS hemisphere routing parity test and property fuzzer pass.
- node mu/host/js/eval_step.js and check_js_debt.sh pass.
- check_host_semantics_ratchet.py reports no host semantic delta.

## Grounding / Authorization

- Task: [NR-1]; wave id `nightly-nr1-hemisphere-numeral-2026-06-29`.
- Governing packet: this file, `reports/control_plane/nightly-nr1-hemisphere-numeral-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the live `[NR-1]` NOW authorization anchor plus the 2026-06-29 tracker sync note for wave `nightly-nr1-hemisphere-numeral-2026-06-29`; the tracker note remains canonical for this packet's L4 fields.
- Authorization: Founder-directed urgent nightly queue from the 2026-06-29 handoff and live instruction: do NR-1 first because hemisphere accounts for the largest nightly failure blast, and include JS parity for the failing hemisphere path.

FOUNDER_OVERRIDE:nightly-nr1-hemisphere-numeral-2026-06-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `nightly-nr1-hemisphere-numeral-2026-06-29`
- Active packet: `reports/control_plane/nightly-nr1-hemisphere-numeral-2026-06-29_2026-06-29.md`
- Indicator artifact: `reports/l4_wave_indicators/nightly-nr1-hemisphere-numeral-2026-06-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
  - `mu/host/js/engine/routing.js`
  - `mu/tests/engine/test_hemisphere_adversarial.py`
  - `mu/tests/l4_gates/test_metabolize_cycle_gate.py`
  - `mu/tests/parity/test_js_parity_automated.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/nightly-nr1-hemisphere-numeral-2026-06-29_2026-06-29.md`
  - `reports/l4_wave_indicators/nightly-nr1-hemisphere-numeral-2026-06-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
