# N3-Kernel-Driver-Mu-Continuation-State-Runtime-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-mu-continuation-state-runtime-2026-05-20
Phase-A-Lock: LOCKED
Purpose: Continue from the merged control-plane packet reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md and implement the successor runtime wave n3-kernel-driver-mu-continuation-state-runtime-2026-05-20. This is an L4_STRUCTURAL implementation wave, not another plan-only/control-plane package. Required semantics: add the cross-substrate KernelDriverStepPacket and KernelDriverContinuationState contract from lines 73-165; make the kernel-driver boundary single-step so each call returns either terminal KernelRunResult data or a Mu continuation-state value; keep Python and JavaScript logical keys/value domains identical. Required write set: stay inside the bounded files from lines 167-189 unless bridge review proves a smaller exact subset is sufficient. Required migrations: Python step_kernel_mu(), step_mu(), run_algorithm_meta_circular(), run_mu_structural(); JavaScript _stepKernelCore(), stepKernel() omitted-fuel compatibility, runStructural(), routing/metabolization, runAlgorithmWithBridge(), JSON API vector/hemisphere/step_kernel_meta paths, and JS public no-fuel self-tests as needed. Required proof: focused L4/parity gates named in the packet, host-semantics ratchet, host-authority inventory ratchet, and L4 execution contract. Hard stops: do not synthesize Mu fuel from max_steps/maxSteps/watchdog/host counts/arrays/ranges/lists; do not hide the residual loop in helpers, recursion, iterators, array methods, generators, compatibility cursors, or substrate primitives; do not claim marker reduction while the Python/JS omitted-fuel run-until-terminal loops remain; do not change public accepted input behavior, empty-fuel behavior, malformed-fuel fail-closed behavior, KernelRunResult fields, or JS/Python metadata parity. Program in Mu: move progress ownership into Mu data and make host code drive explicit Mu continuation values rather than taking Python/JS shortcuts. Use pipeline, receipts, and builders first.

## Scope

Current Phase A rewrite scope: this packet only,
`reports/control_plane/n3-kernel-driver-mu-continuation-state-runtime-2026-05-20_2026-05-20.md`.
No implementation files are to be edited during this rewrite.

Successor Phase B implementation scope, after agent review and bridge
convergence, is limited to the predecessor packet's locked write set:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/js/engine/kernel.js`
- `mu/host/js/engine/routing.js`
- `mu/host/js/engine/pipeline.js`
- `mu/host/js/api/json_handlers.js`
- `mu/host/js/tests/self_tests.js`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py`
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
- `mu/tests/parity/test_exhaustion_parity.py`

The runtime goal is to implement the Mu-owned kernel-driver continuation-state
boundary in Python and JavaScript while preserving public behavior and parity.

## Work items

1. Implement the cross-substrate `KernelDriverStepPacket` contract with one
   shared discriminator, `kind`, where `terminal` carries the existing
   `KernelRunResult` unchanged and `continuation` carries no partial
   `KernelRunResult`.
2. Represent `KernelDriverContinuationState` as existing cross-substrate Mu
   map/object data with identical Python and JavaScript logical keys and value
   domains: `tag`, `version`, `kernel_state`, `domain_input`,
   `projection_cursor`, `remaining_fuel`, `fuel_mode`, `steps_used`,
   `watchdog_cap`, and `terminal`.
3. In Python, migrate `step_kernel_mu()` to a single-step driver boundary and
   update direct production callers `step_mu()`,
   `run_algorithm_meta_circular()`, and `run_mu_structural()` to drive explicit
   returned continuation values without changing accepted public inputs.
4. In JavaScript, migrate `_stepKernelCore()` to the same single-step driver
   boundary and update `stepKernel()` omitted-fuel compatibility plus
   `runStructural()` to preserve compatibility at an explicitly classified
   outer boundary only.
5. Update direct JavaScript caller surfaces in `routing.js`, `pipeline.js`,
   `json_handlers.js`, and `self_tests.js` so hemisphere routing,
   metabolization, `runAlgorithmWithBridge()`, JSON API vector/hemisphere and
   `step_kernel_meta` paths, and public no-fuel self-tests consume the new
   packet shape honestly.
6. Extend or adjust only the listed L4/parity tests so they prove the
   single-step boundary, no synthetic Mu fuel, no hidden run-until-terminal
   loop, `KernelRunResult` field stability, malformed/empty fuel behavior, and
   Python/JavaScript metadata parity.

## Constraints

- This turn is a packet rewrite only; do not implement runtime changes in this
  turn.
- Do not use the predecessor TASKS note as proof that every work item remains
  unlanded. If bridge evidence or current code truth later proves an item is
  already implemented, remove that item from pending work and acceptance before
  Phase B implementation.
- Do not inspect downstream implementation files solely to decide landed state
  while repairing this stub packet.
- Do not edit files outside this packet during Phase A rewrite, and do not edit
  files outside the locked implementation write set during successor Phase B
  unless bridge review narrows the exact subset further.
- Do not synthesize Mu fuel from `max_steps`, `maxSteps`, watchdog caps, host
  counts, arrays, ranges, or lists.
- Do not hide residual run-until-terminal behavior in helpers, recursion,
  iterators, array methods, generators, compatibility cursors, or substrate
  primitives.
- Do not claim marker reduction while Python or JavaScript omitted-fuel
  run-until-terminal compatibility loops remain.
- Do not change public accepted input behavior, empty-fuel behavior,
  malformed-fuel fail-closed behavior, `KernelRunResult` fields, or
  JavaScript/Python metadata parity.
- Do not represent continuation state with a Python-only class,
  JavaScript-only prototype, generator, iterator, hidden helper cursor, or
  host-local state that cannot cross substrates as Mu data.

## Stop conditions

- Stop if same-wave runtime authorization cannot be derived mechanically from
  this packet's `FOUNDER_OVERRIDE` line and the predecessor TASKS grounding.
- Stop if the implementation requires a file outside the locked write set or a
  broader runtime/substrate migration than this packet authorizes.
- Stop if preserving public omitted-fuel compatibility requires synthesizing
  Mu fuel or recreating a hidden host loop inside the kernel-driver body.
- Stop if Python and JavaScript cannot preserve identical continuation keys,
  value domains, terminal metadata, and `KernelRunResult` shape.
- Stop if host-semantics ratchet, host-authority inventory ratchet, L4
  execution-contract enforcement, or focused L4/parity gates fail because the
  implementation adds new host authority.
- Stop if bridge review proves a listed work item is already implemented; the
  plan must be revised to remove stale pending work before implementation
  continues.

## Acceptance criteria

- This Phase A packet contains concrete `Scope`, `Work items`, `Constraints`,
  `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization`
  sections discoverable by:
  `rg -n "^## (Scope|Work items|Constraints|Stop conditions|Acceptance criteria|Grounding|Authorization)" reports/control_plane/n3-kernel-driver-mu-continuation-state-runtime-2026-05-20_2026-05-20.md`
- The packet carries a same-wave authorization line:
  `FOUNDER_OVERRIDE:n3-kernel-driver-mu-continuation-state-runtime-2026-05-20`.
- The successor implementation returns exactly one of two packet shapes per
  kernel-driver call: terminal `KernelRunResult` data or a Mu continuation-state
  value, with `kind` as the only discriminator.
- `KernelDriverContinuationState` preserves the predecessor contract's exact
  logical keys and value domains across Python and JavaScript.
- Each kernel-driver call performs at most one kernel-driver transition before
  returning terminal data or continuation state.
- Public omitted-fuel compatibility is preserved only in a classified outer
  compatibility boundary and does not seed or disguise Mu fuel.
- Focused proof passes before commit handoff:
  `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py mu/tests/l4_gates/test_marker_truth_asymmetry_gate.py mu/tests/l4_gates/test_kernel_run_result_contract.py mu/tests/parity/test_exhaustion_parity.py`
- Ratchet and contract proof passes before commit handoff:
  `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`,
  `python3 tools/checks/check_host_authority_inventory_ratchet.py`, and
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-kernel-driver-mu-continuation-state-runtime-2026-05-20 --wave-class L4_STRUCTURAL`.

## Grounding / Authorization

- TASKS grounding: `TASKS.md:405` carries the current
  `[NEXT-CODEX-POST-REDTEAM]` tracker note for predecessor wave
  `n3-kernel-driver-mu-continuation-state-2026-05-20`. It authorizes the
  merged control-plane predecessor packet and records package-bound L4
  authority, but it does not contain the successor runtime wave id.
- Runtime same-wave authorization:
  `FOUNDER_OVERRIDE:n3-kernel-driver-mu-continuation-state-runtime-2026-05-20`.
  This override is limited to this successor runtime packet and the locked
  implementation surface above.
- Governing predecessor contract:
  `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md:73`
  through `:165` define the cross-substrate `KernelDriverStepPacket` and
  `KernelDriverContinuationState` semantics.
- Governing predecessor write set:
  `reports/control_plane/n3-kernel-driver-mu-continuation-state-2026-05-20_2026-05-20.md:167`
  through `:189` define the locked implementation files and direct caller
  inventory.
- Reviewer evidence for the blocking authorization gap is preserved as current
  packet rationale: `rg -n "n3-kernel-driver-mu-continuation-state-runtime-2026-05-20" TASKS.md`
  exits 1 before this rewrite, so this packet must carry the same-wave runtime
  authorization explicitly.
