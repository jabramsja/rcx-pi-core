<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-13
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/structural/test_engine_cycle_mapping.py

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

**Status:** IMPLEMENTED (2026-02-13, Rounds 15D–15I). All 5 invariants (I1–I5) verified by `tests/structural/test_fix_invariants.py`. Engine integration via 3 dispatch projections in `rcx_engine.v1.json`. Cross-substrate parity locked.

**Gap ID:** `GAP-04-FIX` — **CLOSED** (removed from `tests/structural/test_engine_cycle_mapping.py::TestGapRegistry`)

## Background

The EngineNew 10-step stall-fix-promote cycle (RCXEngineNew.pdf) includes:

- **Step 3** (Rule 0.5): Stall detection — `hash_trace` detects `Ξ(O(G)) = Ξ(G)`.
- **Step 4** (Rule 0.6): Fix routine — `Fix(G)` adds a minimal structural edge to break the stall.
- **Step 5** (Rule 2.2): Recurrence detection — checks if the fix produces a recurring pattern.

Step 4 is now structural: `mu/closures/fix.v1.json` (6 projections) handles edge_add, vertex_add, and pass-through with idempotence guards. Engine dispatch via `engine.hash_done_fix`, `engine.fix_done_applied`, `engine.fix_done_none` in `mu/programs/rcx_engine.v1.json`.

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

- [x] **E1: Stall-recovery failure test** — Pre-integration gap proof established in Round 15D (`TestImplicitFixFailure`: identity+graph stalls with value unchanged, proving no fix mechanism existed). After E4 integration, tests renamed to `TestFixIntegrationEvidence` and updated to verify fix now works (stall=false, value perturbed).
- [x] **E2: Fix seed draft** — `mu/closures/fix.v1.json` v1.1.0, 6 projections (init, edge_add_guard, edge_add, vertex_add_guard, vertex_add, pass_through). Registered in seed_integrity.py + eval_step.js. Rounds 15D–15E.
- [x] **E3: Invariant test suite** — `tests/structural/test_fix_invariants.py`, 19 tests across I1–I5 (6 minimality, 2 purity, 3 idempotence, 3 stall-breaking, 5 no-drift). All green. Round 15F.
- [x] **E4: Engine integration** — `engine.hash_done_fix` dispatches to fix.v1.json on stall=true. `engine.fix_done_applied` / `engine.fix_done_none` route fixed/original state to recurrence. 10 engine projections total. Cross-substrate parity locked (4 tests). Rounds 15G–15H.
- [x] **E5: Closure bookkeeping** — TASKS.md updated: GAP-04-FIX closed in NEXT→Ra. Contract status updated. EngineNew 9/10 structural. Round 15I.

## Related Documents

- `mu/docs/core/RCXEngine.v0.md` — Engine cycle (step 4 is now structural)
- `tests/structural/test_engine_cycle_mapping.py` — Step 4 mapped as structural; gap registry tracks remaining gaps (GAP-10-LOOP only)
- `tests/structural/test_fix_invariants.py` — 19 invariant tests (I1–I5)
- `tests/parity/test_js_parity_automated.py::TestEngineFixPathParity` — Cross-substrate parity lock (4 tests)
- `TASKS.md` — GAP-04-FIX closed in Ra
