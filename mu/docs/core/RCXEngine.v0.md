<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-04
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/test_rcx_engine_integration.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# RCX Engine

## Overview

`rcx_engine.v1.json` is the **programmatic equivalent** of the RCX Core Engine Stateless Specification (RCXEngineNew.pdf). It orchestrates the stall-fix-promote loop that tests whether ZF(C)-like structures can emerge from purely structural recursion.

**Key insight:** RCX doesn't assume set theory axioms - it tests whether they emerge under recursive pressure. The engine combines:
- **Recurrence detection** (`recurrence.v1.json` proof-of-concept, `recurrence.v2.json` production) - detects when operators produce repeating patterns
- **Exhaustion detection** (`exhaustion.v1.json`) - detects when operators can make no further progress

## Relationship to RCXEngineNew.pdf

| PDF Concept | Mu Implementation |
|-------------|-------------------|
| Stall predicate (Rule 0.5) | `recurrence.v1.json` (v1 proof-of-concept) / `recurrence.v2.json` (v2 production) detects fixed points |
| Fix routine (Rule 0.6) | Engine adds minimal structural change |
| LeafInvariance (Rule 0.7c') | `recurrence.v1.json` / `recurrence.v2.json` logs trace token τ |
| Operator exhaustion (Rule 3.1) | `exhaustion.v1.json` freezes exhausted operators |
| Closure-on-Second-Demand (Rule 2.2♢) | Closure projection after τ recurs |

## The ZF(C) Hypothesis

The engine tests whether ZFC axioms emerge from structural pressure:

| ZFC Axiom | RCX Trigger | Status |
|-----------|-------------|--------|
| Empty Set | Fix introduces vertex 0 | Emerges on first stall |
| Pairing | Recursion + Rule 2.2♢ | When structure stabilizes on {a,b} |
| Union | Trace closure under token τ | Rule 2.2♢ |
| Infinity | LeafInvariance + Rule 2.2♢ | Produces ω on second τ |
| Foundation | Acyclicity enforced by Fix | Built-in constraint |
| Choice | Rule 2.5♢ fork | Engine logs AC or ¬AC |

**Not assumed, tested:** The engine doesn't postulate these axioms. It runs the stall-fix-promote loop and observes what structures are forced to exist.

## Engine Cycle

```
1. Start with G₀ = ({0}, ∅)
2. Apply operator O to G
3. Check stall: Ξ(O(G)) = Ξ(G) and Ω,Λ unchanged?
4. If stalled → apply Fix(G)
5. Fix adds minimal edge → recurse
6. LeafInvariance? → log trace token τ, freeze operator
7. τ recurs in independent derivation? → project closure Ω(τ)
8. Operator exhausted? → freeze and switch
9. Loop to step 2
```

## Mu Projection Structure

```json
{
  "meta": {
    "name": "RCX_ENGINE",
    "execution_layer": "APPLICATION",
    "requires_patterns": ["non-linear"],
    "dependencies": [
      "recurrence.v1.json (proof-of-concept) / recurrence.v2.json (production)",
      "exhaustion.v1.json"
    ]
  },
  "projections": [
    // Engine orchestration projections
  ]
}
```

## Current Status

**Execution layer:** APPLICATION (highest level, orchestrates closures)

**Known limitations:**
- Requires non-linear pattern matching (provided by structural bridge execution path; not yet native in core-only mode)
- Runtime path now defaults to structural kernel bridge execution via `run_algorithm_meta_circular()`
  (`step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")`)
- Bootstrap algorithm execution remains explicit fallback only (`execution_mode="bootstrap", allow_bootstrap_fallback=True`)
- Integration tests verify full engine pipeline execution (trace, hash, recurrence, exhaustion). See `tests/test_engine_pipeline_verification.py` and `tests/test_engine_orchestration.py`

**Test coverage:** See `tests/test_rcx_engine_integration.py` for current integration tests.

## Trace Tokens and Closures

From the spec (Appendix A.10):

> A trace token τ is a finite sequence of log events captured during recursion. τ serves as a fingerprint of recursive structural pressure and triggers closure under Rule 2.2♢ if minimal-fix replay fails to proceed without aggregation.

The closure object Ω(τ) is projected when:
1. A trace token τ is logged (LeafInvariance detected)
2. An independent derivation encounters the same τ
3. The engine projects Ω(τ) as a new vertex with the appropriate label (e.g., "ω")

## Related Documents

- `mu/docs/core/EngineNewsStructural.v0.md` - Recurrence/exhaustion closure details
- `mu/docs/core/OperatorExhaustion.v0.md` - Exhaustion detection specifics
- `mu/closures/recurrence.v1.json` - Recurrence detection projections (proof-of-concept)
- `mu/closures/recurrence.v2.json` - Recurrence detection projections (hash-accelerated, production)
- `mu/closures/exhaustion.v1.json` - Exhaustion detection projections
- RCXEngineNew.pdf - Formal specification (external)

## Spec References

Key rules from RCXEngineNew.pdf:
- **Rule 0.5** - Stall detection
- **Rule 0.6** - Fix routine
- **Rule 0.7c'** - LeafInvariance degeneracy test
- **Rule 2.2♢** - Closure-on-Second-Demand
- **Rule 3.1** - Operator exhaustion
