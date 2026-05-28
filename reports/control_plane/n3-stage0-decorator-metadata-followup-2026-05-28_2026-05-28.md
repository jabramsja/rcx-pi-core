# N3-Stage0-Decorator-Metadata-Followup-2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-decorator-metadata-followup-2026-05-28
Wave class: L4_STRUCTURAL
Target gate: G8
Phase-A-Lock: LOCKED
Authorization: same-wave `FOUNDER_OVERRIDE:n3-stage0-decorator-metadata-followup-2026-05-28`; source authorization derives from `TASKS.md:676` and the predecessor same-wave authority `FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28`.

## Purpose

Build the bounded Phase A plan for the Stage0 decorator metadata follow-up that the predecessor `L4_ENABLER` wave intentionally deferred. The predecessor packet corrected current-path comments/source-lock wording while preserving the executable `_stage0_match` `@host_builtin(...)` metadata string because changing that decorator argument was classified as executable runtime diff under the locked enabler packet. This follow-up selects the deferred `L4_STRUCTURAL` marker-metadata cleanup path, not a mechanical contract-path change.

## Scope

- Governing packet for this Phase A wave: `reports/control_plane/n3-stage0-decorator-metadata-followup-2026-05-28_2026-05-28.md`.
- Runtime/source implementation write set if Phase A later receives GO: `mu/host/python/rcx_pi/selfhost/eval_seed.py` only.
- Conditional test write set if needed to keep source-lock wording synchronized: focused Stage0 current-path/source-lock tests only, expected location `mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- Required evidence artifact if implementation later receives GO: `reports/l4_wave_indicators/n3-stage0-decorator-metadata-followup-2026-05-28.json`.
- `TASKS.md` is grounding/authorization input for Phase A; a later implementation may touch `TASKS.md` only if commit automation requires same-wave tracker sync.
- Runtime surface in scope: the executable `@host_builtin(...)` metadata argument for `_stage0_match` only.

## Work Items

1. Confirm the current `_stage0_match` decorator metadata still contains the stale "Sole production path" wording before implementation begins.
2. Rewrite only that executable decorator metadata wording so it no longer claims `_stage0_match` is the sole production Stage0 path.
3. Preserve `_stage0_match` as `@host_builtin` unless a separate current-path proof shows the engine/bootstrap trusted-helper path no longer reaches it.
4. Preserve host-semantics ratchet counts and host-authority inventory; no baseline edit is authorized.
5. Add or adjust focused source-lock test wording only if the metadata rewrite requires synchronized evidence coverage.
6. Collect L4 indicator evidence and run the focused Stage0 current-path tests, host-semantics ratchet, and L4 execution contract for the final write set.

## Constraints

- No Stage0 VM, seed, scheduler, registry, loader, JS parity, binary/checksum, dispatcher, commit executor, Claude surface, or production behavior change is in scope.
- No marker deletion, marker-count reduction, marker-count increase, ratchet-baseline edit, or host-authority inventory increase is authorized.
- Do not relist the predecessor current-path comment/source-lock correction as unresolved; `TASKS.md:676` records that predecessor as local evidence and this packet is limited to the deferred decorator metadata string.
- Do not widen runtime/source edits beyond `eval_seed.py` unless focused source tests demonstrably require synchronized wording.
- Do not implement in Phase A. Implementation starts only after this packet is reviewed, converged, and locked.

## Stop Conditions

- Stop if `_stage0_match` no longer contains the stale "Sole production path" decorator metadata wording; convert the wave to no-op/closeout instead of editing runtime text.
- Stop if the required fix would change callable behavior, Stage0 routing, helper reachability, decorator identity, marker count, or ratchet baselines.
- Stop if evidence shows the engine/bootstrap trusted-helper path no longer reaches `_stage0_match`; that is a marker-removal/reclassification decision and needs a separate locked scope.
- Stop if any required test change is more than synchronized source-lock/current-path wording.
- Stop if L4 contract classification cannot be satisfied as `L4_STRUCTURAL` for the final write set.

## Acceptance Criteria

- The packet locks the exact intended implementation write set, wave class, constraints, stop conditions, ratchet expectations, and validation commands before implementation.
- The final implementation write set is limited to `eval_seed.py`, optional synchronized focused test wording, required L4 indicator evidence, and tracker sync only if commit automation requires it.
- The eventual implementation removes the stale "Sole production path" claim from the executable `_stage0_match` decorator metadata without changing runtime behavior.
- `_stage0_match` remains decorated with `@host_builtin`; host-semantics ratchet counts remain unchanged.
- Focused evidence still proves the current `step_kernel_mu` Stage0 VM cutover does not call `_step_trusted`, `_apply_projection_trusted`, or host `_stage0_match`, while `run_engine_pipeline` still reaches the trusted-helper path covered by the predecessor evidence.
- Required validation for implementation GO:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_cutover.py::TestCutoverIntegration::test_stage0_marker_truth_current_paths mu/tests/l4_gates/test_stage0_vm_cutover.py::TestCutoverIntegration::test_no_monolithic_host_path mu/tests/l4_gates/test_stage0_vm_cutover.py::TestCutoverIntegration::test_no_apply_projection_trusted --tb=short`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-decorator-metadata-followup-2026-05-28 --output reports/l4_wave_indicators/n3-stage0-decorator-metadata-followup-2026-05-28.json`
  - `python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md mu/host/python/rcx_pi/selfhost/eval_seed.py mu/tests/l4_gates/test_stage0_vm_cutover.py reports/control_plane/n3-stage0-decorator-metadata-followup-2026-05-28_2026-05-28.md reports/l4_wave_indicators/n3-stage0-decorator-metadata-followup-2026-05-28.json --wave-id n3-stage0-decorator-metadata-followup-2026-05-28 --wave-class L4_STRUCTURAL`

## Grounding / Authorization

- `TASKS.md:453` records the predecessor `n3-stage0-marker-truth-current-path-sync-2026-05-28` package refresh under `[NEXT-CODEX-POST-REDTEAM]`, class `L4_ENABLER`, and `FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28`.
- `TASKS.md:676` records the predecessor local-evidence scope: current-path wording was corrected while the executable `@host_builtin` marker metadata was preserved, host-semantics counts stayed unchanged, and source authorization came from `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_decorator-metadata-followup.md:21-28` says direct rewrite of the executable decorator metadata string was invalid under the prior locked `L4_ENABLER` packet and must be handled by an `L4_STRUCTURAL` marker-metadata follow-up or a mechanical contract path.
- `reports/deferred/non_blocking/n3-stage0-marker-truth-current-path-sync-2026-05-28_decorator-metadata-followup.md:32-39` bounds the follow-up to `mu/host/python/rcx_pi/selfhost/eval_seed.py` unless source tests need synchronized wording, requires the text to no longer say "Sole production path", and requires preserving the marker and ratchet counts unless current-path proof changes.
- Same-wave override for this packet: `FOUNDER_OVERRIDE:n3-stage0-decorator-metadata-followup-2026-05-28`.
