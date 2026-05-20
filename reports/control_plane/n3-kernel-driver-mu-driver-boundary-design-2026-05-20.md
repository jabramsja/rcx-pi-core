# N3-Kernel-Driver-Mu-Driver-Boundary-Design-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-mu-driver-boundary-design-2026-05-20
Class: L4_STRUCTURAL
Category: /mu structural host-semantics reduction
Target gate: G8
Phase-A-Lock: LOCKED
Source authorization: `TASKS.md` line 607 `[NEXT-CODEX-POST-REDTEAM]`, the residual stop result in `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`, `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`, and same-wave `FOUNDER_OVERRIDE:n3-kernel-driver-mu-driver-boundary-design-2026-05-20`.

## Purpose

The prior residual follow-up correctly stopped with net host-semantics delta `0`.
It restored truthful residual `@host_iteration` markers because the Python and
JavaScript kernel drivers still preserve omitted no-fuel run-until-terminal
compatibility through host loops. This packet exists to lock the next structural
path instead of repeating a marker-only deletion.

## Scope: files/directories in scope

Phase A is limited to designing and locking the next bounded implementation
packet. In-scope evidence surfaces are:

- `reports/control_plane/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.md`
- `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]` tracker grounding
- `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`
- `mu/host/python/rcx_pi/selfhost/step_mu.py::step_kernel_mu`
- `mu/host/js/engine/kernel.js::stepKernel`
- `mu/host/js/engine/kernel.js::_stepKernelCore`
- direct Python and JavaScript call sites that omit `kernel_fuel` / `kernelFuel`
- focused L4/parity/doc tests that currently lock no-fuel compatibility,
  marker truth, and KernelRunResult metadata
- `mu/tools/checks/check_host_semantics_ratchet.py`
- `tools/checks/check_host_authority_inventory_ratchet.py`
- `tools/checks/enforce_l4_execution_contract.py`

## Current Code Truth To Reproduce

- Python `step_kernel_mu` exposes omitted fuel through the default
  `kernel_fuel: object = _KERNEL_FUEL_UNSET`.
- Python computes `caller_supplied_fuel = kernel_fuel is not _KERNEL_FUEL_UNSET`
  and still enters `while (not caller_supplied_fuel) or (fuel_cursor is not None)`.
- JavaScript `stepKernel` computes `hasKernelFuel = Object.hasOwn(options,
  'kernelFuel')` and passes `undefined` into `_stepKernelCore` when the option is
  omitted.
- JavaScript `_stepKernelCore` computes `callerSuppliedFuel = kernelFuel !==
  undefined` and still enters `while (!callerSuppliedFuel || fuelCursor !== null)`.
- The residual follow-up packet records that preserving omitted no-fuel
  compatibility while removing the host loop would require host-counted
  compatibility fuel, recursion, helper/iterator indirection, or a public
  boundary behavior change.

## Work Items

1. Re-open the Python and JavaScript kernel-driver sources and enumerate every
   production and test call site that relies on omitted kernel fuel.
2. Decide whether the direct public kernel boundary can retire omitted-fuel
   run-until-terminal compatibility and require explicit Mu driver/fuel data
   without silently breaking higher-level API contracts.
3. If direct omission cannot be retired in one implementation wave, define the
   smallest Mu-driver seed or continuation-state packet that moves progress
   ownership into Mu data rather than a Python/JavaScript run-until-terminal loop.
4. Reject any plan that simply moves the host loop into a helper, recursion,
   array method, host iterator abstraction, synthetic max-step fuel list, or
   substrate-specific primitive.
5. Lock focused tests that fail if both residual kernel-driver markers are
   removed while either target still contains a host run-until-terminal loop.
6. Lock the evidence plan for host-semantics ratchet, host-authority inventory
   ratchet, L4 execution contract, and Python/JS parity, with no ratchet
   baseline edits unless a real marker reduction is mechanically proven.

## Constraints: not in scope

- No Phase B runtime/test/docs implementation is authorized while
  `Phase-A-Lock` remains `UNLOCKED`.
- Do not preserve omitted no-fuel compatibility by constructing synthetic fuel
  from `max_steps` / `maxSteps`.
- Do not treat generated host-side fuel lists as semantic progress authority.
- Do not move the loop into helpers, recursion, iterator abstractions, array
  methods, or substrate-specific behavior.
- Do not edit ratchet baselines to force a reduction.
- Do not touch seeds, registries, Stage0 VM internals, loader checksum surfaces,
  Claude files, Codex-local binary/config files, or unrelated docs.

## Stop Conditions

Phase A must stop before locking Phase B if any of these conditions hold:

- Omitted-fuel run-until-terminal compatibility cannot be retired at the public
  kernel boundary without an enumerated, bounded caller migration plan.
- The only available compatibility-preserving path constructs host-counted
  synthetic fuel from `max_steps` / `maxSteps`, moves the loop into a helper,
  recursion, iterator/array abstraction, or depends on substrate-specific host
  behavior.
- Python and JavaScript cannot be kept behaviorally equivalent for accepted
  inputs, failure modes, `KernelRunResult` metadata, and explicit empty-fuel
  handling.
- The plan cannot prove that removing the residual `@host_iteration` markers is
  real structural reduction rather than marker movement or baseline-only
  cleanup.
- The required evidence would need out-of-scope edits to seeds, registries,
  Stage0 VM internals, loader checksum surfaces, Claude files, Codex-local
  binary/config files, unrelated docs, or ratchet baselines.
- Runtime implementation is requested before `Phase-A-Lock` is changed to
  `LOCKED` and a detector-visible same-wave `TASKS.md` tracker entry exists.

If any stop condition is met, Phase A must leave this as a smaller explicit
Mu-driver seed/continuation-state design packet with proof limits, not as a
Phase B runtime implementation packet.

## Acceptance Criteria

- Phase A either locks a bounded Phase B packet that can remove both residual
  kernel-driver `@host_iteration` sites as real structural reduction, or stops
  with a smaller explicit Mu-driver design packet and proof limits.
- The locked plan distinguishes direct public-boundary behavior changes from
  runtime semantic changes and names the call sites to migrate.
- The locked plan includes negative controls for marker movement and no-fuel
  synthetic fuel.
- The locked plan preserves Python/JS parity and fail-closed behavior.

## Phase B Design Result

This packet stops as a design implementation, not a runtime kernel change. The
direct public omitted-fuel boundary cannot be retired in this implementation
wave without silently changing production callers and many focused/fuzz/structural
tests that currently depend on omitted `kernel_fuel` / `kernelFuel` preserving
run-until-terminal compatibility.

The next bounded runtime packet must therefore be smaller than direct public
boundary retirement: define a Mu-owned kernel-driver continuation state and a
caller migration path before removing the residual no-fuel host loop. This packet
does not edit seeds, registries, Stage0 VM internals, ratchet baselines, loader
checksum surfaces, Claude files, Codex-local files, or unrelated docs.

### Reproduced Boundary Truth

- Python `step_kernel_mu` is still the residual marked driver at
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1166`; omitted fuel is represented
  by the default sentinel at `step_mu.py:1175`, detected at `step_mu.py:1339`,
  and driven through `while (not caller_supplied_fuel) or (fuel_cursor is not
  None):` at `step_mu.py:1355`.
- JavaScript `_stepKernelCore` is still the residual marked driver at
  `mu/host/js/engine/kernel.js:72-77`; omitted fuel is represented by
  `kernelFuel = undefined`, detected at `kernel.js:89`, and driven through
  `while (!callerSuppliedFuel || fuelCursor !== null)` at `kernel.js:92`.
- Existing focused gates already lock the stop-result truth:
  `mu/tests/l4_gates/test_kernel_run_result_contract.py` covers no-fuel,
  explicit empty-fuel, supplied-fuel, remaining-fuel, and malformed-fuel
  metadata; `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py` and
  `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py` lock marker honesty
  and source-shape negative controls; `mu/tests/docs/test_l4_current_state_truth.py`
  locks doc/current-state truth.

### Omitted-Fuel Call-Site Inventory

Production Python direct callers that currently omit `kernel_fuel`:

- `mu/host/python/rcx_pi/selfhost/step_mu.py:1520`:
  `run_algorithm_meta_circular(execution_mode="structural")` delegates to
  `step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1731`: `step_mu()` delegates to
  `step_kernel_mu(projections, input_value)`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1838`: `run_mu_structural()`
  delegates to `step_kernel_mu(..., return_meta=True)`.

Production JavaScript direct callers that currently omit `kernelFuel`:

- `mu/host/js/engine/routing.js:33` and `routing.js:117`: hemisphere routing
  and metabolization loops call `stepKernel(..., { returnMeta: true, vmConfig })`.
- `mu/host/js/engine/pipeline.js:139`: `runAlgorithmWithBridge()` calls
  `_stepKernelCore(..., 10000, vmConfig || null)` with no fuel argument.
- `mu/host/js/engine/kernel.js:322` and `kernel.js:329`: public `stepKernel()`
  passes `undefined` into `_stepKernelCore` whenever `Object.hasOwn(options,
  "kernelFuel")` is false.
- `mu/host/js/engine/kernel.js:395`: `runStructural()` calls `_stepKernelCore`
  with no fuel argument for each trace step.
- `mu/host/js/api/json_handlers.js:107`, `json_handlers.js:119`, and
  `json_handlers.js:256`: JSON API vector and hemisphere paths call
  `stepKernel()` without `kernelFuel`.
- `mu/host/js/api/json_handlers.js:371`: `step_kernel_meta` preserves omission
  unless the request carries an own `kernelFuel` field.
- `mu/host/js/tests/self_tests.js:174`, `177`, `180`, `205`, `213`, `492`,
  and `520`: JS self-tests exercise public `stepKernel()` without fuel.

Python test direct-call inventory from an AST scan of `mu/tests`:

- `mu/tests/fuzz/test_boundary_validation_fuzzer.py`: omit lines
  329,335,341,347,353,359,365,371.
- `mu/tests/fuzz/test_cross_seed_boundary_fuzzer.py`: omit lines
  208,216,235,245,255,281,296,306,316.
- `mu/tests/fuzz/test_gate4_algorithm_runtime_fuzzer.py`: omit lines
  372,381,392,399,415.
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`: omit lines
  70,80,90,101,121,289,297,303,601; supply fuel lines
  137,161,185,212,235,266,277,516,548.
- `mu/tests/l4_gates/test_meta_circular_evidence_gate.py`: omit lines
  103,129,142,397,430,468,475,492.
- `mu/tests/l4_gates/test_parity_hardening_gate.py`: omit line 100.
- `mu/tests/l4_gates/test_performance_canary_gate.py`: omit lines
  113,121,128,157,172,180,187,194,281,306.
- `mu/tests/l4_gates/test_stage0_vm_cutover.py`: omit lines
  70,76,82,91,97,158,165,179,280,286,292,301,307,313,320,332,338,348,354,401,425,436.
- `mu/tests/l4_gates/test_stage0_vm_performance.py`: omit lines 198,204.
- `mu/tests/l4_gates/test_undefined_motif_runtime_gate.py`: omit lines
  181,201,211.
- `mu/tests/parity/test_exhaustion_parity.py`: omit line 913; supply fuel
  lines 623,660,879.
- `mu/tests/research/test_d010_h5_projection_loader_binary.py`: omit lines
  508,511,544,547.
- `mu/tests/structural/test_cache_alias_containment.py`: omit lines
  98,112,140,159,175,187.
- `mu/tests/structural/test_entropy_budget_enforcement.py`: omit line 225.
- `mu/tests/structural/test_gate4_kernel_modes.py`: omit lines
  42,66,75,80,88,98.
- `mu/tests/structural/test_gate4_runtime_hardening.py`: omit lines
  120,143,173,187.
- `mu/tests/structural/test_gate5_meta_circular_parity.py`: omit line 115.
- `mu/tests/structural/test_kernel_mode_discipline.py`: omit lines
  99,103,107,111,152,158,164.
- `mu/tests/structural/test_projection_order_security.py`: omit lines
  269,283,297,311,327.
- `mu/tests/structural/test_step_mu_kernel_integration.py`: omit lines
  71,92,191,195,203,248,258,270,284,388,395,447,497.
- `mu/tests/structural/test_type_tag_security.py`: omit lines
  470,489,512,536.

JavaScript test direct-call inventory:

- `mu/tests/parity/test_js_vm_bridge_parity.py:445` calls `stepKernel()` from
  an embedded JS proof script without `kernelFuel`.
- `mu/tests/l4_gates/test_kernel_run_result_contract.py:335` calls direct
  `stepKernel()` from an embedded JS proof script with explicit `kernelFuel`
  for watchdog rejection coverage.

### Boundary Decision

Direct public-boundary retirement is not safe in one implementation wave.
Requiring fuel immediately would change `step_mu()`, `run_algorithm_meta_circular()`,
`run_mu_structural()`, JS routing/metabolization, JS algorithm execution, JS
structural trace, JSON API vector/hemisphere paths, JS self-tests, and the listed
test suites. That is a public behavior change and a broad caller migration, not
a local kernel-driver marker reduction.

Compatibility-preserving alternatives remain rejected:

- no synthetic compatibility fuel from `max_steps` / `maxSteps`;
- no helper that hides the same host loop;
- no recursion, generator, iterator, array method, or `Array.from` / `.fill`
  fuel construction as a substrate-specific substitute;
- no ratchet baseline edit without a mechanically proven marker reduction.

### Smallest Next Packet

The next packet should be a Phase A design/implementation split for a
Mu-owned kernel-driver continuation state, tentatively:

`n3-kernel-driver-mu-continuation-state-2026-05-20`.

Minimum scope for that packet:

- Define a Mu data shape for kernel-driver continuation state that carries the
  current kernel state, original domain input, normalized projection cursor,
  remaining explicit fuel, `steps_used`, watchdog cap, and terminal metadata.
- Add a single-step public/internal boundary that returns either terminal
  `KernelRunResult` or a continuation-state Mu value without running a
  Python/JavaScript run-until-terminal loop.
- Migrate production direct callers in the inventory above to pass explicit
  Mu fuel or drive returned continuation data through existing outer boundary
  loops that are already classified as boundary scaffolding.
- Preserve accepted input parity, explicit empty-fuel behavior, malformed-fuel
  fail-closed behavior, `KernelRunResult` fields, and JS/Python metadata parity.
- Remove residual `@host_iteration` markers only after the target functions no
  longer contain omitted-fuel run-until-terminal host loops.

Proof limits for that packet:

- It must not claim marker reduction while `step_kernel_mu` contains
  `while (not caller_supplied_fuel) or (fuel_cursor is not None):` or
  `_stepKernelCore` contains `while (!callerSuppliedFuel || fuelCursor !== null)`.
- It must not construct Mu fuel from host counts or watchdog numbers.
- It must not move the loop into helper functions, recursion, iterators, array
  methods, generator functions, or substrate-specific primitives.

### Focused Test Lock

This packet keeps the current runtime intact and hardens
`mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py` so the marker-truth
gate also rejects hidden `compatibility_fuel` / `compatibilityFuel` helper
paths, Python `range(max_steps)` semantic ownership, and JavaScript host-sized
synthetic fuel arrays (`Array.from` / `.fill`) in `_stepKernelCore`.

The focused tests now fail if both residual markers are removed while either
target still contains the run-until-terminal loop, and they fail if the omitted
fuel path is laundered into synthetic fuel or a helper cursor.

### Phase B-Local Evidence Plan

Evidence command for this design packet:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestPythonOuterLoopBoundary::test_step_kernel_mu_has_fuel_governed_watchdog_loop \
  mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_active_kernel_core_has_fuel_governed_watchdog_loop \
  mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py::TestMarkerTruthAsymmetryGate::test_js_active_kernel_core_loop_is_mu_fuel_governed_with_watchdog \
  mu/tests/l4_gates/test_kernel_run_result_contract.py \
  mu/tests/parity/test_exhaustion_parity.py -k "kernel_fuel or step_kernel_meta or default_no_fuel" \
  --tb=short && \
node mu/host/js/eval_step.js && \
python3 mu/tools/checks/check_host_semantics_ratchet.py --json && \
python3 tools/checks/check_host_authority_inventory_ratchet.py && \
python3 tools/checks/enforce_l4_execution_contract.py --files \
  TASKS.md \
  reports/control_plane/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.md \
  mu/host/python/rcx_pi/selfhost/step_mu.py \
  mu/host/js/engine/kernel.js \
  mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py \
  reports/l4_wave_indicators/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.json \
  --wave-id n3-kernel-driver-mu-driver-boundary-design-2026-05-20 \
  --wave-class L4_STRUCTURAL
```

Expected evidence delta: no runtime behavior change; source comments at the two
target kernel-driver boundaries bind omitted-fuel compatibility to the separate
Mu continuation-state migration; no ratchet baseline edit; host-semantics counts
remain unchanged with Python `host_iteration=1` and JavaScript
`host_iteration=1`; host-authority inventory reports no unaccepted increase; L4
execution contract binds this design/test packet to the same-wave tracker entry
and founder override.

Phase B-local validation note: the focused pytest set, JS self-test,
host-semantics ratchet, and host-authority inventory pass locally. Strict L4
execution-contract closure is blocked inside this implementer because the
enforcer requires creating and including the same-wave indicator artifact under
`reports/l4_wave_indicators/`, which is outside this locked packet's file scope.
That artifact collection remains executor-owned unless a broader scope is
authorized.

## Grounding / Authorization

- `TASKS.md` line 607 authorizes this queued Phase A packet under
  `[NEXT-CODEX-POST-REDTEAM]`, names the wave id
  `n3-kernel-driver-mu-driver-boundary-design-2026-05-20`, and limits the work
  to Phase A until the packet is locked and a same-wave tracker entry exists.
- The governing packet is this file:
  `reports/control_plane/n3-kernel-driver-mu-driver-boundary-design-2026-05-20.md`.
- The governing predecessor evidence is the Phase B stop result in
  `reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`,
  which records that preserving omitted no-fuel compatibility while removing
  the host loop would require host-counted compatibility fuel, recursion,
  helper/iterator indirection, or a public-boundary behavior change.
- Source founder authorization is
  `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- Same-wave founder authorization is
  `FOUNDER_OVERRIDE:n3-kernel-driver-mu-driver-boundary-design-2026-05-20`.

Questions? Concerns? Thoughts? -- Think hard
