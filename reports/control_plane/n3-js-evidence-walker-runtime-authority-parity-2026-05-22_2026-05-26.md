# N3 JS Evidence Walker Runtime Authority Parity

Date: 2026-05-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-js-evidence-walker-runtime-authority-parity-2026-05-22
Class: L4_STRUCTURAL successor plan
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Create the bounded Phase A packet for the successor locked by `reports/control_plane/n3-terminal-hemisphere-ontology-authority-lock-2026-05-14_2026-05-22.md` lines 138-185. The successor must close the scoped JavaScript ontology evidence-walker runtime authority gap by moving JS primary evidence walking from host trace traversal to verified `evidence_walker.v1.json` projection execution, without adding host authority or broadening the predecessor write set. This reviewed dated packet path is the control-packet path for same-wave validation; the predecessor's undated packet path is historical lock text only and must not be used as the active validation target for this rewrite.

## Scope

Phase A packet rewrite scope for this turn:

- `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md` only.

Successor implementation scope locked by the predecessor packet, with the control-packet path normalized to this reviewed dated packet:

- `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`
- `TASKS.md`
- `mu/seed_registry_manifest.v1.json`
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/engine/pipeline.js`
- `mu/tests/l4_gates/test_evidence_walker_gate.py`
- `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `reports/l4_wave_indicators/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.json`

The successor purpose is limited to JavaScript runtime authority parity for ontology evidence walking. Python's existing structural evidence-walker runtime remains the parity reference unless current implementation evidence in the successor proves a narrower adjustment is needed.

The predecessor packet names `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.md` at `reports/control_plane/n3-terminal-hemisphere-ontology-authority-lock-2026-05-14_2026-05-22.md:149` and `:155`. Bridge review for this packet is against `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`; therefore the dated packet is the only control-packet path this plan may bind into same-wave L4 validation.

## Work items

1. Promote `evidence_walker.v1.json` into the JS core-locked verified seed view only if `mu/seed_registry_manifest.v1.json`, `mu/host/python/rcx_pi/selfhost/seed_integrity.py`, and `mu/host/js/core/seed_loader.js` are updated together so the manifest checksum and both substrate registry guards agree in the same successor.
2. Replace the JS primary `collectOntologyEvidence()` trace walking path in `mu/host/js/engine/pipeline.js` with execution of verified `evidence_walker.v1.json` projections. Host cycle/cap traversal may remain only as boundary validation or a typed fail-closed fallback if the successor proves why it is not primary authority.
3. Update `mu/tests/l4_gates/test_evidence_walker_gate.py` so the gate fails if the JS runtime path continues to exclude `evidence_walker.v1.json`.
4. Update `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py` and `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` so JS evidence collection proves structural walker use while retaining no-overwrite, one-shot, cycle/cap, and typed-error behavior.
5. Update `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py` with Python/JS parity cases so Python `_collect_ontology_evidence()` and JS `collectOntologyEvidence()` agree on null trace, one-entry trace, multi-entry trace, duplicate projection ids, non-string projection ids, malformed trace, and deterministic `control_hash` / `collected_at` fields.
6. Keep `TASKS.md` synchronized in the successor with same-wave L4_STRUCTURAL evidence, indicator metadata, and detector-visible authorization. Do not treat this Phase A packet rewrite as implementation evidence.

## Constraints

- Do not edit files outside the predecessor exact successor write set plus the same-wave L4 indicator artifact after replacing the predecessor's undated control-packet path with this reviewed dated packet path, unless a later bridge-reviewed plan proves the narrower lock is insufficient.
- Do not edit `terminal_classify.v1.json`, `hemispheres.v1.json`, `metabolization.v1.json`, `metabolize_cycle.v1.json`, kernel-driver continuation code, ratchet baselines, unrelated indicator artifacts, Claude-related files, dispatcher files, commit/push machinery, or unrelated deferred cleanup.
- Do not launder evidence-walker semantics into smarter JS host traversal. JS host logic may validate boundaries, enforce caps, and fail closed, but primary trace traversal authority must come from verified seed/projection execution.
- Do not increase host semantics ratchet counts, host authority inventory counts, or accepted authority sites. Baseline edits are out of scope.
- Do not start Phase B implementation from this packet until bridge review accepts the Phase A bounds and same-wave authorization.
- Do not validate same-wave authorization against `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.md`; the active control packet is `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`.
- If current code evidence found during the successor proves any listed item is already landed, prune that item from pending implementation and acceptance criteria instead of relisting it as unresolved.
- If handoff or receipt recovery is required, use the builder/API-backed dispatcher recovery path, not a hand-authored handoff.

## Stop conditions

- Stop if `evidence_walker.v1.json` cannot be added to the JS core-locked verified seed view in the same successor as the manifest checksum and both substrate registry guard updates.
- Stop if the JS runtime still uses host trace traversal as the primary evidence-walking authority after the proposed change.
- Stop if the change requires new host semantics, new host authority, ratchet baseline edits, or accepted authority-site increases.
- Stop if required parity or L4 gates cannot distinguish verified projection execution from source-lock-only or host-traversal behavior.
- Stop if implementation needs files outside the normalized successor write set plus the same-wave L4 indicator artifact before a revised Phase A packet and bridge review justify the broader scope.
- Stop if `TASKS.md` and the dated control packet cannot expose same-wave authorization mechanically.

## Acceptance criteria

- This Phase A packet contains bounded Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The packet contains detector-visible same-wave authorization: `FOUNDER_OVERRIDE:n3-js-evidence-walker-runtime-authority-parity-2026-05-22`.
- The required L4 execution-contract validation includes `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`, the packet that carries the same-wave override; it must not validate the absent or untracked undated predecessor path.
- The successor implementation touches only the normalized locked write set plus the same-wave L4 indicator artifact required for tracker/contract binding unless a revised packet is approved.
- JS runtime evidence collection executes verified `evidence_walker.v1.json` projections as primary authority; host cycle/cap traversal is boundary-only or typed fail-closed fallback with explicit tests.
- `evidence_walker.v1.json` is present in the JS core-locked verified seed view with manifest checksum and Python/JS registry guard parity updated together.
- Focused gates prove JS runtime inclusion of the evidence walker, ontology runtime behavior, boundary authority behavior, and Python/JS parity for the trace cases listed in Work Item 5.
- Host semantics and host authority ratchets report no increases, with no baseline edits.
- Required successor local validation is the predecessor command set or a stricter equivalent:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_evidence_walker_gate.py mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py --tb=short
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md mu/seed_registry_manifest.v1.json mu/host/python/rcx_pi/selfhost/seed_integrity.py mu/host/js/core/seed_loader.js mu/host/js/engine/pipeline.js mu/tests/l4_gates/test_evidence_walker_gate.py mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py reports/l4_wave_indicators/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.json --wave-id n3-js-evidence-walker-runtime-authority-parity-2026-05-22 --wave-class L4_STRUCTURAL
```

Execution note: this command is the successor implementation validation, not evidence that this Phase A rewrite implemented the successor. It must run after Work Item 6 adds the wave-bound tracker sync note to `TASKS.md` and after the dated control packet is in tracked scope; otherwise the L4 checker strips untracked files before binding `--wave-id`.

## Grounding / Authorization

- `TASKS.md:429` records the predecessor `[NEXT-CODEX-POST-REDTEAM]` tracker sync for `n3-terminal-hemisphere-ontology-authority-lock-2026-05-14` and its converged packet at `reports/control_plane/n3-terminal-hemisphere-ontology-authority-lock-2026-05-14_2026-05-22.md`.
- `TASKS.md:665` records the source proof-class gap as `[NEXT-CODEX-POST-REDTEAM]`: `N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally Executed`, with JS runtime parity intentionally not widened in that earlier wave.
- `reports/control_plane/n3-terminal-hemisphere-ontology-authority-lock-2026-05-14_2026-05-22.md` lines 138-185 lock this successor wave id, class, target gate, exact successor write set, implementation bounds, parity proof requirements, and required validation command.
- The predecessor lock at `reports/control_plane/n3-terminal-hemisphere-ontology-authority-lock-2026-05-14_2026-05-22.md:149` and `:155` names the undated packet path. The active reviewed packet for this rewrite is `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`, so same-wave validation must include this dated path.
- Reviewer blocking evidence for this rewrite is treated as authoritative: validating the undated predecessor path strips the active packet from scope and fails with `--wave-id 'n3-js-evidence-walker-runtime-authority-parity-2026-05-22' not found in any tracker sync note`, even though this dated packet carries the same-wave override.
- During Phase A review, the successor wave id was not yet present in `TASKS.md` as its own tracker sync note, so this control-surface packet carried same-wave authorization mechanically until Work Item 6 added the matching tracker sync. The staged Phase B package now records the canonical tracker sync at `TASKS.md:429`, and same-wave validation binds to that current tracker note plus the founder override below:

FOUNDER_OVERRIDE:n3-js-evidence-walker-runtime-authority-parity-2026-05-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-js-evidence-walker-runtime-authority-parity-2026-05-22`
- Active packet: `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/js/engine/pipeline.js`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
  - `mu/seed_registry_manifest.v1.json`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/l4_gates/test_evidence_walker_gate.py`
  - `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py`
  - `reports/control_plane/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_2026-05-26.md`
  - `reports/deferred/non_blocking/n3-js-evidence-walker-runtime-authority-parity-2026-05-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-js-evidence-walker-runtime-authority-parity-2026-05-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
