# N3-Kernel-Driver-Mu-Continuation-State-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-mu-continuation-state-2026-05-20
Wave Class: L4_ENABLER (control-plane plan/recovery; successor implementation remains L4_STRUCTURAL)
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-kernel-driver-mu-continuation-state-2026-05-20

Purpose: define the bounded Phase A plan for the Mu-owned kernel-driver
continuation-state packet named by the predecessor boundary-design wave. This
packet moves kernel progress ownership into explicit Mu data before any residual
kernel-driver host-loop marker reduction is claimed.

## Scope: files/directories in scope

This Phase A rewrite is limited to this governing packet:

- `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md`

The future implementation packet may touch only the bounded kernel-driver
continuation-state surface below after Phase A locks and a detector-visible
same-wave `TASKS.md` tracker entry exists:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/js/engine/kernel.js`
- direct Python/JavaScript production caller sites named by the predecessor
  inventory only where required to pass explicit Mu fuel or drive returned
  continuation data through existing boundary-scaffolding loops
- focused existing proof surfaces:
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/parity/test_exhaustion_parity.py`

Tracker, receipt, indicator, L4 execution-contract, and focused executor
regression updates are in scope only as pipeline-owned governance surfaces for
this control-plane package. Runtime implementation files are not authorized in
this wave; they remain reserved for the successor L4_STRUCTURAL implementation
packet after same-wave tracker authority is present.

## Work items

1. Define a cross-substrate Mu continuation-state data shape for the kernel
   driver. It must carry current kernel state, original domain input, normalized
   projection cursor, remaining explicit fuel, `steps_used`, watchdog cap, and
   terminal metadata.
2. Add a single-step public/internal kernel-driver boundary in both Python and
   JavaScript. The boundary must return either terminal `KernelRunResult` data or
   a continuation-state Mu value without running a Python/JavaScript
   run-until-terminal loop.
3. Migrate only the production direct callers identified by the predecessor
   design inventory: Python `step_mu()`, `run_algorithm_meta_circular()`,
   `run_mu_structural()`, JavaScript routing/metabolization, public
   `stepKernel()` omitted-fuel compatibility, `runAlgorithmWithBridge()`,
   `runStructural()`, JSON API vector/hemisphere paths, JSON API
   `step_kernel_meta`, and JS self-tests. Each migrated caller must either pass
   explicit Mu fuel or drive returned continuation data through an existing outer
   boundary loop already classified as boundary scaffolding.
4. Preserve accepted input parity, explicit empty-fuel behavior, malformed-fuel
   fail-closed behavior, `KernelRunResult` fields, and Python/JavaScript
   metadata parity.
5. Update focused L4/parity tests so they fail on marker-only deletion,
   synthetic max-step fuel, helper-cursor compatibility fuel, JS array-based fuel
   construction, or loop laundering into helpers, recursion, iterators, array
   methods, generator functions, or substrate-specific primitives.
6. Collect implementation evidence through repo pipeline/receipt/builder
   surfaces first, including host-semantics ratchet, host-authority inventory
   ratchet, focused L4/parity tests, and L4 execution-contract proof for the
   same wave.

## Cross-substrate continuation-state contract

The implementation packet must add a single-step kernel-driver return packet
with one discriminator shared by Python and JavaScript:

```text
KernelDriverStepPacket =
  {
    kind: "terminal",
    result: KernelRunResult,
    continuation: null
  }
| {
    kind: "continuation",
    result: null,
    continuation: KernelDriverContinuationState
  }
```

`kind` is the only terminal-vs-continuation discriminator. A `terminal` packet
must carry the existing `KernelRunResult` data without field removal, field
renaming, or substrate-specific metadata drift. A `continuation` packet must not
carry a partial `KernelRunResult`; it carries only the Mu-owned continuation
value below.

`KernelDriverContinuationState` is a Mu data value represented by the existing
cross-substrate map/object value surface, not by a Python-only class, a
JavaScript-only prototype, a generator, an iterator, or a hidden helper cursor.
Python and JavaScript must use the same logical keys and value domains:

```text
KernelDriverContinuationState = {
  tag: "kernel_driver_continuation_state",
  version: 1,
  kernel_state: MuValue,
  domain_input: MuValue,
  projection_cursor: null | KernelProjectionCursor,
  remaining_fuel: null | MuFuelValue,
  fuel_mode: "explicit" | "omitted_compatibility",
  steps_used: NonNegativeInteger,
  watchdog_cap: null | NonNegativeInteger,
  terminal: KernelTerminalMetadata
}

KernelProjectionCursor = {
  tag: "kernel_projection_cursor",
  version: 1,
  position: NonNegativeInteger,
  exhausted: Boolean
}

KernelTerminalMetadata = {
  reached: Boolean,
  reason: null | "accepted" | "fuel_exhausted" | "watchdog_exhausted" |
    "malformed_fuel" | "error",
  error: null | String
}
```

Field semantics:

- `kernel_state` is the current Mu kernel state to resume from on the next
  single-step call.
- `domain_input` is the original accepted domain input value; it must not be
  rebuilt from host-local state while resuming.
- `projection_cursor` is the normalized projection cursor. `null` means no
  projection cursor is active; otherwise the cursor records only normalized
  progress and must not embed a host iterator, range, array cursor, or
  compatibility-fuel helper.
- `remaining_fuel` is the remaining caller-provided Mu fuel value. It may be
  `null` only for omitted-fuel compatibility paths that are still explicitly
  outside marker-reduction authority. It must never be synthesized from
  `max_steps`, `maxSteps`, watchdog caps, host counts, arrays, ranges, or lists.
- `fuel_mode` records whether the state came from explicit Mu fuel or the
  still-supported omitted-fuel compatibility surface. It is metadata for
  preservation and proof, not permission to invent compatibility fuel.
- `steps_used` is the exact number of kernel steps already consumed by this
  driver packet and must increment only when the single-step boundary performs
  one kernel transition.
- `watchdog_cap` records the existing watchdog guard as metadata. It is not
  fuel, must not seed `remaining_fuel`, and must not become a hidden host loop
  bound.
- `terminal` records terminal metadata already known while carrying a
  continuation. For ordinary nonterminal continuation packets it is
  `{reached: false, reason: null, error: null}`.

The single-step boundary contract is structural: each call may perform at most
one kernel-driver transition and must return immediately with either the
terminal `KernelRunResult` or the continuation-state Mu value above. Public
omitted-fuel compatibility may be preserved only by an already-classified outer
boundary-scaffolding loop that repeatedly drives this returned continuation; the
kernel-driver body itself must not retain, hide, or recreate a run-until-terminal
Python/JavaScript loop.

## Locked implementation write set and caller inventory

After the same-wave `TASKS.md` tracker entry exists, the implementation packet
may touch only the files and direct caller surfaces below:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`: `step_kernel_mu()` single-step
  boundary/continuation state plus production callers `step_mu()`,
  `run_algorithm_meta_circular()`, and `run_mu_structural()`.
- `mu/host/js/engine/kernel.js`: `_stepKernelCore()` single-step
  boundary/continuation state plus public `stepKernel()` omitted-fuel
  compatibility and `runStructural()`.
- `mu/host/js/engine/routing.js`: hemisphere routing and metabolization
  `stepKernel(..., { returnMeta: true, vmConfig })` callers.
- `mu/host/js/engine/pipeline.js`: `runAlgorithmWithBridge()` direct
  `_stepKernelCore()` caller.
- `mu/host/js/api/json_handlers.js`: `run_vector`, `run_all_vectors`,
  `run_hemisphere`, and `step_kernel_meta` request paths.
- `mu/host/js/tests/self_tests.js`: public `stepKernel()` no-fuel self-test
  callers that must keep compatibility coverage honest.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
- `mu/tests/parity/test_exhaustion_parity.py`

## Constraints: not in scope

- Do not solve the implementation in this Phase A packet-rewrite turn.
- Do not inspect or edit unrelated dirty files, unrelated executor/test changes,
  Claude files, Codex-local files, seed/registry/Stage0/scheduler/loader/binary/
  checksum/integrity surfaces, ratchet baselines, or broad documentation.
- Do not retire public omitted-fuel compatibility in one jump. The predecessor
  evidence says omitted-fuel compatibility is still used by multiple production
  and test callers.
- Do not claim host-iteration marker reduction while `step_kernel_mu` still
  contains `while (not caller_supplied_fuel) or (fuel_cursor is not None):` or
  `_stepKernelCore` still contains
  `while (!callerSuppliedFuel || fuelCursor !== null)`.
- Do not construct Mu fuel from host counts, `max_steps`, `maxSteps`, watchdog
  caps, `Array.from`, `.fill`, ranges, lists, or equivalent synthetic host data.
- Do not move the loop into helpers, recursion, iterators, array methods,
  generator functions, compatibility cursors, or substrate-specific primitives.
- Do not edit ratchet baselines or accept host-authority inventory increases.

## Stop conditions

Stop before Phase B implementation if any of the following is true:

- `TASKS.md` still lacks a detector-visible same-wave tracker entry for
  `n3-kernel-driver-mu-continuation-state-2026-05-20`.
- `Phase-A-Lock` is not `LOCKED` after bridge convergence.
- The design cannot name the exact Python/JavaScript write set and focused proof
  set without widening into unrelated runtime, substrate, Stage0, seed, registry,
  loader, binary, checksum, integrity, Claude, or Codex-local surfaces.
- A caller migration would require changing public API behavior instead of
  passing explicit Mu fuel or using an already-classified boundary loop.
- The implementation path would synthesize fuel from watchdog counts or hide the
  residual loop in a helper, recursion, iterator, array method, generator, or
  substrate primitive.
- The proof plan cannot preserve accepted input parity, empty-fuel behavior,
  malformed-fuel fail-closed behavior, `KernelRunResult` fields, and metadata
  parity across Python and JavaScript.

## Acceptance criteria

- This packet carries the required Phase A sections and same-wave authorization
  for `n3-kernel-driver-mu-continuation-state-2026-05-20`.
- Phase B is not authorized until this packet is locked and `TASKS.md` contains
  the exact current wave id plus governing packet path.
- The locked implementation plan names the exact files, direct callers, and
  focused tests that will change; no broad repo investigation or unrelated dirty
  file inspection is required to start from this plan.
- The Mu continuation-state shape is explicit and cross-substrate, and the
  single-step boundary can return either terminal `KernelRunResult` data or a
  continuation-state Mu value.
- Production callers that rely on omitted fuel are migrated only through
  explicit Mu fuel or existing boundary-scaffolding loops; public compatibility
  is not silently broken.
- Marker reduction is claimed only if the target Python and JavaScript kernel
  driver bodies no longer contain omitted-fuel run-until-terminal host loops and
  focused gates reject marker-only deletion and loop laundering.
- Host-semantics ratchet counts, host-authority inventory, accepted inputs,
  empty-fuel behavior, malformed-fuel failures, `KernelRunResult` fields, and
  Python/JavaScript metadata parity remain preserved unless a later locked
  packet explicitly proves a real structural reduction.

## Grounding / Authorization

- `TASKS.md:401` documents the predecessor
  `n3-kernel-driver-mu-driver-boundary-design-2026-05-20` Phase B handoff and
  its L4 structural evidence surface.
- `TASKS.md:612` documents the same predecessor as implemented/local evidence,
  rejects direct omitted-fuel retirement for that wave, and defines the next
  smaller packet as a Mu-owned kernel-driver continuation-state migration before
  runtime marker removal.
- `reports/control_plane/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.md:255-286`
  is the governing predecessor packet section. It names
  `n3-kernel-driver-mu-continuation-state-2026-05-20`, defines the minimum scope,
  and records the proof limits used here.
- Current exact-wave tracker status: targeted search for
  `n3-kernel-driver-mu-continuation-state-2026-05-20` in `TASKS.md` returned no
  match before Phase B recovery. The final package now stages the same-wave
  tracker note and indicator so commit validation can bind this control-plane
  package without claiming runtime marker reduction.
- Same-wave authorization for this control-plane Phase A packet:
  `FOUNDER_OVERRIDE:n3-kernel-driver-mu-continuation-state-2026-05-20`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-mu-continuation-state-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-mu-continuation-state-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-mu-continuation-state-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-mu-continuation-state-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `81df6c71f31a4c12129aa209805145cbb5bc92450e23e68ca07794876f175c19`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-mu-continuation-state-2026-05-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-mu-continuation-state-2026-05-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-mu-continuation-state-2026-05-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
