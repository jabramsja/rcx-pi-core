<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-26
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_ontology_promotion_contract_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Ontology Promotion Contract v0

## Purpose

Define the invariants governing ontology promotion in RCX: the conditions under which a structural pattern observed in Mu execution may be elevated to a first-class ontological token (a named entity in the system's vocabulary of structural operations).

**Scope note:** v0 is contract-only; runtime enforcement deferred to A12. This document establishes the invariants that any future runtime implementation must satisfy. No runtime host files are changed by this wave.

## Background

RCX's structural substrate produces emergent patterns through projection execution: recurrence closures, exhaustion boundaries, metabolization cycles, and hemisphere routing states. Some of these patterns recur with sufficient regularity and independence to warrant ontological status — becoming named tokens that the system can reference, compose, and reason about structurally.

Without promotion discipline, the system risks:
1. **Premature reification** — naming patterns that are artifacts of a specific seed or substrate, not genuine structural invariants
2. **Host contamination** — allowing host-language semantics to mint ontological tokens (violating North Star #5, #6)
3. **Provenance loss** — tokens appearing without traceable lineage from structural dynamics
4. **Instability** — promoting patterns that collapse under perturbation, creating brittle ontologies

## Invariants

### INV_OPROMO_1: Recurrence Witness Requirement

**Statement:** No ontology promotion without >= 2 independent recurrence witnesses.

**Rationale:** A pattern observed once may be coincidental. A pattern observed in two independent recurrence traces — different seeds, different initial conditions, same structural outcome — provides minimal evidence of genuine structural invariance rather than seed-specific artifact.

**Measurable check:** Given candidate pattern P, there must exist at least two recurrence traces T1, T2 such that:
- T1 and T2 originate from distinct seed configurations (different seed files or different projection subsets)
- Both T1 and T2 exhibit closure containing P (P appears in the closure's fixed-point structure)
- T1 and T2 are independently reproducible (deterministic replay from their respective seeds)

**Fail-closed rule:** If fewer than 2 independent witnesses exist for a candidate promotion, the promotion MUST NOT proceed. The candidate remains an observed pattern, not a promoted token. No override mechanism exists at v0; future versions may define a founder-override path with explicit justification.

### INV_OPROMO_2: Bounded-Perturbation Closure Stability

**Statement:** Promotion requires bounded-perturbation closure stability.

**Rationale:** A genuinely structural pattern must survive small changes to its context. If adding or removing a single projection from the seed destroys the pattern, it is likely an artifact of a specific projection arrangement rather than a deep structural invariant.

**Measurable check:** Given candidate pattern P observed in seed S with projections {p1, ..., pN}:
- For each single-projection removal S_i = S \ {p_i} where P's witness projections are not removed: P must still appear in at least one recurrence trace from S_i
- For at least one single-projection addition S+ = S ∪ {p_extra} where p_extra is a structurally valid but non-interfering projection: P must still appear in at least one recurrence trace from S+

**Fail-closed rule:** If the candidate pattern vanishes under any single non-witness projection removal, or under all tested single-projection additions, promotion MUST NOT proceed. The pattern is classified as "arrangement-dependent" and logged for future investigation, not promoted.

### INV_OPROMO_3: Host Cannot Mint Ontology Tokens

**Statement:** Host cannot mint ontology tokens (seed authority only).

**Rationale:** North Star #5 ("Emergence must be attributable to RCX dynamics, not 'Python did it'") and #6 ("Host languages are scaffolding only; their assumptions must not leak into semantics") require that ontological tokens arise from structural dynamics expressed in seeds, not from host-language code. If host code can create ontological tokens, emergence is a host artifact.

**Measurable check:**
- No host runtime file (`rcx_pi/selfhost/*.py`, `mu/host/js/**/*.js`) contains token-minting logic (functions that create new ontological token types at runtime)
- All promoted tokens must trace to seed projection patterns via a documented derivation chain
- The derivation chain must be reproducible: given the same seeds and the same substrate, the same tokens must be derivable

**Fail-closed rule:** If a proposed ontology token cannot be traced to seed-derived structural dynamics — if its existence depends on host-language logic rather than projection execution — promotion MUST NOT proceed. The token is classified as "host-originated" and rejected.

### INV_OPROMO_4: Provenance Lineage Requirement

**Statement:** Every promoted token carries tau-lineage provenance.

**Rationale:** Ontological tokens without provenance are opaque — they cannot be audited, reproduced, or falsified. Every promoted token must carry a lineage record (tau-lineage) that traces its origin through the structural dynamics that produced it, enabling independent verification and replay.

**Measurable check:** Every promoted token T must include a provenance record containing:
- `witness_traces`: list of >= 2 recurrence trace references (per INV_OPROMO_1)
- `seed_configs`: the seed configurations that produced each witness trace
- `closure_structure`: the fixed-point structure in which T was observed
- `perturbation_log`: results of bounded-perturbation tests (per INV_OPROMO_2)
- `derivation_timestamp`: when the promotion was performed
- `substrate_versions`: which substrate versions (Python commit, JS commit) were used

**Fail-closed rule:** If a promoted token lacks any of the required provenance fields, it MUST be demoted back to "observed pattern" status until provenance is complete. No token may persist in promoted status without full tau-lineage.

## Relationship to Existing Contracts

| Contract | Relationship |
|----------|-------------|
| `NorthStarSemantics.v0.md` | INV_OPROMO_3 enforces North Star #5 and #6 at the ontology layer |
| `L4ExecutionContract.v2.md` | A11 is classified L4_ENABLER; runtime enforcement (A12) will be L4_STRUCTURAL |
| `Boot1LoopContract.v0.md` | Ontology promotion is orthogonal to loop policy; promoted tokens must be observable via both trampoline and recursive paths |
| `StructuralPurity.v0.md` | Promoted tokens must satisfy structural purity — no host-language semantics embedded in token definitions |

## Version History

| Version | Date | Change |
|---------|------|--------|
| v0 | 2026-02-26 | Contract-only. 4 invariants defined. Runtime enforcement deferred to A12. |
