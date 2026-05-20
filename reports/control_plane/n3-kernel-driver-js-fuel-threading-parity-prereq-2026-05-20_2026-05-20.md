# N3-Kernel-Driver-Js-Fuel-Threading-Parity-Prereq-2026-05-20 2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
Purpose: Create the source-proof prerequisite plan routed by the upstream structural fuel source-lock packet before any production max_steps loop reduction is attempted. This packet proves what JavaScript fuel-threading parity evidence is required for the D006 linked-list fuel model, while preserving current production loop truth and keeping runtime implementation out of scope.

## Scope

Files/directories in scope for this Phase A packet:

- `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`.
- `TASKS.md` only for the same-wave `[NEXT-CODEX-POST-REDTEAM]` tracker authority at `TASKS.md:395`.
- Upstream governing packet refs in `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md:171-207`.
- Documentation refs required by that governing packet: `mu/docs/core/L4ExitChecklist.v0.md:90`, `mu/docs/core/L4ExitChecklist.v0.md:185-186`, and `mu/docs/core/L4ExitChecklist.v0.md:207-214`.
- Candidate parity and negative-control test surfaces only as Phase A evidence selection targets. Any test addition or implementation must be locked by a later converged Phase A/Phase B packet before edit.

Out of scope:

- Production Python or JavaScript kernel loop edits.
- Ratchet baselines, debt markers, debt-map comments, marker locations, and semantic-debt thresholds.
- JavaScript fuel-threading implementation.
- Production `max_steps` loop reduction.

## Work items

1. Bind this Phase A plan to the same-wave route at `TASKS.md:395`, including wave id, packet path, `L4_ENABLER` class, G8 target, and the explicit no-production-loop/no-ratchet-baseline limit.
2. Reconcile the upstream source-lock requirement from `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md:171-207` with the cited L4 checklist lines:
   - `L4ExitChecklist.v0.md:90` for unresolved CPS or explicit fuel threading.
   - `L4ExitChecklist.v0.md:185-186` for the D006 research-classification basis.
   - `L4ExitChecklist.v0.md:207-214` for the production prerequisite lock.
3. Identify the minimum parity proof needed to compare a JavaScript linked-list fuel-threading model against current Python D006 research behavior before any production `max_steps` reduction.
4. Identify exact future parity and negative-control tests that would demonstrate the JavaScript model matches D006 behavior without relying on host timers, host exception tables, substrate shortcuts, or host-only accepted sets.
5. Preserve the current active-loop truth named by the upstream packet for `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1172`, `mu/host/python/rcx_pi/selfhost/step_mu.py:1317-1319`, and `mu/host/js/engine/kernel.js:72-77`. This packet does not inspect or edit those production loops.
6. Record that performance profiling and production integration with fuel parameter threading remain later prerequisites even if JavaScript parity proof passes.

## Source-Lock Reconciliation

The upstream governing packet routes this exact prerequisite at `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md:171-207`:

- `:175-180` names wave `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`, task `[NEXT-CODEX-POST-REDTEAM]`, target gate `G8`, default class `L4_ENABLER`, and purpose: prove cross-substrate fuel-threading parity for linked-list fuel before production `max_steps` reduction is attempted.
- `:182-196` requires citations to the L4 checklist, exact parity and negative-control test selection, preservation of current active-loop truth, and deferral of performance plus production integration.
- `:198-207` defines the prerequisite stop conditions: no host timers, host exception tables, thread-state checks, substrate-specific shortcuts, host-only accepted sets, non-comparable proof, comment/marker/baseline-only results, or production loop edits without a later full `L4_STRUCTURAL` packet.

The cited checklist lines mean:

- `mu/docs/core/L4ExitChecklist.v0.md:90`: the `max_steps` reduction path is still unproven and requires CPS or explicit fuel threading. A JavaScript proof must therefore demonstrate explicit fuel threading as structural data, not a host-side timeout or exception discipline.
- `mu/docs/core/L4ExitChecklist.v0.md:185-186`: G8 classification treats `max_steps` as `REDUCIBLE_WITH CPS fuel threading`; D006 proves only a research linked-list fuel model where iteration remains host.
- `mu/docs/core/L4ExitChecklist.v0.md:207-214`: production reduction is locked behind separate productionization prerequisites. For `max_steps`, those prerequisites are JavaScript fuel-threading parity, performance profiling of `O(fuel)` space versus `O(1)` integer, and production integration with fuel parameter threading.

This packet therefore authorizes source-proof planning only. It does not convert the D006 research artifact into production proof and does not authorize any production kernel loop edit.

## Minimum Parity Proof

The minimum acceptable proof for a later JavaScript fuel-threading packet is a cross-substrate comparison against the Python D006 research behavior, not a comparison against production `max_steps` loops.

The JavaScript model must prove all of the following:

- Fuel is represented as Mu data using the same linked-list shape as D006: `null` for empty fuel and `{ "head": null, "tail": <fuel> }` for one node plus the remaining fuel.
- One fuel node is consumed for each attempted step before the terminal status is reported, matching the D006 `fuel_step` order: call the existing step function, take `tail`, then classify `stall` versus `ok`.
- Empty fuel returns the unchanged state with `fuel_exhausted` before any step.
- The status taxonomy matches D006 exactly: `ok`, `stall`, and `fuel_exhausted`.
- The canonical D006 vectors match across Python and JavaScript for final state, termination reason, per-step state sequence, and remaining fuel counts: identity stall, single match, multi-step convergence, fuel exhaustion, and nested Mu structure.
- The JavaScript proof calls the existing JavaScript step/kernel primitive once per fuel node through an adapter; it must not teach the existing projection/match/subst step path to inspect fuel.
- The proof must reject host-only substitutes: timers, exception-classification tables, thread-state checks, substrate-specific shortcuts, host-only accepted result sets, or precomputed answer tables.

Passing this proof would satisfy only the JavaScript parity/source-proof prerequisite. It would not prove production `max_steps` reduction, performance acceptability, or production fuel-parameter integration.

## Future Evidence Test Selection

The following are exact future evidence targets. They are not completed implementation proof in this packet, and this packet does not add or edit tests.

Existing Python reference evidence:

- `tests/research/test_d006_h1_fuel_threading.py:40-51` defines the D006 linked-list fuel shape and construction limitation.
- `tests/research/test_d006_h1_fuel_threading.py:73-94` defines `fuel_step`, including existing-step invocation, one-node consumption, and `ok`/`stall` classification.
- `tests/research/test_d006_h1_fuel_threading.py:97-127` defines `fuel_run` and documents that D006 is still host-loop research behavior.
- `tests/research/test_d006_h1_fuel_threading.py:181-252` provides the success/parity vector baseline.
- `tests/research/test_d006_h1_fuel_threading.py:284-346` provides the fuel-inspection and host-loop limitation guards.
- `tests/research/test_d006_h1_fuel_threading.py:354-411` provides structural fuel properties: valid Mu fuel, monotonic consumption, zero fuel, one fuel, and LOC budget.

Existing negative-control evidence:

- `tests/research/test_d007_h3_negative_control.py:137-168` proves one step is not enough for multi-step convergence.
- `tests/research/test_d007_h3_negative_control.py:170-215` proves fixed unrolling is not a general solution.
- `tests/research/test_d007_h3_negative_control.py:217-257` proves recursion is iteration and can hit host stack limits.
- `tests/research/test_d007_h3_negative_control.py:260-299` proves higher-order composition hides host iteration.
- `tests/research/test_d007_h3_negative_control.py:307-363` summarizes that no tested strategy is both general and iteration-free.

Existing JavaScript parity harness patterns that a later packet may reuse:

- `mu/tests/parity/test_js_parity_automated.py:37-59` shows the stdin-based Node JSON helper pattern.
- `mu/tests/parity/test_js_parity_automated.py:62-94` already compares Python and JavaScript linked-list conversion behavior.
- `mu/tests/parity/test_exhaustion_parity.py:211-229` shows a JSON API bridge into the JavaScript runtime.
- `mu/tests/parity/test_exhaustion_parity.py:232-330` shows cross-substrate vector comparison structure.

Required future tests, to be locked by a later implementation packet in `mu/tests/parity/test_js_fuel_threading_parity.py` or an explicitly equivalent same-purpose file:

- `test_js_fuel_run_matches_python_d006_identity_stall`
- `test_js_fuel_run_matches_python_d006_single_match`
- `test_js_fuel_run_matches_python_d006_multi_step_convergence`
- `test_js_fuel_run_matches_python_d006_fuel_exhaustion`
- `test_js_fuel_run_matches_python_d006_nested_mu_structure`
- `test_js_zero_fuel_immediate_exhaustion_matches_python_d006`
- `test_js_one_fuel_consumes_exactly_one_step_matches_python_d006`
- `test_js_fuel_consumption_is_monotonic_linked_list`
- `test_js_fuel_adapter_calls_existing_step_once_per_fuel_node`
- `test_js_step_path_does_not_inspect_fuel`
- `test_js_fuel_is_mu_linked_list_not_integer_counter`
- `test_js_fuel_parity_harness_rejects_host_timer_or_thread_state_mechanisms`
- `test_js_fuel_parity_harness_rejects_host_exception_tables`
- `test_js_fuel_parity_harness_rejects_host_only_accepted_sets`
- `test_js_single_step_negative_control_fails_multi_step`
- `test_js_fixed_unroll_negative_control_is_not_general`
- `test_js_recursion_negative_control_is_host_iteration_or_rejected`
- `test_js_compose_n_negative_control_exposes_host_iteration`

These test names are the minimum source-proof selection set. A later packet may add more tests, but it must not drop any of these proof classes unless current code truth shows a named class has already been satisfied and the tracker routes only the remaining gap.

## Current Production Loop Truth

This packet preserves the current active-loop truth named by the upstream packet and does not re-inspect or edit production loop bodies:

- `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1172`
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1317-1319`
- `mu/host/js/engine/kernel.js:72-77`

Those references remain production-loop truth inputs for later source-lock or structural packets. They are not write authorization in this packet.

## Deferred Production Prerequisites

Even if the future JavaScript fuel-threading parity proof passes, later packets must still lock and prove:

- Performance profiling for `O(fuel)` linked-list space versus current `O(1)` integer budget behavior.
- Production integration with explicit fuel parameter threading.
- Rollback/default behavior for production adoption.
- Ratchet expectation for any claimed host-loop or marker reduction.
- Bridge-converged acceptance criteria for production proof.

## Constraints

- This is a control-surface/source-proof packet only.
- Do not edit production Python or JavaScript kernel loops.
- Do not change ratchet baselines, debt markers, debt-map comments, marker locations, or semantic-debt thresholds.
- Do not implement JavaScript fuel threading in this packet.
- Do not solve production `max_steps` loop reduction in this packet.
- Do not use stale packet wording as proof that any listed implementation item remains unlanded; current code truth controls when later implementation packets inspect code.
- Do not expand into unrelated runtime, seed, scheduler, registry, Stage0, bridge, executor, or CI repair work.

## Stop conditions

- Stop if JavaScript fuel parity would require host timers, host exception tables, thread-state checks, substrate-specific shortcuts, or host-only accepted sets.
- Stop if the proof cannot be made parity-comparable with Python D006 linked-list fuel behavior.
- Stop if the only available result is a comment, marker, debt-map, or baseline adjustment while production loop behavior remains unchanged.
- Stop before production loop edits unless a later packet locks a full `L4_STRUCTURAL` write set, tests, rollback/default behavior, ratchet expectation, and bridge-converged acceptance criteria.
- Stop if Phase A evidence shows the prerequisite has already been satisfied by current code; in that case, remove the satisfied item from pending work and route only the remaining proof gap.

## Acceptance criteria

- The packet contains the required Phase A sections: Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization.
- The packet cites `TASKS.md:395` as the same-wave `[NEXT-CODEX-POST-REDTEAM]` authorization for `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`.
- The packet cites the upstream governing packet route at `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md:171-207`.
- The packet includes same-wave `FOUNDER_OVERRIDE:n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20` authorization for control-surface `L4_ENABLER` automation.
- The packet identifies D006 JavaScript fuel-threading parity as prerequisite/source-proof work only and does not authorize production loop edits.
- The packet names parity and negative-control test selection as future Phase A evidence work, not as completed implementation proof.
- The packet keeps current production loop truth references intact and explicitly defers performance profiling plus production fuel-parameter integration to later packets.

## Grounding / Authorization

- `TASKS.md:395` authorizes this same-wave `[NEXT-CODEX-POST-REDTEAM]` route as `Class: L4_ENABLER`, `target_gate_id: G8`, `Packet: reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`, with evidence that the builder-created tracker authority routes the PR #1003 source-lock prerequisite into Phase A and does not authorize production kernel loop edits or ratchet baseline changes.
- Upstream governing packet: `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md:171-207`.
- L4 checklist grounding: `mu/docs/core/L4ExitChecklist.v0.md:90`, `mu/docs/core/L4ExitChecklist.v0.md:185-186`, and `mu/docs/core/L4ExitChecklist.v0.md:207-214`.
- Same-wave control-surface authorization: `FOUNDER_OVERRIDE:n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`.
- This packet is the governing packet for the Phase A prerequisite rewrite after bridge review convergence.

## Validation Boundary

The locked plan lists no Phase B-local validation commands for this implementer. Startup/preflight, attestation, dispatcher, commit, push, PR, merge, pre-push, and closeout commands are executor-owned context for this Phase B boundary and are not authorized here.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `cd19400d4f120470e23296967ac3c25116d1e7d737d29f842fcc27618552adb1`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20 --output reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
