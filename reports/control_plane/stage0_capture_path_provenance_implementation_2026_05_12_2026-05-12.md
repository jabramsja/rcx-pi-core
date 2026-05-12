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

This Phase B handoff sync is limited to the successor implementation packet at `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`.

If this packet converges and is routed to Phase B, the locked runtime/test implementation write set is exactly:

- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/core/stage0_vm.js`
- `mu/tests/l4_gates/test_stage0_vm.py`

Same-wave commit-handoff control-surface sync is a separate handoff activity, not Phase B runtime/test implementation. If Phase B reaches commit handoff, the only detector-visible control-surface paths authorized for same-wave handoff sync are exactly:

- `TASKS.md` for the same-wave tracker sync note for `stage0-capture-path-provenance-implementation-2026-05-12`.
- `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md` for successor-packet visibility and same-wave metadata.
- `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json` for L4 indicator/evidence metadata for `stage0-capture-path-provenance-implementation-2026-05-12`.

No other tracker, report, indicator, evidence, docs, or metadata path is authorized by this packet for commit-handoff control-surface sync.

The governing predecessor route is `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`. This successor exists to unlock the exact Python/JS Stage0 write set and focused parity proof that TASKS.md requires before any Stage0 implementation work proceeds.

## Work items

1. Lock the Stage0 capture_path boundary decision for Phase B: validate Mu capture provenance at capture time, and perform the safe copy only after validation succeeds.
2. Update `mu/host/python/rcx_pi/selfhost/stage0_vm.py` so hostile or non-Mu direct-API capture leaves fail closed at `capture_path` instead of being recorded and later materializing as `None`.
3. Update `mu/host/js/core/stage0_vm.js` with the paired JavaScript behavior, preserving Python/JS parity and avoiding JS-only host-object semantics.
4. Update `mu/tests/l4_gates/test_stage0_vm.py` with focused coverage that drives both Python and Node direct cases.
5. Prove that valid Mu captures still match and materialize identically on Python and JS.
6. Prove that hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on both runtimes.
7. If Phase B reaches commit handoff, carry same-wave handoff sync only through `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`; this is separate from the three-file runtime/test implementation write set.

## Constraints

- Do not modify any file in this Phase A rewrite except `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`.
- Do not begin Phase B runtime or test implementation from this packet until Phase A converges and the dispatcher routes the successor wave.
- Do not write outside the locked Phase B runtime/test implementation write set: `mu/host/python/rcx_pi/selfhost/stage0_vm.py`, `mu/host/js/core/stage0_vm.js`, and `mu/tests/l4_gates/test_stage0_vm.py`.
- The Phase B runtime/test write-set lock does not forbid the separate same-wave commit-handoff control-surface sync, but that sync is limited to exactly `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`.
- Any commit-handoff control-surface sync must be same-wave only, detector-visible, and limited to the minimum tracker, packet, and indicator metadata in the three enumerated paths above.
- Do not touch seeds, scheduler, registry, production callers, transparent proxy policy, VM coverage trace, JS pipeline shape, unrelated runtime, or Claude files.
- Do not add Python-only subclass semantics, JS-only host object semantics, host semantic debt, or semantic host bootstrap.
- Program in Mu: host code may service validation and orchestration only as a narrowed bootstrap boundary.
- Treat this as a retained /mu structural non-blocker, not a new production /mu wave.

## Stop conditions

- Stop if Phase B runtime/test implementation requires any runtime or test write outside the locked implementation write set.
- Stop if same-wave commit-handoff control-surface sync would require any file other than `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, or `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`.
- Stop if the proposed Python and JS behavior cannot be kept paired by the same semantic rule.
- Stop if the fix would rely on a host oracle, Python-only type hierarchy, JS-only host object behavior, or any new host semantic debt.
- Stop if valid Mu captures would stop matching or materializing identically across Python and JS.
- Stop if direct non-Mu capture leaves cannot fail closed at `capture_path` on both runtimes.
- Stop if `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`, and the routed wave ID cannot be made detector-visible as the same wave through the separate commit-handoff control-surface sync before commit handoff.
- Stop and reclassify the packet if current code truth proves the scoped behavior has already landed before Phase B starts.

## Acceptance criteria

- Packet-shape proof: targeted heading search finds `## Scope`, `## Work items`, `## Constraints`, `## Stop conditions`, `## Acceptance criteria`, `## Grounding / Authorization`, and same-wave `FOUNDER_OVERRIDE:stage0-capture-path-provenance-implementation-2026-05-12`.
- Phase B runtime/test implementation writes, if routed, are limited to the locked implementation write set and no other runtime/test repo path.
- Valid Mu capture behavior remains unchanged: Python and JS still match and materialize equivalent capture paths.
- Hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on Python.
- Hostile or non-Mu direct-API capture leaves fail closed at `capture_path` on JavaScript.
- The focused Python test file drives both Python and Node direct cases for the failure path.
- Existing Stage0 and lower-stage0 checks still pass after the scoped runtime/test change.
- Commit handoff, if reached, includes separate same-wave sync only in `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`; this handoff sync does not count as Phase B runtime/test implementation.

## Grounding / Authorization

- TASKS.md line 525 authorizes the retained predecessor route `stage0-capture-path-provenance-boundary-2026-05-09` as `Class: L4_ENABLER`, `Category: /mu structural Stage0 boundary`, `target_gate_id: G8`, `workload_target: stage0_boundary`, and `primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY`.
- TASKS.md line 525 keeps Stage0 implementation hard-stopped until a successor packet locks the exact Python/JS Stage0 write set and focused parity proof.
- Governing predecessor packet: `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
- Successor implementation packet: `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`.
- Exact same-wave commit-handoff control-surface paths, if Phase B reaches handoff: `TASKS.md`, `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`, and `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`.
- Same-wave detector authorization: `FOUNDER_OVERRIDE:stage0-capture-path-provenance-implementation-2026-05-12`.
- Routed next-candidate: `stage0-capture-path-provenance-implementation-2026-05-12`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stage0-capture-path-provenance-implementation-2026-05-12`
- Active packet: `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`
- Indicator artifact: `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/stage0_vm.js`
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
  - `mu/tests/l4_gates/test_stage0_vm.py`
  - `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`
  - `reports/deferred/non_blocking/stage0-capture-path-provenance-implementation-2026-05-12_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/stage0-capture-path-provenance-implementation-2026-05-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->