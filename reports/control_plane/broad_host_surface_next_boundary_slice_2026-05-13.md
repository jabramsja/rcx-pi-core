# Broad Host-Surface Next Boundary Slice

Status: IMPLEMENTED / LOCAL EVIDENCE

Wave ID: broad-host-surface-next-boundary-slice-2026-05-13
Class: L4_STRUCTURAL
Task: [NEXT-CODEX-POST-REDTEAM]
Phase-A-Lock: LOCKED
Category: /mu structural host-surface reduction
Parent wave: broad-host-surface-reduction-boundary-2026-05-13
FOUNDER_OVERRIDE:broad-host-surface-next-boundary-slice-2026-05-13
Authorization: TASKS.md:320 `[NEXT-CODEX-POST-REDTEAM]` retains active
N3 broad host-surface boundary residue; TASKS.md:328-329 binds the parent
`broad-host-surface-reduction-boundary-2026-05-13` tracker handoff/follow-up.
Bridge Round 1 remediation adds the same-wave TASKS tracker note for
`broad-host-surface-next-boundary-slice-2026-05-13` and stages the same-wave
indicator artifact required by strict L4 validation.
## Scope

This packet routes the remaining N3 broad host-surface deferred non-blocker after
PR #944. The parent wave closed one bounded JS invalid-state acceptance slice,
but it did not close N3. This wave must select another bounded, source-grounded
slice or explicitly leave N3 active with a precise next-wave task.

Active deferred source:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `reports/deferred/non_blocking/README.md`
- `reports/deferred/README.md`

Parent evidence:

- `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`
- PR #944 / merge `15be9e511fbbeaf16870838b9cfe0c60ba33143b`

## Grounding / Authorization

Detector-visible TASKS.md authorization:

- `TASKS.md:320` records `[NEXT-CODEX-POST-REDTEAM]` for the transparent JS
  live container provenance structural implementation and states that the active
  deferred non-blocking residue is now N3 broad host-surface boundary only.
- `TASKS.md:328` records `[NEXT-CODEX-POST-REDTEAM]` for parent wave
  `broad-host-surface-reduction-boundary-2026-05-13`, binding the parent packet,
  indicator artifact, and `FOUNDER_OVERRIDE`.
- `TASKS.md:329` records the same parent wave follow-up without a phase or
  task-state change.
- This packet is the successor governing packet for
  `broad-host-surface-next-boundary-slice-2026-05-13`; the packet-local
  `FOUNDER_OVERRIDE:broad-host-surface-next-boundary-slice-2026-05-13` is the
  wave-bound override for Phase A routing.
- Bridge Round 1 same-wave binding is the `TASKS.md` tracker sync note dated
  2026-05-13 for `broad-host-surface-next-boundary-slice-2026-05-13`, with
  `indicator_artifact_ref:
  reports/l4_wave_indicators/broad-host-surface-next-boundary-slice-2026-05-13.json`.

Direct current truth from the parent packet:

- N3 was not closed by PR #944.
- The parent slice removed no authority-subset site; authority inventory stayed
  flat at 217 authority sites.
- A valid successor must choose a narrow source-grounded host-surface reduction,
  not claim broad host-surface elimination.
- Baseline-only cleanup is not a reduction.

## Work Items

Concrete bounded Phase A tasks from current `[NEXT-CODEX-POST-REDTEAM]`
authorization:

1. Reproduce current deferred N3 status from `reports/deferred/non_blocking/`.
2. Reproduce parent-wave closure state from PR #944 and the parent packet.
3. Re-run current ratchet evidence:
   - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
   - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
   - `python3 tools/checks/check_host_authority_inventory_ratchet.py --json`
   - `./tools/checks/check_docs_consistency.sh`
4. Inspect the candidate source surfaces below and select exactly one bounded
   implementation slice, or leave N3 active with a precise next packet.
5. Lock a Phase B write set, focused tests, parity proof, ratchet expectations,
   and stop conditions before implementation.

Candidate source surfaces:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/engine/pipeline.js`
- `mu/host/js/core/stage0_vm.js`
- `mu/host/js/core/terminal_classification.js`
- `mu/host/js/core/types.js`

## Constraints

- Use dispatcher pipeline: post-merge routing -> Phase A -> Phase B -> commit
  executor.
- Do not hand-implement runtime changes before Phase A locks a bounded route.
- Do not edit Claude-related files.
- Do not add semantic host debt. Work in Mu or narrow host bootstrap
  assumptions.
- Prefer paired Python/JS surfaces when the selected behavior is semantically
  shared. If a single-substrate slice is selected, Phase A must prove the paired
  substrate is already strict or out of scope.
- Do not update ratchet baselines as a substitute for real reduction.
- Do not archive N3 unless code or locked architecture evidence proves the
  retained broader advisory is closed.

## Stop Conditions

- Stop if the dispatcher selects a completed packet or stale wrong-wave packet.
- Stop if current code proves the apparent candidate already landed; remove it
  from pending scope instead of duplicating work.
- Stop if the only available action would add host-only semantics or move
  authority into Python/JavaScript.
- Stop if Phase A cannot bind a focused test or parity proof to the candidate.

## Acceptance Criteria

- Phase A either locks one narrow implementation slice or leaves N3 active with
  a precise next-wave task.
- Phase B, if routed, changes only the locked files and tests.
- Host-semantics ratchet must not increase.
- Host-authority inventory must not add total-inventory or authority-subset
  sites unless the packet explicitly proves a justified reduction/rename.
- Deferred README/source truth must be updated only if the selected work closes
  or narrows active N3 truth.

## Required Validation

Minimum Phase A validation:

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Any Phase B implementation must add focused tests for the locked source surface
and rerun the relevant parity, L4, ratchet, and docs checks.

## Phase A Lock

Current-source reproduction removed the parent wave's
`js-hash-trace-invalid-state-fail-closed-2026-05-13` candidate from pending
scope. The parent-selected behavior already exists in current code:

- `mu/host/js/engine/pipeline.js:198` through `:202` rejects invalid
  `hashTraceForRecurrence` entry state before hashing.
- `mu/tests/l4_gates/test_wave11_hardening_gate.py:78` through `:84` and
  `:143` through `:151` cover Python and JS invalid-state rejection.

Selected bounded route:

- Route ID:
  `js-stage0-mucopy-host-trap-fail-closed-2026-05-13`.
- Boundary:
  exported JS Stage0 `muCopy(..., rejectNonMu=true)` parse-tree/capture copy
  boundary.
- Reproduced pre-implementation gap:
  - Direct `node` probe of exported `muCopy(proxy, true, "probe")` with a
    Proxy `getPrototypeOf` trap printed `Error:host trap`, proving a native
    host exception leaked from the JS copy boundary.
- Direct source evidence and implementation:
  - `mu/host/js/core/stage0_vm.js:81` through `:99` now treats host-trapping
    plain object/array prototype checks as non-Mu plainness failure.
  - `mu/host/js/core/stage0_vm.js:207` through `:277` now converts host
    own-key/descriptor/copy errors inside direct `muCopy` array and record
    copying to Stage0 copy-boundary failure when `rejectNonMu=True`, or `null`
    in lax copy mode.
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py:202` through `:224` is already
    strict for the paired substrate: non-dict/list/primitive values raise
    `Stage0VMError` when `reject_non_mu=True` and return `None` otherwise.
- Why this is an honest N3 slice:
  The change does not add host semantics or a Proxy oracle. It narrows the JS
  Stage0 bootstrap copy boundary so host-trap behavior cannot leak as native JS
  exceptions from the exported copy surface.
- Why this does not create parity debt:
  Python is already strict at the equivalent copy boundary. This is a
  single-substrate JS tightening to match Python's fail-closed behavior class.

Locked Phase B write set:

- `mu/host/js/core/stage0_vm.js`
- `mu/tests/l4_gates/test_stage0_vm.py`
- this control-plane packet

Focused test:

- `mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance::test_node_mu_copy_proxy_traps_fail_closed_without_native_error`

Phase B-local validation commands:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance::test_node_mu_copy_proxy_traps_fail_closed_without_native_error --tb=short -p no:cacheprovider
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance --tb=short -p no:cacheprovider
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Ratchet expectation:

- Host-semantics ratchet remains flat.
- Host-authority inventory adds no total-inventory or authority-subset sites.
- N3 remains active; this slice narrows one Stage0 JS host-trap boundary but
  does not prove broad host-surface closure.

## Bridge Round 1 Remediation

Blocking finding:

- Strict staged L4 validation failed because the runtime/test/control-plane
  package had no detector-visible same-wave tracker note in `TASKS.md`.

Repair:

- Add the same-wave `TASKS.md` L4_STRUCTURAL tracker sync note for
  `broad-host-surface-next-boundary-slice-2026-05-13`.
- Stage the same-wave indicator artifact at
  `reports/l4_wave_indicators/broad-host-surface-next-boundary-slice-2026-05-13.json`.

Bridge validation to rerun:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id broad-host-surface-next-boundary-slice-2026-05-13
```

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `broad-host-surface-next-boundary-slice-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-next-boundary-slice-2026-05-13.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/stage0_vm.js`
  - `mu/tests/l4_gates/test_stage0_vm.py`
  - `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`
  - `reports/deferred/non_blocking/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/broad-host-surface-next-boundary-slice-2026-05-13.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
