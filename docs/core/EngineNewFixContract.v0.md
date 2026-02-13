<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-10
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/test_engine_cycle_mapping.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# EngineNew Fix Contract v0

## Purpose

Define the structural contract for GAP-04-FIX (EngineNew step 4, Rule 0.6): the Fix routine that applies a minimal structural perturbation to a stalled state.

**Status:** VECTOR (design-only). This document specifies WHAT Fix must do when implemented. No runtime code implements this contract yet.

**Gap ID:** `GAP-04-FIX` (locked by `tests/test_engine_cycle_mapping.py::TestGapRegistry`)

## Background

The EngineNew 10-step stall-fix-promote cycle (RCXEngineNew.pdf) includes:

- **Step 3** (Rule 0.5): Stall detection — `hash_trace` detects `Ξ(O(G)) = Ξ(G)`.
- **Step 4** (Rule 0.6): Fix routine — `Fix(G)` adds a minimal structural edge to break the stall.
- **Step 5** (Rule 2.2): Recurrence detection — checks if the fix produces a recurring pattern.

Currently, step 4 is implicit: the engine re-applies operators to the stalled state, relying on recurrence/exhaustion detection to eventually terminate. No explicit Fix projection exists in any seed.

## Fix Intent

When the engine detects a stall (step 3 produces `stall: true`), the Fix routine must:

1. Accept the stalled state as input
2. Produce a minimally perturbed output state
3. Return the perturbed state to the engine cycle (step 5)

The perturbation must be **structural** (expressible as a Mu projection), not a host-level hack.

## Input Shape

```
{
  "stalled_state": <Mu>,        // The state that triggered stall detection
  "stall_hash": <string>,       // mu_hash of the stalled state
  "tau_step": <integer>,        // Current trace token step count
  "engine_iteration": <integer> // Which engine iteration detected the stall
}
```

## Output Shape

```
{
  "fixed_state": <Mu>,          // Minimally perturbed state
  "fix_applied": <boolean>,     // true if perturbation was applied; false if Fix declined
  "fix_type": <string>          // Perturbation class: "edge_add" | "vertex_add" | "none"
}
```

## Invariants

### I1: Minimality

Fix must add the smallest possible structural change. Specifically:

- **Edge add:** Add exactly one edge to the graph structure. No bulk modifications.
- **Vertex add:** Add exactly one vertex (e.g., vertex 0 for Empty Set emergence). No bulk additions.
- **None:** If Fix cannot determine a valid perturbation, it must return `fix_applied: false` and pass the stalled state through unchanged.

### I2: Structural purity

Fix must be expressible as a Mu projection (pattern → body). It must NOT:

- Call host functions directly (no Python/JS escape hatch)
- Modify kernel-reserved fields (`_mode`, `_match_ctx`, etc.)
- Depend on wall-clock time, randomness, or external state
- Produce side effects outside the returned output shape

### I3: Idempotence safety

Applying Fix twice to the same stalled state must not compound perturbations. Either:

- The second application returns `fix_applied: false` (recognizes already-fixed state), OR
- The second application produces the same output as the first (true idempotence)

### I4: Stall-breaking

If `fix_applied: true`, the output `fixed_state` must differ from `stalled_state` by at least one structural element. Formally: `mu_hash(fixed_state) != stall_hash`.

### I5: No semantic drift

Fix must not introduce structures that violate the engine's acyclicity constraint (Foundation axiom). The perturbed state must remain a valid input to the next engine cycle step.

## Disallowed Behaviors

| Behavior | Why disallowed |
|----------|---------------|
| Host-only fix (Python/JS code, not a projection) | Violates structural purity; not meta-circular |
| Random perturbation | Non-deterministic; breaks trace reproducibility |
| Copy of another step's output | Fix must be its own structural operation, not a shortcut |
| Modifying kernel fields | Reserved fields are kernel-internal; domain projections must not touch them |
| Unbounded perturbation | Violates minimality; could mask real structural dynamics |

## Required Evidence for VECTOR → NEXT Promotion

All of the following must be satisfied before GAP-04-FIX can be promoted from VECTOR to NEXT:

- [ ] **E1: Stall-recovery failure test** — A test demonstrating that the current implicit fix (engine re-application) fails on a specific input where an explicit Fix projection would succeed. This proves the gap is not merely theoretical.
- [ ] **E2: Fix seed draft** — A concrete `fix.v1.json` seed file with projections for both edge_add and vertex_add, conforming to the input/output shapes above.
- [ ] **E3: Invariant test suite** — Tests verifying I1–I5 against the draft seed using test-local fixtures.
- [ ] **E4: Engine integration sketch** — Design showing how `engine.trace_done` (or a new `engine.stall_detected`) would dispatch to Fix via `_boundary_request`, and how the fixed state re-enters step 5.
- [ ] **E5: VECTOR → NEXT promotion** — Explicit entry in TASKS.md with rationale referencing E1–E4.

## Related Documents

- `docs/core/RCXEngine.v0.md` — Engine cycle (step 4 references Fix)
- `tests/test_engine_cycle_mapping.py` — Gap registry (GAP-04-FIX)
- `TASKS.md` — VECTOR item with promotion checklist
