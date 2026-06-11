# N3-Kernel-Driver-Max-Steps-Structural-Budget-Decision-2026-06-11 2026-06-11

Date: 2026-06-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11
Phase-A-Lock: LOCKED
Purpose: GOAL: A Phase-A-ONLY design DECISION wave (no runtime implementation while Phase-A-Lock is UNLOCKED). Make and LOCK a single binary determination about the residual no-fuel kernel-driver @host_iteration watchdog loops in the Python step_kernel_mu and the JavaScript _stepKernelCore -- the last two tracked host-semantics markers blocking a tracked-marker floor reduction below 5.

## Scope

Phase-A binary DECISION wave: lock whether the residual no-fuel kernel-driver host_iteration markers (`step_kernel_mu`, `_stepKernelCore`) are REDUCIBLE via a structural Mu-data step budget, or ACCEPTED-IRREDUCIBLE at the max_steps watchdog boundary per L3 Canonical Truth. The decision is recorded in THIS packet; no runtime/baseline edit anywhere.

**Write scope -- the ONLY files this wave may modify:**

1. `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md` -- this packet. The budget-source census, the locked A/B decision, and the smallest-next-bounded-packet spec are recorded here and nowhere else.
2. `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json` -- mechanical indicator artifact, produced ONLY by the `indicator_collection_command` (no hand edit).
3. `TASKS.md` -- canonical tracker note for this wave, written ONLY via `mu/tools/executors/tracker_sync_note.py` (pipeline automation; no freeform hand edit).

**Read-only grounding scope -- read to ground the census/decision; MUST NOT be edited by this wave:**

- `mu/host/python/rcx_pi/selfhost/step_mu.py` -- contains the Python kernel driver `step_kernel_mu` (one of the two residual @host_iteration markers).
- Python no-fuel caller surfaces under `mu/host/python/rcx_pi/selfhost/` named in the supervisor grounding: `step_mu`, `run_algorithm_meta_circular`, `run_mu_structural`.
- `mu/host/js/engine/kernel.js` -- contains the JS kernel driver `_stepKernelCore` (the other residual @host_iteration marker).
- `mu/host/js/core/constants.js` -- contains the `_stepKernelCore` marker/classification reference.
- JS no-fuel caller surfaces under `mu/host/js/` named in the supervisor grounding: routing/metabolization (incl. `runMetabolizationCycle`), `runAlgorithmWithBridge`, `runStructural`, JSON API vector/hemisphere paths, JS self-tests.
- Prior kernel-driver lineage packets under `reports/control_plane/` (enumerated in Grounding / Authorization below).
- `TASKS.md` tracker note for this wave id (authorization; line reference in Grounding / Authorization below).
- L3 Canonical Truth marker-truth wording under `mu/docs/` (the "execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics" clause) -- read-only in this wave.

Anything not listed above is out of scope for this wave.

- `reports/deferred/non_blocking/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks, all confined to the write scope above:

- **WI-1 -- Python no-fuel budget-source census.** From the read-only Python grounding scope, enumerate by function name EVERY no-fuel path into `step_kernel_mu` (at minimum the supervisor-named callers: `step_mu`, `run_algorithm_meta_circular`, `run_mu_structural`, plus any additional no-fuel entry discovered while enumerating). For each path, classify the step-budget source as DATA-DETERMINED (input-structure-driven, supplyable as Mu fuel without a host count) or HOST-COUNT-DETERMINED (max_steps or any host numeric derived from it). Record the census as a per-row `file:function -> classification` table in this packet. Bound: census only; zero edits outside this packet.
- **WI-2 -- JS no-fuel budget-source census.** Same census for `_stepKernelCore` from the read-only JS grounding scope (at minimum: routing/metabolization incl. `runMetabolizationCycle`, `runAlgorithmWithBridge`, `runStructural`, JSON API vector/hemisphere paths, JS self-tests, plus any additional no-fuel entry discovered). Same per-row classification table in this packet. Bound: census only; zero edits outside this packet.
- **WI-3 -- Apply the locked discriminator and lock the decision.** Choose (A) REDUCIBLE ONLY if every row of BOTH censuses is DATA-DETERMINED (common coverage across ALL no-fuel callers). ANY host-count-determined row (e.g. `runMetabolizationCycle` deriving its budget from a host count) forces (B) ACCEPTED-IRREDUCIBLE or a STOP. A single data-determined caller is NOT sufficient. Record the locked A-or-B decision in this packet with a source-grounded justification citing the census rows.
- **WI-4 -- Record the smallest next bounded packet spec** as text in this packet (no new packet file is created in this wave). If (A): name the exact Mu-data budget representation, the affected drivers, the focused parity/marker-truth gates, and the proof obligation that the new fuel is data-determined not host-count-determined. If (B): name the precise NON-runtime marker-truth updates (`tests/l4_gates` marker-truth gates and/or `mu/docs` marker-truth wording) that record the two markers as an ACCEPTED boundary at the max_steps watchdog rather than a deferred reduction TODO.
- **WI-5 -- Zero-delta ratchet evidence.** Run the evidence_command (`python3 mu/tools/checks/check_host_semantics_ratchet.py --json && python3 tools/checks/check_host_authority_inventory_ratchet.py`) and record in this packet that no marker/authority count changed. Produce the indicator artifact via the `indicator_collection_command`.

## Constraints

NOT in scope for this wave:

- NO runtime edit: no file under `mu/host/python/rcx_pi/selfhost/` or `mu/host/js/` may be modified. Reading them is in scope; editing them is not.
- NO ratchet baseline edit (host-semantics or host-authority-inventory baselines untouched).
- NO seed/registry/Stage0/scheduler/loader/binary edit.
- NO marker movement while Phase-A-Lock is UNLOCKED: no @host_iteration marker may be added, removed, or reclassified in code by this wave.
- NO test or doc edits: even the (B)-branch marker-truth updates are the NEXT packet's implementation work; this wave only specifies them in WI-4.
- NO re-derivation or re-attempt of the four prior established results (Grounding (1)-(4) in the supervisor request below); they are binding inputs.
- NOT an open-ended "design how to make max_steps structural in general" wave; only the narrow binary A/B determination with source-grounded justification.
- NO new files except the mechanical indicator artifact named in the write scope.

## Stop conditions

Stop the wave (record a NO-GO/STOP in this packet instead of forcing a result) when ANY of the following holds:

1. The no-fuel caller set into either driver cannot be exhaustively enumerated by named function from the read-only grounding scope (e.g. dynamic/unknown call paths) -- record the enumeration gap; do NOT guess common coverage.
2. Classifying any caller's budget source would require a runtime edit, instrumentation, or any modification outside the write scope -- that breaches Phase-A-only.
3. The census is MIXED and an honest (B) classification cannot be written within the L3 Canonical Truth wording -- escalate to founder rather than forcing (A) or (B).
4. The evidence_command shows ANY marker/authority count delta during this wave -- the wave is mis-scoped; do NOT amend baselines to make it pass.
5. Phase-A-Lock flips to LOCKED mid-wave, or the TASKS.md tracker-note authorization for this wave id is missing or changed at execution time.
6. Grounding beyond the read-only scope list appears necessary to decide A-vs-B -- stop and report rather than widening scope.

## Acceptance criteria

1. A locked A-or-B decision recorded in this packet, justified by a budget-source CENSUS of EVERY no-fuel path/caller into BOTH `step_kernel_mu` and `_stepKernelCore`, by function name, with a per-row DATA-DETERMINED vs HOST-COUNT-DETERMINED classification (WI-1..WI-3).
2. (A) REDUCIBLE is chosen ONLY with 100% data-determined rows across BOTH censuses (common coverage); otherwise the packet records (B) ACCEPTED-IRREDUCIBLE or a STOP per the stop conditions.
3. The smallest next bounded packet spec is recorded in this packet per WI-4 (branch-appropriate to the locked decision).
4. Ratchet evidence recorded: evidence_command output proving this wave changes no marker/authority counts; indicator artifact produced at the `indicator_artifact_ref` path.
5. The wave-owned diff touches ONLY the write scope: this packet, the indicator artifact, and the automation-written TASKS.md tracker note. No runtime/baseline/test/doc edit.

## Grounding / Authorization

**TASKS.md authorization (canonical):** Tracker sync note dated 2026-06-11 for wave id `n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11` (TASKS.md, currently line 528) authorizes this wave as Class: L4_ENABLER, target_gate_id: G8, with Packet: this file.

**Authorization:** wave-bound founder override for this control-surface L4_ENABLER packet, matching the TASKS.md tracker note verbatim so commit automation can derive the same-wave override mechanically:

FOUNDER_OVERRIDE:n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11

**Governing packet:** this file (`reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md`).

**Prior kernel-driver lineage packets (read-only grounding; sources of the four established results):**

- `reports/control_plane/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.md`
- `reports/control_plane/n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20_2026-05-20.md`
- `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
- `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
- `reports/control_plane/n3-kernel-driver-mu-continuation-state-runtime-2026-05-20_2026-05-20.md` -- established result (2): the Mu-owned KernelDriverContinuationState runtime exists.
- `reports/control_plane/n3-kernel-driver-post-continuation-marker-reduction-2026-05-22_2026-05-22.md` -- established result (4): post-continuation marker reduction was NO-GO.

**Policy grounding:** L3 Canonical Truth clause -- "execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics" -- governs the (B) branch classification.

## Request from Post-Merge Supervisor

GOAL: A Phase-A-ONLY design DECISION wave (no runtime implementation while Phase-A-Lock is UNLOCKED). Make and LOCK a single binary determination about the residual no-fuel kernel-driver @host_iteration watchdog loops in the Python step_kernel_mu and the JavaScript _stepKernelCore -- the last two tracked host-semantics markers blocking a tracked-marker floor reduction below 5.

THE BINARY DECISION TO LOCK (choose exactly one, with a precise source-grounded justification):
(A) REDUCIBLE: the residual no-fuel watchdog @host_iteration marker can be HONESTLY removed/demoted to a non-host-iteration (BOUNDARY/watchdog) classification by representing the no-fuel step budget as STRUCTURAL Mu data the loop consumes (supplied-or-derived Mu fuel owns progress; max_steps/maxSteps becomes a pure numeric watchdog bound), WITHOUT constructing compatibility fuel from max_steps (which only MOVES host authority) and WITHOUT breaking the public no-fuel caller contract, AND ONLY when EVERY no-fuel path into BOTH drivers has a data-determined budget (COMMON COVERAGE) -- a single data-determined caller is NOT sufficient, because the residual watchdog loop serves every no-fuel path and cannot be demoted while ANY path still needs a host count. If (A): the deliverable is a LOCKED smaller implementation packet naming the exact Mu-data budget representation, the affected drivers, the focused parity/marker-truth gates, and the proof the new fuel is data-determined not host-count-determined.
(B) ACCEPTED-IRREDUCIBLE: the residual watchdog loop is an accepted host resource-bounding boundary per the L3 Canonical Truth that "execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics", because every no-fuel caller's termination budget is ultimately a host numeric bound (max_steps) with no data-determined structural budget available without moving authority. If (B): the deliverable is a LOCKED classification decision + the precise marker-truth doc/test updates (NON-runtime: tests/l4_gates marker-truth gates and/or mu/docs marker-truth wording) that record the two markers as an ACCEPTED boundary at the max_steps watchdog rather than a deferred reduction TODO, so this frontier stops being re-attempted as an open reduction.

GROUNDING (build on these established results; do NOT re-derive or re-attempt them): four prior bounded waves already established -- (1) direct omitted-fuel public-boundary retirement is REJECTED because production callers (Python step_mu / run_algorithm_meta_circular / run_mu_structural, JS routing/metabolization / runAlgorithmWithBridge / runStructural, JSON API vector/hemisphere paths, JS self-tests) depend on omitted fuel for compatibility; (2) a Mu-owned KernelDriverContinuationState runtime already exists; (3) constructing compatibility fuel from max_steps just MOVES the host count into fuel construction (the trap); (4) the post-continuation marker-reduction wave was NO-GO because both drivers still own transition progress in host control flow for the no-fuel path. This wave does NOT retry (1)-(4); it makes the FINAL A-vs-B determination. The DISCRIMINATOR is whether EVERY no-fuel path into step_kernel_mu and _stepKernelCore has a DATA-DETERMINED (input-structure-driven) step budget supplyable as Mu fuel without a host count (COMMON COVERAGE across ALL no-fuel callers). A MIXED budget census -- some callers data-determined, others host-count/max_steps-determined (e.g. runMetabolizationCycle deriving its budget from a host count) -- is NOT sufficient for REDUCIBLE and MUST resolve to (B) ACCEPTED-IRREDUCIBLE or a STOP, because the residual watchdog loop serves every no-fuel path and cannot be honestly demoted while any path still needs a host count. A single data-determined caller does NOT make the marker reducible.

CONSTRAINTS / OUT OF SCOPE: Phase A only -- NO runtime edit, NO ratchet baseline edit, NO seed/registry/Stage0/scheduler/loader/binary edit, NO marker movement while Phase-A-Lock is UNLOCKED. Reading the kernel drivers + their callers + the prior packets to ground the decision is in scope; editing them is not. Do NOT scope this as "design how to make max_steps structural in general" (open-ended) -- scope it as the narrow binary A/B determination with a source-grounded justification. The deliverable is the LOCKED decision (A or B) + the single smallest next bounded packet implied by it.

ACCEPTANCE: a locked A-or-B decision with a precise source-grounded justification = a budget-source CENSUS of EVERY no-fuel path/caller by function name, with REDUCIBLE chosen ONLY if ALL are data-determined (common coverage) and ACCEPTED/STOP otherwise + the smallest next bounded packet; ratchet evidence that this wave changes no marker/authority counts; no runtime/baseline edit.

Routed next-candidate:
n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11 --output reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11 --output reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

## Decision Record (Phase B implementation of the locked Phase A plan)

### Enumeration method (exhaustiveness proof for stop condition 1)

Direct call sites were enumerated mechanically, not by memory, then closed under transitive fan-in:

- Python: a repo-wide search for `step_kernel_mu(` over `mu/` and `tools/` (excluding `mu/tests/`) finds exactly three production call sites, all inside `mu/host/python/rcx_pi/selfhost/step_mu.py`, enclosed by `run_algorithm_meta_circular`, `step_mu`, and `run_mu_structural`. The caller set was then closed under transitive fan-in by sweeping production callers of every chain function (`run_mu`, `_run_sub_algorithm`, `_boundary_op_run_trace`, `_boundary_op_run_algorithm`, `_service_boundary_effect`, `run_engine_pipeline`/`_run_engine_recursive`, `run_hemisphere_routing`, `run_metabolization_cycle`, `run_engine_with_routing`, `_collect_ontology_evidence`): every production call site of the chain lives in `step_mu.py` or `engine_pipeline.py`, and `mu/host/python/rcx_pi/step_mu.py` is a one-line re-export shim adding no call site. Test files enter via the driver or its chain entries and are recorded as a census category row.
- JavaScript: a tree-wide search for `_stepKernelCore` finds its definition plus call sites only in `mu/host/js/engine/kernel.js` (`stepKernel`, `runStructural`, and the `_vmConfigTrust.makeStepKernelCoreRunner` factory) and the classification comment in `mu/host/js/core/constants.js`. The single factory consumer is `runAlgorithmWithBridge` in `mu/host/js/engine/pipeline.js`. The caller set was then closed under transitive fan-in by sweeping production callers of `stepKernel`, `runStructural`, `stepKernelStructural`, `runAlgorithmWithBridge`, `runSubAlgorithm`, `runEnginePipeline`/`runEnginePipelineRecursive`, `runHemisphereRouting`, `runMetabolizationCycle`, and `runEngineWithRouting` under `mu/host/js/`, and by enumerating the JSON API dispatch action-by-action (all 22 `request.action` branches in `mu/host/js/api/json_handlers.js`). The bootstrap evaluator `step`/`run` in `mu/host/js/core/bootstrap_core.js` does NOT reach `_stepKernelCore`; the JSON actions that drive it are recorded in the exclusion note below.

Round-1 bridge review found the pre-closure census incomplete (missing `_collect_ontology_evidence`, `run_metabolization_cycle`, and the `step_kernel_meta` action); the closure sweep above restored those rows and additionally surfaced `run_engine_with_routing` (Python) plus the `run_hemisphere_routing` / `run_metabolization_cycle` JSON actions and the exported `stepKernelStructural` wrapper (JS). No dynamic or unknown call paths into either driver were found. The no-fuel caller set is exhaustively enumerable by named function; stop condition 1 does not fire.

### WI-1 -- Python no-fuel budget-source census (`step_kernel_mu`)

No-fuel semantics (code truth): when `kernel_fuel` is omitted, `step_kernel_mu` sets `fuel_cursor = None` and the transition loop is bounded solely by `steps_used >= watchdog_cap`, where `watchdog_cap = max_steps` (signature default `max_steps: int = 10000`). Omitted fuel never seeds `remaining_fuel` from `max_steps` (asserted by the docstring and by the marker-truth gate in `mu/tests/docs/test_l4_current_state_truth.py`).

Direct no-fuel callers:

| Row | file:function | No-fuel call shape | Step-budget source | Classification |
|-----|---------------|--------------------|--------------------|----------------|
| PY-1 | `mu/host/python/rcx_pi/selfhost/step_mu.py:step_mu` | `step_kernel_mu(projections, input_value)` -- `kernel_fuel` omitted, `max_steps` omitted | Driver default `max_steps=10000`. The public contract `step_mu(projections, input_value)` exposes NO budget parameter, so every transitive caller inherits the host default count | HOST-COUNT-DETERMINED |
| PY-2 | `mu/host/python/rcx_pi/selfhost/step_mu.py:run_algorithm_meta_circular` | `step_kernel_mu(projections, input_value, kernel_mode="bridge", validation_mode="algorithm_runtime")` -- `kernel_fuel` omitted, `max_steps` omitted | Driver default `max_steps=10000`; public contract exposes NO budget parameter | HOST-COUNT-DETERMINED |
| PY-3 | `mu/host/python/rcx_pi/selfhost/step_mu.py:run_mu_structural` | inner `step_kernel_mu(..., return_meta=True)` once per outer `for i in range(max_steps)` iteration; `kernel_fuel` omitted | Own parameter `max_steps: int = 1000` (host numeric) bounds the outer loop; each inner driver call additionally runs on the driver default `10000` | HOST-COUNT-DETERMINED |

Indirect no-fuel entries discovered while enumerating (fan-in to PY-1..PY-3):

| Row | file:function | Path into the driver | Step-budget source | Classification |
|-----|---------------|----------------------|--------------------|----------------|
| PY-4 | `mu/host/python/rcx_pi/selfhost/step_mu.py:run_mu` | calls `step_mu` once per `for i in range(max_steps)` | Own parameter `max_steps: int = 1000` (host numeric) + inherited PY-1 default | HOST-COUNT-DETERMINED |
| PY-5 | `mu/host/python/rcx_pi/selfhost/step_mu.py:_run_sub_algorithm` | calls `run_algorithm_meta_circular` once per `for _ in range(max_iterations)` | `max_iterations` host numeric supplied by the engine pipeline | HOST-COUNT-DETERMINED |
| PY-6 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:_boundary_op_run_trace` | calls `run_mu_structural(projs, value, max_steps=trace_max_steps)` | API-supplied integer `req_input["max_steps"]`, else default `100`; hard host cap `_MAX_BOUNDARY_TRACE_STEPS = 10000`. A caller-supplied integer is a host count passed through the API boundary, not input-structure-derived data | HOST-COUNT-DETERMINED |
| PY-7 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:_boundary_op_run_algorithm` | calls `_run_sub_algorithm(algo_projs, req_input, max_algorithm_iterations)` | `max_algorithm_iterations` host numeric | HOST-COUNT-DETERMINED |
| PY-8 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:run_engine_pipeline` (and `_run_engine_recursive`) | drives boundary ops PY-6/PY-7 | Defaults `max_algorithm_iterations: int = 50`, deprecated `max_iterations` override -- host numerics | HOST-COUNT-DETERMINED |
| PY-9 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:run_hemisphere_routing` | calls `run_mu_structural(projs, wrapped, max_steps=30, ...)` | Host numeric literal `30` | HOST-COUNT-DETERMINED |
| PY-10 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:_collect_ontology_evidence` | calls `run_mu(projs, wrapped, max_steps=5000)` for structural trace walking; activated one-shot via the opt-in `collect_ontology_candidate_evidence` flag inside `_service_boundary_effect` (boundary-effect servicing on the PY-8 engine surfaces) | Host numeric literal `5000` | HOST-COUNT-DETERMINED |
| PY-11 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:run_metabolization_cycle` | calls `run_mu(projs, wrapped, max_steps=step_budget)` | `step_budget = max(20, 4 * entry_count + 10)` where `entry_count` is produced by the host counting pass `count_hemisphere_entries` and combined by host arithmetic -- the Python analog of JS-5: input-structure-INFORMED but host-count-REALIZED | HOST-COUNT-DETERMINED |
| PY-12 | `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:run_engine_with_routing` | chains `run_engine_pipeline` (PY-8) -> `run_hemisphere_routing` (PY-9) -> `run_metabolization_cycle` (PY-11) | The chained rows' host numerics, forwarded via `**engine_kwargs` | HOST-COUNT-DETERMINED |
| PY-13 | Python test surfaces under `mu/tests/` calling `step_kernel_mu` directly or via its chain entries (category row; e.g. `mu/tests/hemisphere_helpers.py` calls `run_mu(..., max_steps=20)`) | direct and chain-entry no-fuel calls | Test-chosen explicit `max_steps` host numerics | HOST-COUNT-DETERMINED |

Python census result: 13 of 13 rows HOST-COUNT-DETERMINED; 0 rows DATA-DETERMINED.

### WI-2 -- JS no-fuel budget-source census (`_stepKernelCore`)

No-fuel semantics (code truth): `callerSuppliedFuel = kernelFuel !== undefined`; with fuel omitted the transition loop is bounded solely by `watchdogCap = maxSteps`, a mandatory finite-integer parameter validated at entry.

Direct callers:

| Row | file:function | No-fuel call shape | Step-budget source | Classification |
|-----|---------------|--------------------|--------------------|----------------|
| JS-1 | `mu/host/js/engine/kernel.js:stepKernel` | forwards `options.kernelFuel` only when the option is present; no-fuel otherwise | `options.maxSteps` integer, default `10000` (host numeric) | HOST-COUNT-DETERMINED |
| JS-2 | `mu/host/js/engine/kernel.js:runStructural` | inner `_stepKernelCore(..., 10000, ..., undefined, ...)` once per outer `for (let i = 0; i < maxSteps; i++)` | Own parameter `maxSteps = 10000` default (outer host numeric) + inner host literal `10000` | HOST-COUNT-DETERMINED |
| JS-3 | `mu/host/js/engine/pipeline.js:runAlgorithmWithBridge` (sole consumer of `_vmConfigTrust.makeStepKernelCoreRunner`) | `runStepKernelCore(..., 10000)` with fuel `undefined`, inside `while (steps < limit)` | `limit = maxSteps ?? 200` (host numeric) + inner host literal `10000` | HOST-COUNT-DETERMINED |

Indirect no-fuel entries (fan-in, by named function):

| Row | file:function | Path into the driver | Step-budget source | Classification |
|-----|---------------|----------------------|--------------------|----------------|
| JS-4 | `mu/host/js/engine/routing.js:runHemisphereRouting` | calls `stepKernel` once per `for (let i = 0; i < limit; i++)` | `limit = 30` host literal; inner `maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG` (host constant `1000`) | HOST-COUNT-DETERMINED |
| JS-5 | `mu/host/js/engine/routing.js:runMetabolizationCycle` | calls `stepKernel` once per `for (let i = 0; i < stepBudget; i++)` | `stepBudget = Math.max(20, 4 * entryCount + 10)` where `entryCount` is produced by the host counting loop `countHemisphereEntries` and combined by host arithmetic; inner per-call budget is the host constant `KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000`. The budget is input-structure-INFORMED but host-count-REALIZED: it exists only as a host integer computed by host counting/arithmetic, and supplying it as Mu fuel would construct fuel from a host-computed count -- exactly the established-result-(3) trap. This is the row the supervisor request pre-named as host-count-determined | HOST-COUNT-DETERMINED |
| JS-6 | `mu/host/js/engine/routing.js:runEngineWithRouting` | chains `runEnginePipeline`/`runEnginePipelineRecursive` then JS-4 then JS-5 | Engine option host numerics (JS-10) plus JS-4/JS-5 budgets | HOST-COUNT-DETERMINED |
| JS-7 | `mu/host/js/engine/pipeline.js:runSubAlgorithm` | calls `runAlgorithmWithBridge(..., 200, ...)` once per `for (let i = 0; i < maxIterations; i++)` | `maxIterations` host numeric + inner host literal `200` | HOST-COUNT-DETERMINED |
| JS-8 | `mu/host/js/engine/pipeline.js:boundaryOpRunTrace` | calls `runStructural(..., traceMaxSteps, ...)` | API-supplied integer `max_steps`, else default `100`; hard host cap `MAX_BOUNDARY_TRACE_STEPS = 10000` | HOST-COUNT-DETERMINED |
| JS-9 | `mu/host/js/engine/pipeline.js:boundaryOpRunAlgorithm` | calls `runSubAlgorithm(..., maxAlgorithmIterations, ...)` | `maxAlgorithmIterations` host numeric | HOST-COUNT-DETERMINED |
| JS-10 | `mu/host/js/engine/pipeline.js:runEnginePipeline` and `runEnginePipelineRecursive` | drive boundary ops JS-8/JS-9 | Options `maxSteps = 100`, `maxAlgorithmIterations` defaults -- host numerics; recursion depth capped by host constant `BOOT1_MAX_REENTRY_DEPTH = 20` | HOST-COUNT-DETERMINED |
| JS-11 | `mu/host/js/api/json_handlers.js` actions `run_vector`, `run_all_vectors` (JSON API vector paths) | `stepKernel(..., { maxSteps: 100, ... })` | Host literal `100` | HOST-COUNT-DETERMINED |
| JS-12 | `mu/host/js/api/json_handlers.js` actions `run_recurrence`, `run_structural_trace` | `runStructural(..., maxSteps ?? 100, ...)` | API-supplied integer else `100`, guarded by `guardMaxSteps` against host cap `API_MAX_STEPS = 10000` | HOST-COUNT-DETERMINED |
| JS-13 | `mu/host/js/api/json_handlers.js` actions `run_recurrence_with_bridge`, `run_exhaustion_with_bridge` | `runAlgorithmWithBridge(..., maxSteps, ...)` | API-supplied integer else inner default `200` | HOST-COUNT-DETERMINED |
| JS-14 | `mu/host/js/api/json_handlers.js` action `run_hemisphere` (JSON API hemisphere path) | `stepKernel({ maxSteps: API_KERNEL_DRIVER_BOUNDARY_WATCHDOG, ... })` once per `while (steps < limit)` | `limit = maxSteps ?? 100` API integer; inner host constant `API_KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000` | HOST-COUNT-DETERMINED |
| JS-15 | `mu/host/js/api/json_handlers.js` actions `run_engine_pipeline`, `run_engine_with_routing`, `run_engine_pipeline_meta` | engine pipeline / routing chains (JS-6/JS-10) | `maxEngineIterations ?? 20`, `maxAlgorithmIterations ?? 50`, host caps `API_MAX_ENGINE_ITERATIONS = 100`, `API_MAX_ALGORITHM_ITERATIONS = 200` | HOST-COUNT-DETERMINED |
| JS-16 | `mu/host/js/api/json_handlers.js` action `run_hemisphere_routing` | calls `runHemisphereRouting` (JS-4) directly | JS-4's internal host budgets (`limit = 30` literal; `KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000`) | HOST-COUNT-DETERMINED |
| JS-17 | `mu/host/js/api/json_handlers.js` action `run_metabolization_cycle` | calls `runMetabolizationCycle` (JS-5) directly | JS-5's host-count-REALIZED `stepBudget` plus the host constant `KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000` | HOST-COUNT-DETERMINED |
| JS-18 | `mu/host/js/api/json_handlers.js` action `step_kernel_meta` | `stepKernel(kernelProjs, input, domainProjs ?? [], kernelOptions)` plus the continuation re-entry `while (packet.kind === 'continuation')` loop; `kernelFuel` is forwarded ONLY when `Object.hasOwn(request, 'kernelFuel')`, so omitted-fuel requests run the no-fuel path | `maxSteps: reqMaxSteps ?? 100` -- API-supplied integer guarded by `guardMaxSteps` against host cap `API_MAX_STEPS = 10000`, else host literal `100`; same budget on each continuation re-entry | HOST-COUNT-DETERMINED |
| JS-19 | `mu/host/js/engine/kernel.js:stepKernelStructural` | exported public wrapper forwarding to `runStructural` (JS-2); the surface exposes no fuel parameter, so every call is no-fuel | `options.maxSteps` integer, default `10000` (host numeric); sole live consumer is the JS self-test in `mu/host/js/tests/self_tests.js` with host literal `100` | HOST-COUNT-DETERMINED |
| JS-20 | `mu/host/js/tests/self_tests.js` (JS self-tests; category row) | direct `stepKernel`/`runStructural`/`stepKernelStructural` calls | Test-chosen host literals (e.g. `100`, `10`, `5`) | HOST-COUNT-DETERMINED |

Exclusions recorded for honesty: JSON API actions `run_exhaustion` and `step_metabolization` drive the bootstrap evaluator `step()` from `mu/host/js/core/bootstrap_core.js`, which never enters `_stepKernelCore`; they are therefore not rows in this census. The remaining JSON actions (`get_constants`, `normalize_roundtrip`, `validate_mu`, `validate_reserved_fields`, `validate_algorithm_runtime_fields`, `hash_trace`, `list_actions`) reach no kernel driver (verified per action; `hash_trace` calls the hashing-only `hashTraceForRecurrence`).

JS census result: 20 of 20 rows HOST-COUNT-DETERMINED; 0 rows DATA-DETERMINED.

### WI-3 -- Locked decision

**DECISION: (B) ACCEPTED-IRREDUCIBLE. LOCKED.**

Justification, grounded in the census rows above:

1. The locked discriminator requires (A) REDUCIBLE only when EVERY no-fuel path into BOTH drivers has a DATA-DETERMINED budget (common coverage). The censuses show the opposite extreme: 33 of 33 rows (13 Python + 20 JS) are HOST-COUNT-DETERMINED and 0 rows are DATA-DETERMINED. Common coverage for (A) fails not marginally but unanimously.
2. The strongest candidate rows -- `runMetabolizationCycle` (JS-5, surfaced to the API as JS-17) and its Python analog `run_metabolization_cycle` (PY-11) -- are input-structure-INFORMED yet still host-count-REALIZED: in both substrates the budget exists only as a host integer produced by a host counting pass plus host arithmetic (`max(20, 4 * entry_count + 10)` / `Math.max(20, 4 * entryCount + 10)`), and each inner driver call is additionally bounded by a host watchdog constant or default. Converting that integer into Mu fuel would construct fuel from a host count, which established result (3) already rejected as moving host authority rather than removing it.
3. Public no-fuel contracts (`step_mu`, `run_algorithm_meta_circular`, JS `stepKernel` options) expose either no budget parameter at all or an integer `max_steps`/`maxSteps`. There is no existing Mu data structure flowing through any no-fuel caller whose traversal could own loop progress without first computing a host count -- so no honest demotion of the residual watchdog loop is available while any (here: every) path needs the host bound, consistent with established result (4) (both drivers still own transition progress in host control flow for the no-fuel path).
4. This classification fits the L3 Canonical Truth clause verbatim -- "execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics" (`mu/docs/core/L3SubstrateArchitecture.v0.md`, canonical L3 truth statement; same wording in `mu/docs/core/Why_RCX_PI_VM_EXISTS.md`) -- and the existing primitive table already records `max_steps` as "Provides the termination clock -- cannot be structural fuel" (`mu/docs/core/BootstrapPrimitives.v0.md`). The census is uniformly host-count-determined, so the honest-(B) wording exists and stop condition 3 (MIXED census not honestly classifiable) does not fire.
5. Established results (1)-(4) are treated as binding inputs and were not re-derived: no caller migration was proposed (1), the existing Mu-owned KernelDriverContinuationState runtime is unchanged (2), no compatibility fuel from `max_steps` was constructed (3), and the post-continuation NO-GO (4) is preserved by this decision rather than re-attempted.

Consequence: the two residual `@host_iteration` markers -- Python `step_kernel_mu` ("Kernel execution loop - residual watchdog; supplied Mu fuel owns progress") and JS `_stepKernelCore` -- are ACCEPTED host resource-bounding boundaries at the `max_steps`/`maxSteps` watchdog. The tracked-marker floor of 5 (Python 1 host_iteration + 1 host_builtin; JS 1 host_iteration + 2 host_builtin) is accepted at this frontier; reduction below 5 is no longer an open TODO on the kernel-driver path. Any future re-attempt requires a founder-authorized reversal of this locked decision.

### WI-4 -- Smallest next bounded packet (B-branch, specification only; no packet file created by this wave)

Proposed wave id: `n3-kernel-driver-watchdog-accepted-boundary-marker-truth` (date-stamped at creation). Class: L4_ENABLER (non-runtime; docs + gate only). All edits below are OUTSIDE `mu/host/python/rcx_pi/selfhost/` and `mu/host/js/`:

1. `mu/docs/core/L3SubstrateArchitecture.v0.md` -- add an "Accepted kernel-driver watchdog boundary" record adjacent to the canonical L3 truth statement: the two residual `@host_iteration` markers (Python `step_kernel_mu` in `mu/host/python/rcx_pi/selfhost/step_mu.py`; JS `_stepKernelCore` in `mu/host/js/engine/kernel.js`) are ACCEPTED-IRREDUCIBLE at the `max_steps` watchdog per this decision packet (cite this wave id); every no-fuel caller budget is a host numeric bound by design (census in this packet); this frontier is CLOSED as an open reduction absent founder reversal.
2. `mu/docs/core/BootstrapPrimitives.v0.md` -- in the `max_steps` primitive entry and the bootstrap-primitive inventory row for `step_kernel_mu`, replace the open-reduction framing with the locked ACCEPTED-boundary status, citing this packet (wording stays consistent with the existing "cannot be structural fuel" row).
3. NEW text-truth gate `tests/l4_gates/test_kernel_driver_watchdog_accepted_boundary_gate.py` -- read-only file-content assertions (same technique as `mu/tests/docs/test_l4_current_state_truth.py`; core tier, no kernel execution): (a) both docs above contain the ACCEPTED-boundary record with this wave id; (b) the two `@host_iteration` marker strings still exist verbatim in the two runtime files (no silent marker removal/demotion); (c) the host-semantics ratchet baseline still tracks exactly one `host_iteration` marker per substrate, so any future marker movement on this frontier fails the gate unless it cites a founder reversal.

Explicit non-goals for that packet (proof obligations): zero runtime edits (the in-code marker strings and the `kernel.js` comment phrasing "retained until ratchet baseline update" are runtime-file content and are NOT touched; aligning that comment wording would require a separately-authorized runtime-touching wave); zero ratchet-baseline edits; zero marker movement; evidence_command identical to this wave's (both ratchets zero-delta) plus the new gate passing.

### WI-5 -- Zero-delta ratchet evidence

Evidence command (`python3 mu/tools/checks/check_host_semantics_ratchet.py --json && python3 tools/checks/check_host_authority_inventory_ratchet.py`) run twice during this wave -- the host-semantics ratchet before any packet edit and the full command after the censuses and decision were recorded -- with identical results:

- Host-semantics ratchet: `"passed": true` with `"decreases": []` and `"increases": []`; current == baseline on every class: Python `host_iteration: 1`, `host_builtin: 1`, `host_mutation: 0`, `host_recursion: 0`; JavaScript `host_iteration: 1`, `host_builtin: 2`, `host_mutation: 0`, `host_recursion: 0` (tracked-marker total 5, unchanged by this wave).
- Host-authority inventory ratchet: `PASS: No unaccepted new total-inventory or authority-subset sites detected.` Verbatim counts: `Current total inventory: 309 total (181 Python + 128 JS)` vs `Baseline total inventory: 312 total (181 Python + 131 JS)`; `Current authority subset: 212 total (119 Python + 93 JS)` vs `Baseline authority subset: 217 total (120 Python + 97 JS)`; 2 ACCEPTED SPLITS (seed_integrity `load_verified_seed -> load_verified_seed_image`; seed_loader `loadVerifiedSeed -> loadVerifiedSeedImage`); `NOTE: baseline site removals detected -- baseline can be updated after review.`; `NOTE: 18 existing authority site(s) changed signal shape.`

Wave-relative delta is ZERO: the baseline-relative removals/splits in the authority inventory are pre-existing branch state (the ratchet scans 12 Python + 16 JS runtime files; this wave's diff touches no runtime file -- only this packet, the mechanical indicator artifact, and the automation-written TASKS.md note -- so this wave cannot have produced any inventory change). No baseline was amended by this wave. Stop condition 4 (a marker/authority count delta produced during this wave) does not fire.

Indicator artifact: produced mechanically at `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json` by running the `indicator_collection_command` verbatim (exit 0, collector v2.2.0; no hand edit). The collector reads the staged wave files (`git diff --cached`); in round 1 nothing was staged yet, so the invocation correctly fail-closed with "No changed files in staged files" -- in round 2 the wave files were staged and collection succeeded. Deterministic recorded values: `net_host_semantic_delta: 0` (consistent with the zero-delta ratchet evidence above) and `parity_diff_count: 3` (JS debt proxy via `tools/checks/check_js_debt.sh`); timing provenance fields are environment-dependent and intentionally not transcribed here. The Phase B executor's pre-supervisor step re-runs this same collector (byte-identical script at `mu/tools/metrics/collect_l4_wave_indicators.py`) over the staged wave files and stages the artifact, failing closed on any collection error.

### Stop-condition review (none fired)

1. Caller sets exhaustively enumerated by named function (method above) -- no enumeration gap.
2. All classifications were made by reading source in the read-only grounding scope -- no instrumentation or out-of-scope modification was needed.
3. Census is uniformly host-count-determined, not MIXED -- the honest (B) classification fits the L3 Canonical Truth wording verbatim.
4. Evidence command shows zero marker/authority delta.
5. Phase-A-Lock: LOCKED for this packet; TASKS.md tracker note for this wave id verified present at execution time.
6. No grounding beyond the read-only scope list was needed to decide A-vs-B.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11`
- Active packet: `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11`
- Active packet: `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e00f32ba49413828dc60f5a8bf151cdf1b23af62301b413662df753a47a5e9a3`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11 --output reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_2026-06-11.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-max-steps-structural-budget-decision-2026-06-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
