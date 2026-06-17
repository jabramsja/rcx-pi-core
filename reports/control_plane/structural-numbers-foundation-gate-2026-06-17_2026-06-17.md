# Structural-Numbers-Foundation-Gate-2026-06-17 2026-06-17

Date: 2026-06-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-foundation-gate-2026-06-17
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage-1 foundation: add a cross-substrate equivalence gate proving the binary-positional numeral is valid Mu + content-addressed-equal + int/BigInt round-trips + Python/JS-identical. Gate-only, no runtime change, no host-debt increase.

## Scope

Files/directories in scope (gate-only, additive):

- `mu/tests/l4_gates/test_structural_numbers_foundation.py` — NEW. The sole structural artifact (`structural_artifact_ref` per TASKS.md): the cross-substrate equivalence gate test. It is a test, not runtime code.
- `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json` — generated indicator artifact, produced by the `indicator_collection_command` (see L4 fields below).
- `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md` — this Phase A packet (planning/provenance only).
- `TASKS.md`, `STATUS.md` — tracker/status note updates for this wave at session/commit boundaries (no other tracker entries touched).

Read-only design inputs (referenced, NOT modified):

- `mu/docs/core/StructuralNumbers.v0.md` — defines the binary-positional numeral being gated.
- The Python and JS substrate content-hash (`mu_hash`) surfaces — invoked read-only by the test to compute content hashes; not changed.

## Work Items

Concrete, bounded tasks derived from the TASKS.md `[NEXT-CODEX-POST-REDTEAM]` tracker note (2026-06-17):

1. Create `mu/tests/l4_gates/test_structural_numbers_foundation.py` over a numeric corpus that includes `2**250` (Mu depth ~250 < 300 bound), asserting the four foundation properties:
   - **Valid Mu** — each integer's binary-positional numeral encoding (per `StructuralNumbers.v0.md`) is a well-formed Mu structure.
   - **Content-addressed equality** — `mu_hash(encode(a)) == mu_hash(encode(b))` iff `a == b` (equal hash iff equal int).
   - **int/BigInt round-trip** — `decode(encode(n)) == n` for every corpus value.
   - **Python/JS parity** — the Python and JS substrates produce the SAME content hash for each numeral (L3 parity).
2. Run the `evidence_command` (see L4 fields below) and confirm: test green under `PYTHONHASHSEED=0`; host-semantics ratchet unchanged; host-authority inventory ratchet unchanged; L4 execution-contract enforcement passes for `--wave-id structural-numbers-foundation-gate-2026-06-17`.
3. Produce the indicator artifact via the `indicator_collection_command` (see L4 fields below).

Per the tracker `progress_proof_before`, no executable gate currently proves these properties, so all three work items are unlanded.

## Constraints (Out of Scope)

- NO runtime/substrate/seed change. Do not modify `mu/host/python/rcx_pi/selfhost/`, `mu/host/js/eval_step.js`, or any seed. As an L4_ENABLER, this wave MUST NOT touch runtime dirs.
- NO host-semantics ratchet increase and NO host-authority inventory increase (gate-only, additive coverage).
- NO `_stage0_match` cutover and NO arithmetic-projection seed — those are later StructuralNumbers stages, explicitly deferred.
- NO canonicalization that introduces a host primitive (e.g., signed-zero normalization). Parity-safety must come from pure content-addressed structure, not host fix-ups.
- NO new files beyond the three named in Scope (gate test, generated indicator JSON, this packet).

## Stop Conditions

- STOP (done) once `mu/tests/l4_gates/test_structural_numbers_foundation.py` exists and the full `evidence_command` passes with both ratchets unchanged. Do not extend into later StructuralNumbers stages.
- STOP and escalate to the founder if proving any property requires a runtime/substrate/seed change — that reclassifies the wave as L4_STRUCTURAL and exceeds gate-only scope; do not mutate runtime to make the gate pass.
- STOP and report if the binary-positional numeral cannot be shown valid-Mu or content-addressed-equal without a host primitive or canonicalization (parity hazard; cf. the signed-zero divergence). Surface it; do not work around it.
- STOP and use the established Phase B / commit pipeline; do not hand-commit or bypass gates.

## Acceptance Criteria

- `mu/tests/l4_gates/test_structural_numbers_foundation.py` exists and PASSES under `PYTHONHASHSEED=0`.
- All four foundation properties (valid Mu; content-addressed equality iff int-equality; int/BigInt round-trip; Python/JS hash parity) are each asserted across the corpus, including `2**250`.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py` reports NO host-semantics increase.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` reports NO host-authority inventory increase.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id structural-numbers-foundation-gate-2026-06-17` passes.
- No runtime/substrate/seed file is modified (verified by diff); L3 parity preserved.
- The indicator artifact `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json` is produced.

## Grounding / Authorization

- **Authorization (TASKS.md):** Tracker sync note dated 2026-06-17, `[NEXT-CODEX-POST-REDTEAM]` — "StructuralNumbers foundation cross-substrate equivalence gate." Class: **L4_ENABLER**. `target_gate_id`: G8. `primary_blocker_class`: DESIGN. `primary_invariant_id`: INV_CROSS_SUBSTRATE_PARITY.
- **Governing packet:** this file, `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md` (named as `Packet:` in the TASKS.md tracker note).
- **Wave-bound founder override** (so commit automation derives the same-wave override mechanically):

  `FOUNDER_OVERRIDE:structural-numbers-foundation-gate-2026-06-17`

- **L4 class fit:** L4_ENABLER adds the `mu/tests/l4_gates/` gate test as a prerequisite that locks the foundation properties for the G8 line without touching runtime dirs, consistent with the gate-only `evidence_delta` below.

## Request from Post-Merge Supervisor

Routing provenance (next-candidate routed by the post-merge supervisor):

- Routed next-candidate: `structural-numbers-foundation-gate-2026-06-17`
- Intent: StructuralNumbers Stage-1 foundation — a cross-substrate equivalence gate proving the binary-positional numeral is valid Mu, content-addressed-equal, int/BigInt round-tripping, and Python/JS-identical. Gate-only; no runtime change; no host-debt increase.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-foundation-gate-2026-06-17 --output reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_structural_numbers_foundation.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-foundation-gate-2026-06-17.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-foundation-gate-2026-06-17`
- Active packet: `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_structural_numbers_foundation.py`
  - `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md`
  - `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-foundation-gate-2026-06-17`
- Active packet: `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2bb37ee020f1cd24144ea532d9a9defe7aee965c0a4a4a30da6a37696107cf3e`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_structural_numbers_foundation.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_structural_numbers_foundation.py`
  - `reports/control_plane/structural-numbers-foundation-gate-2026-06-17_2026-06-17.md`
  - `reports/l4_wave_indicators/structural-numbers-foundation-gate-2026-06-17.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
