# Structural-Numbers-Design-Doc-2026-06-17

Date: 2026-06-17
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-design-doc-2026-06-17
Phase-A-Lock: LOCKED
Purpose: Land the canonical design spec for representing RCX numbers as structural Mu (self-hosting / meta-circular, not host semantics) plus the P6 re-open note. StructuralNumbers.v0.md adopts binary-positional structural numerals (Coq positive/N/Z shape) with arithmetic and equality as Mu projections, exact rationals and signed-digit reals (no host floats), and a proven-equivalent host-accelerated int/BigInt boundary codec, plus the von Neumann ordinal <-> N isomorphism for engine unification and a staged migration program. TypedNumericEnvelopes.v0.md (P6) is re-opened and pointed at the new spec. Docs only; no runtime, seed, or test-logic change.

## Scope

Author StructuralNumbers.v0.md design spec + reopen P6 (TypedNumericEnvelopes) — docs only.

## Request from Post-Merge Supervisor

Land the canonical design spec for representing RCX numbers as structural Mu (self-hosting / meta-circular, not host semantics) plus the P6 re-open note. StructuralNumbers.v0.md adopts binary-positional structural numerals (Coq positive/N/Z shape) with arithmetic and equality as Mu projections, exact rationals and signed-digit reals (no host floats), and a proven-equivalent host-accelerated int/BigInt boundary codec, plus the von Neumann ordinal <-> N isomorphism for engine unification and a staged migration program. TypedNumericEnvelopes.v0.md (P6) is re-opened and pointed at the new spec. Docs only; no runtime, seed, or test-logic change.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: DESIGN.
- `primary_invariant_id`: INV_CROSS_SUBSTRATE_PARITY.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-design-doc-2026-06-17.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-design-doc-2026-06-17 --output reports/l4_wave_indicators/structural-numbers-design-doc-2026-06-17.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_doc_contracts.py --tb=short && rg -n "structural-numbers-design-doc-2026-06-17" TASKS.md && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id structural-numbers-design-doc-2026-06-17`.
- `evidence_delta`: (1) New mu/docs/core/StructuralNumbers.v0.md adopts binary-positional structural numerals (Coq positive/N/Z shape) as the canonical RCX integer, with arithmetic/equality as Mu projections, exact rationals + signed-digit reals (no host floats), a proven-equivalent host-accelerated int/BigInt boundary codec, and a von Neumann ordinal <-> N isomorphism for engine unification. (2) mu/docs/core/TypedNumericEnvelopes.v0.md (P6) is re-opened by founder direction (the override authority) as a structural-purity reframing prompted by the Stage0 escalation, and superseded by the new spec -- this is NOT a firing of P6's original mixed-int/float promotion triggers (the direction is integer-first, no host floats; the integer-only RCXEngineNew seed motivates structural integers but is not the mixed-int/float trigger). (3) Docs only; no runtime, seed, parity-semantics, or test-logic change; doc-governance contracts pass..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-design-doc-2026-06-17.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-design-doc-2026-06-17`
- Active packet: `reports/control_plane/structural-numbers-design-doc-2026-06-17_2026-06-17.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `83bfc1026761500569d2053e39de68044cedc288c7c475cb57e3b5f590cc88b1`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-design-doc-2026-06-17.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q tests/docs/test_doc_contracts.py --tb=short && rg -n "structural-numbers-design-doc-2026-06-17" TASKS.md && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id structural-numbers-design-doc-2026-06-17`.
- Evidence delta: (1) New mu/docs/core/StructuralNumbers.v0.md adopts binary-positional structural numerals (Coq positive/N/Z shape) as the canonical RCX integer, with arithmetic/equality as Mu projections, exact rationals + signed-digit reals (no host floats), a proven-equivalent host-accelerated int/BigInt boundary codec, and a von Neumann ordinal <-> N isomorphism for engine unification. (2) mu/docs/core/TypedNumericEnvelopes.v0.md (P6) is re-opened by founder direction (the override authority) as a structural-purity reframing prompted by the Stage0 escalation, and superseded by the new spec -- this is NOT a firing of P6's original mixed-int/float promotion triggers (the direction is integer-first, no host floats; the integer-only RCXEngineNew seed motivates structural integers but is not the mixed-int/float trigger). (3) Docs only; no runtime, seed, parity-semantics, or test-logic change; doc-governance contracts pass..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-design-doc-2026-06-17.json`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/core/StructuralNumbers.v0.md`
  - `mu/docs/core/TypedNumericEnvelopes.v0.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `reports/control_plane/structural-numbers-design-doc-2026-06-17_2026-06-17.md`
  - `reports/l4_wave_indicators/structural-numbers-design-doc-2026-06-17.json`
  - `roadmap/MANIFEST.md`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
