# N3 Stage0 Decorator Metadata Redo 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-decorator-metadata-redo-2026-06-01
Class: L4_STRUCTURAL | target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Re-apply the n3-stage0 decorator-metadata accuracy fix from the closed PR #1036 (branch origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28) onto CURRENT dev. Two changes: (1) in eval_seed.py, update the `_stage0_match` `@host_builtin(...)` metadata string from the stale 'Sole production path (flag removed Wave 4)' claim to reflect the step_kernel_mu VM cutover reality (the engine/bootstrap trusted-helper path remains reachable after the Wave 4 cutover); (2) in test_stage0_vm_cutover.py, add marker-truth assertions in `test_stage0_marker_truth_current_paths` proving the `_stage0_match` `_host_builtin_reason` has no 'Sole production path' and contains the trusted-helper + step_kernel_mu cutover phrasing. This is a PARITY-PRESERVING structural reduction: net_host_semantic_delta=0, no new/removed host authority sites, host semantics ratchet + authority inventory remain at baseline. RE-VALIDATE the 'trusted-helper path remains reachable after the step_kernel_mu VM cutover' claim against CURRENT dev code (the cutover may have evolved since 2026-05-28) before asserting it. The exact prior diff is recoverable via `git show origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28 -- mu/host/python/rcx_pi/selfhost/eval_seed.py mu/tests/l4_gates/test_stage0_vm_cutover.py`.

## Scope

Files / directories in scope for this wave:

- `mu/host/python/rcx_pi/selfhost/eval_seed.py` — the `_stage0_match` `@host_builtin(...)` decorator metadata (`_host_builtin_reason`) string only.
- `mu/tests/l4_gates/test_stage0_vm_cutover.py` — the `test_stage0_marker_truth_current_paths` assertions only.
- `TASKS.md` — the wave tracker note already exists for this wave (no further TASKS.md edit is required by this packet).
- `reports/control_plane/n3_stage0_decorator_metadata_redo_2026-06-01.md` — this governing Phase A packet.
- `reports/l4_wave_indicators/n3-stage0-decorator-metadata-redo-2026-06-01.json` — indicator artifact (mechanical evidence surface).

Character of the change: L4_STRUCTURAL parity-preserving doc-accuracy fix on the host-authority marker. Host semantics ratchet unchanged (net_host_semantic_delta=0); authority inventory stays at baseline. Cite code by function name and file path only; no file:line references / no line numbers in this packet.

## Work Items

Concrete bounded tasks (mirrors the TASKS.md evidence_delta for this wave):

1. **Marker string (eval_seed.py).** Update the `_stage0_match` `@host_builtin(...)` metadata (`_host_builtin_reason`): remove the stale `'Sole production path (flag removed Wave 4)'` claim and replace it with cutover-accurate wording stating that the engine/bootstrap trusted-helper path remains reachable after the `step_kernel_mu` VM cutover. Recover the exact prior wording with `git show origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28 -- mu/host/python/rcx_pi/selfhost/eval_seed.py`.
2. **Marker-truth test (test_stage0_vm_cutover.py).** Add assertions to `test_stage0_marker_truth_current_paths` proving the `_stage0_match` `_host_builtin_reason` (a) does NOT contain `'Sole production path'`, and (b) DOES contain the trusted-helper + `step_kernel_mu` cutover phrasing.
3. **Re-validation precondition (Phase B).** Before asserting the new marker text, re-validate against CURRENT dev code that the trusted-helper path is in fact still reachable after the `step_kernel_mu` VM cutover (the cutover may have evolved since 2026-05-28). The marker wording must match current code truth, not the 2026-05-28 snapshot.
4. **Indicator refresh.** Regenerate the indicator artifact via the indicator_collection_command and confirm `net_host_semantic_delta=0` with authority inventory at baseline.

## Constraints

What is NOT in scope:

- No new or removed host-authority sites. The host semantics ratchet must remain unchanged (`net_host_semantic_delta=0`); the authority inventory stays at baseline.
- No runtime/behavioral change to `_stage0_match` or any execution path. This is a metadata/marker-string + test-only change (parity-preserving structural reduction); the `@host_builtin` decorator's runtime semantics are untouched.
- No L3 parity divergence. Only a Python-side host-authority marker string and its Python test assertion change; no projection/semantic change on either substrate, so Python/JS parity is unaffected and no JS edit is in scope.
- No file:line references and no line numbers in this packet (doc-governance). Code is cited by function name and file path only.
- No edits to files outside the Scope list — no executor/test-infra changes, no unrelated dirty-file edits, no other stale-marker cleanups.

## Stop Conditions

- Phase A ends when this packet contains all required sections and the bridge converges. Do NOT begin Phase B edits in this turn.
- If re-validation against CURRENT dev shows the trusted-helper path is NOT reachable after the `step_kernel_mu` cutover, STOP and route back — do not assert a marker that contradicts current code truth.
- If the change would require touching runtime semantics (not just the marker string), or would move `net_host_semantic_delta` off 0, or would add/remove a host-authority site, STOP — that exceeds the parity-preserving structural-reduction authorization.
- If the prior PR #1036 diff no longer applies cleanly to current dev, STOP at design and re-scope rather than force-applying stale wording.
- Once the evidence gate and post_gate_contract_sweep are green and the indicator confirms baseline, STOP — do not expand scope to adjacent markers or files.

## Acceptance Criteria

- `eval_seed.py` `_stage0_match` `_host_builtin_reason` contains NO `'Sole production path'` substring and DOES contain the trusted-helper + `step_kernel_mu` cutover phrasing, validated against current dev code truth.
- `test_stage0_vm_cutover.py::test_stage0_marker_truth_current_paths` asserts both the absence of the stale claim and the presence of the cutover phrasing, and passes.
- Evidence gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- post_gate_contract_sweep green (no parity/structural regression): `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/structural/ mu/tests/parity/`.
- Indicator confirms `net_host_semantic_delta=0` and authority inventory at baseline: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-decorator-metadata-redo-2026-06-01 --output reports/l4_wave_indicators/n3-stage0-decorator-metadata-redo-2026-06-01.json`.
- No line numbers / file:line references introduced in this packet.

## Grounding / Authorization

- **TASKS.md authorization:** Tracker sync note `(2026-06-01, n3-stage0-decorator-metadata-redo-2026-06-01)` under task `[NEXT-CODEX-POST-REDTEAM]` — Class: L4_STRUCTURAL, target_gate_id: G8, Packet: `reports/control_plane/n3_stage0_decorator_metadata_redo_2026-06-01.md`. This is the same-wave tracker note that authorizes the wave.
- **Authorization:** wave-bound founder override recorded in the TASKS.md tracker note for this wave, so commit automation derives the same-wave override mechanically.
- **FOUNDER_OVERRIDE:n3-stage0-decorator-metadata-redo-2026-06-01**
- **Governing packet:** this file (`reports/control_plane/n3_stage0_decorator_metadata_redo_2026-06-01.md`) is the locked Phase A packet for the wave.
- **Prior implementation reference:** closed PR #1036, branch `origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28`. Exact prior diff: `git show origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28 -- mu/host/python/rcx_pi/selfhost/eval_seed.py mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- **L4 contract fields (from the TASKS.md tracker note):** primary_blocker_class: INTEGRATION; primary_invariant_id: INV_CROSS_SUBSTRATE_PARITY; indicator_artifact_ref: `reports/l4_wave_indicators/n3-stage0-decorator-metadata-redo-2026-06-01.json`; host_semantics_delta: baseline before → unchanged after (net_host_semantic_delta=0, authority inventory at baseline); post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/structural/ mu/tests/parity/`; bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD.

## Request from Post-Merge Supervisor

Re-apply the n3-stage0 decorator-metadata accuracy fix from the closed PR #1036 (branch origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28) onto CURRENT dev. Two changes: (1) in mu/host/python/rcx_pi/selfhost/eval_seed.py, update the `_stage0_match` `@host_builtin(...)` metadata string from the stale 'Sole production path (flag removed Wave 4)' claim to reflect the step_kernel_mu VM cutover reality (the engine/bootstrap trusted-helper path remains reachable after the Wave 4 cutover); (2) in mu/tests/l4_gates/test_stage0_vm_cutover.py, add marker-truth assertions in `test_stage0_marker_truth_current_paths` proving the `_stage0_match` `_host_builtin_reason` has no 'Sole production path' and contains the trusted-helper + step_kernel_mu cutover phrasing. This is a PARITY-PRESERVING structural reduction: net_host_semantic_delta=0, no new/removed host authority sites, host semantics ratchet + authority inventory remain at baseline. RE-VALIDATE the 'trusted-helper path remains reachable after the step_kernel_mu VM cutover' claim against CURRENT dev code (the cutover may have evolved since 2026-05-28) before asserting it. The exact prior diff is recoverable via `git show origin/jabramsja/n3-stage0-decorator-metadata-followup-2026-05-28 -- mu/host/python/rcx_pi/selfhost/eval_seed.py mu/tests/l4_gates/test_stage0_vm_cutover.py`.

Routed next-candidate:
n3-stage0-decorator-metadata-redo-2026-06-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-stage0-decorator-metadata-redo-2026-06-01`
- Active packet: `reports/control_plane/n3_stage0_decorator_metadata_redo_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-decorator-metadata-redo-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/eval_seed.py`
  - `mu/tests/l4_gates/test_stage0_vm_cutover.py`
  - `reports/control_plane/n3_stage0_decorator_metadata_redo_2026-06-01.md`
  - `reports/deferred/non_blocking/n3-stage0-decorator-metadata-redo-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-stage0-decorator-metadata-redo-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
