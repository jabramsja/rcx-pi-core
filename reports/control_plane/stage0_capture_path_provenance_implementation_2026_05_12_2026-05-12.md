# Stage0 Capture Path Provenance Implementation 2026 05 12

Date: 2026-05-12
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage0-capture-path-provenance-implementation-2026-05-12
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Category: /mu structural Stage0 boundary
target_gate_id: G8
workload_target: host_debt_reduction
primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY
FOUNDER_OVERRIDE:stage0-capture-path-provenance-implementation-2026-05-12

## Scope

This is a completed historical implementation packet for the Stage0
`capture_path` provenance fix. It records the landed runtime/test write set and
same-wave control-surface handoff; it does not authorize new Phase A or Phase B
implementation work.

The completed runtime/test implementation write set was exactly:

- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/core/stage0_vm.js`
- `mu/tests/l4_gates/test_stage0_vm.py`

The completed same-wave commit-handoff control-surface sync was limited to:

- `TASKS.md` for the same-wave tracker sync note for `stage0-capture-path-provenance-implementation-2026-05-12`.
- `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md` for successor-packet visibility and same-wave metadata.
- `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json` for L4 indicator/evidence metadata for `stage0-capture-path-provenance-implementation-2026-05-12`.

The generated Phase B deferred bridge artifact is closed by
`stage0-capture-provenance-deferred-cleanup-2026-05-12` and archived at
`reports/archive/deferred/stage0-capture-path-provenance-implementation-2026-05-12_bridge_nonblockers_closed-by-stage0-capture-provenance-deferred-cleanup-2026-05-12.md`.

The governing predecessor route is `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`. This successor exists to unlock the exact Python/JS Stage0 write set and focused parity proof that TASKS.md requires before any Stage0 implementation work proceeds.

## Work items

1. Locked the Stage0 `capture_path` boundary decision for Phase B: validate Mu capture provenance at capture time, and perform the safe copy only after validation succeeds.
2. Updated `mu/host/python/rcx_pi/selfhost/stage0_vm.py` so hostile or non-Mu direct-API capture leaves fail closed at `capture_path` instead of being recorded and later materializing as `None`.
3. Updated `mu/host/js/core/stage0_vm.js` with the paired JavaScript behavior, preserving Python/JS parity and avoiding JS-only host-object semantics.
4. Updated `mu/tests/l4_gates/test_stage0_vm.py` with focused coverage that drives both Python and Node direct cases.
5. Proved that valid Mu captures still match and materialize identically on Python and JS.
6. Proved that hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on both runtimes.
7. Carried same-wave handoff sync only through `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`; this was separate from the three-file runtime/test implementation write set.

## Constraints

- This completed packet is historical; it does not authorize additional
  runtime/test/control-plane edits.
- Any future Stage0, runtime, test, or deferred cleanup work must use a
  separate packet with its own scoped write set and validation.
- The completed Phase B runtime/test write set was limited to
  `mu/host/python/rcx_pi/selfhost/stage0_vm.py`,
  `mu/host/js/core/stage0_vm.js`, and
  `mu/tests/l4_gates/test_stage0_vm.py`.
- The completed same-wave control-surface sync was limited to `TASKS.md`,
  this packet, and
  `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`.
- The implementation did not touch seeds, scheduler, registry, production
  callers, transparent proxy policy, VM coverage trace, JS pipeline shape,
  unrelated runtime, or Claude files.
- The implementation did not add Python-only subclass semantics, JS-only host
  object semantics, host semantic debt, or semantic host bootstrap.
- Program in Mu: host code serviced validation and orchestration only as a
  narrowed bootstrap boundary.

## Stop conditions

The following stop conditions governed the completed implementation and remain
closure boundaries for this historical record:

- No additional runtime/test implementation may be derived from this packet.
- Stop and route a separate packet if any future cleanup requires runtime,
  Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, or
  Claude-related edits.
- Stop and route a separate packet if future evidence shows Python and JS
  `capture_path` behavior cannot be kept paired by the same semantic rule.
- Stop and route a separate packet if a future fix would rely on a host oracle,
  Python-only type hierarchy, JS-only host object behavior, or any new host
  semantic debt.

## Acceptance criteria

- Packet-shape proof: targeted heading search finds `## Scope`, `## Work items`, `## Constraints`, `## Stop conditions`, `## Acceptance criteria`, `## Grounding / Authorization`, and same-wave `FOUNDER_OVERRIDE:stage0-capture-path-provenance-implementation-2026-05-12`.
- Phase B runtime/test implementation writes, if routed, are limited to the locked implementation write set and no other runtime/test repo path.
- Valid Mu capture behavior remains unchanged: Python and JS still match and materialize equivalent capture paths.
- Hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on Python.
- Hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on JavaScript.
- The focused Python test file drives both Python and Node direct cases for the failure path.
- Existing Stage0 and lower-stage0 checks still pass after the scoped runtime/test change.
- Commit handoff included separate same-wave sync only in `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`; this handoff sync did not count as Phase B runtime/test implementation.
- The generated Phase B deferred bridge artifact is no longer active pending
  work; it is archived by
  `stage0-capture-provenance-deferred-cleanup-2026-05-12`.

## Grounding / Authorization

- TASKS.md line 525 authorized the retained predecessor route `stage0-capture-path-provenance-boundary-2026-05-09` as `Class: L4_ENABLER`, `Category: /mu structural Stage0 boundary`, `target_gate_id: G8`, `workload_target: stage0_boundary`, and `primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY`.
- TASKS.md line 525 kept Stage0 implementation hard-stopped until this successor packet locked the exact Python/JS Stage0 write set and focused parity proof.
- Governing predecessor packet: `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
- Successor implementation packet: `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`.
- Completed same-wave commit-handoff control-surface paths: `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`.
- Same-wave detector authorization: `FOUNDER_OVERRIDE:stage0-capture-path-provenance-implementation-2026-05-12`.
- Routed next-candidate: `stage0-capture-path-provenance-implementation-2026-05-12`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stage0-capture-path-provenance-implementation-2026-05-12`
- Active packet: `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`
- Indicator artifact: `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged implementation scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Completed predecessor staged files:
  - `TASKS.md`
  - `mu/host/js/core/stage0_vm.js`
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
  - `mu/tests/l4_gates/test_stage0_vm.py`
  - `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`
  - `reports/deferred/non_blocking/stage0-capture-path-provenance-implementation-2026-05-12_bridge_nonblockers.md`
    (generated bridge artifact; archived by
    `stage0-capture-provenance-deferred-cleanup-2026-05-12` at
    `reports/archive/deferred/stage0-capture-path-provenance-implementation-2026-05-12_bridge_nonblockers_closed-by-stage0-capture-provenance-deferred-cleanup-2026-05-12.md`)
  - `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
