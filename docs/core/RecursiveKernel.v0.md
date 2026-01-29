# Recursive Kernel Design (Phase 8)

**Status:** DESIGN - v2 (9-agent review 2026-01-28)
**Goal:** Define honest boundaries for self-hosting while maximizing structural execution

---

## 9-Agent Review Summary (2026-01-28)

Two rounds of comprehensive agent review (6 agents, then 9 agents) reached consensus:

### Key Findings

| Finding | Agent(s) | Implication |
|---------|----------|-------------|
| **THREE nested loops exist** | Expert, Translator, Structural-proof | run_mu → step_kernel_mu → eval_step |
| **Python stack limits (1000 frames)** | Adversary | Truly recursive projections IMPOSSIBLE at scale |
| **eval_step IS the bootstrap primitive** | Expert, Structural-proof | Like Forth's NEXT - irreducible "hardware" |
| **Hash stall detection is INCOMPLETE** | Fuzzer | Misses oscillation (A→B→A), growth (X→[X]) |
| **EngineNews ASSUMES substrate** | Verifier | It's a SPEC about emergence, not execution bootstrap |
| **Independence checking is NON-STRUCTURAL** | Adversary | Rule 2.2 closure needs log comparison |
| **Fuel-based approach doesn't work** | Verifier, Expert | Moves loop, doesn't eliminate it |

### Critical Question

**Structural-proof agent:** "Is 'iterate until stable' a PRIMITIVE or DERIVED operation?"

- If **PRIMITIVE** → Accept Python substrate (honest boundary)
- If **DERIVED** → Must express as projections (but how without infinite regress?)

### Recommended Path (Advisor)

1. **Option 2: Phased Recursive** - Incrementally move loops into projections with validation
2. **Option 5: Trace-Driven** - Reframe iteration as closure detection (aligns with EngineNews Rule 2.2)
3. **Minimal Python Substrate** - Accept honest boundaries for what MUST be Python

---

## Problem Statement

### The Three Loops

Phase 7d-1 revealed not one but THREE nested Python loops:

```
run_mu (outer cycle)          # L3 boundary - scaffolding
  └─> step_kernel_mu          # @host_iteration debt (PARTIAL L2)
        └─> eval_step         # BOOTSTRAP PRIMITIVE (like Forth's NEXT)
```

**Previous approaches failed** because they tried to eliminate the WRONG loop:
- Fuel-based: Moved step_kernel_mu loop, didn't eliminate it
- CPS transform: Still needs something to drive continuations
- Meta-kernel: Infinite regress - who runs the meta-kernel?

### The Honest Question

**What is the MINIMUM Python substrate required for honest emergence?**

The goal isn't "zero Python" - that's impossible. The goal is ensuring:
1. Python provides only MECHANICAL operations (no semantic decisions)
2. All MEANING comes from structural projections
3. Results are "honest structure" - not Python artifacts

---

## Design: Minimal Python Substrate

### What Python MUST Provide (Bootstrap Primitives)

| Primitive | Why Irreducible | Analogy |
|-----------|-----------------|---------|
| `eval_step()` first-match-wins | Projection application | Forth's NEXT |
| `mu_equal()` hash comparison | Fixed-point detection | Hardware comparator |
| `max_steps` resource limit | Termination guarantee | Watchdog timer |
| Stack depth protection | Prevent overflow | Memory protection |
| Projection loader | Parse JSON, validate | ROM bootstrap |

These are the "hardware" that structural projections run on.

### What Python SHOULD NOT Provide

| Operation | Why Prohibited | Alternative |
|-----------|----------------|-------------|
| Semantic branching | Hides decisions | Projection patterns |
| Arithmetic on data | Non-structural | Linked-list countdown |
| String manipulation | Host smuggling | Structural keys |
| Control flow choices | Python artifact | State machine patterns |

### The Honest Boundary

```
┌─────────────────────────────────────────────────────┐
│  STRUCTURAL LAYER (Mu projections)                  │
│  - Projection selection (kernel.v1 linked-list)     │
│  - Pattern matching (match.v2 projections)          │
│  - Substitution (subst.v2 projections)              │
│  - Domain logic (user projections)                  │
│  - EngineNews engine cycle (stall/fix/promote)      │
└─────────────────────────────────────────────────────┘
                         │
                   (honest boundary)
                         │
┌─────────────────────────────────────────────────────┐
│  PYTHON SUBSTRATE (bootstrap primitives)            │
│  - eval_step: apply first matching projection       │
│  - mu_equal: detect fixed-point (structural hash)   │
│  - max_steps: resource exhaustion protection        │
│  - stack guard: prevent overflow                    │
│  - loader: parse seeds, validate schema             │
└─────────────────────────────────────────────────────┘
```

---

## Design Question

**How do we MAXIMIZE structural execution while ACCEPTING irreducible primitives?**

The revised question acknowledges:
1. Some operations ARE primitives (cannot be expressed as projections)
2. The goal is minimizing primitives, not eliminating them
3. Honest boundaries are better than false claims of "pure structural"

---

## Proposed Solution: Phased Structural Maximization

### Strategy: Specialize Each Loop

Rather than trying to eliminate ALL loops (impossible), we specialize EACH loop:

| Loop | Current State | Phase 8 Target | Method |
|------|---------------|----------------|--------|
| `run_mu` | Python for-loop | ACCEPT as L3 boundary | Scaffolding (outer cycle) |
| `step_kernel_mu` | Python for-loop | STRUCTURAL | Specialize to single eval_step |
| `eval_step` | Python for-loop | ACCEPT as PRIMITIVE | Bootstrap hardware |

### Key Insight: Specialize step_kernel_mu

The `step_kernel_mu` loop can be specialized because:
1. It always processes kernel state (known structure)
2. Kernel projections form a FINITE state machine
3. Each state transition is ONE eval_step call

**Current:**
```python
for _ in range(max_steps):
    result = eval_step(kernel_projs, current)
    if is_done(result): return result
    current = result
```

**Target:**
```python
# Single eval_step that returns either DONE or NEXT state
# Python only checks termination condition - no semantic decisions
result = eval_step(kernel_projs, current)
while not is_terminal(result) and steps < max_steps:
    result = eval_step(kernel_projs, result)
    steps += 1
```

The loop REMAINS but it's now **mechanical** (no semantic branching).

### Trace-Driven Closure Detection

Align with EngineNews Rule 2.2 (closure-on-second-demand):

```
Engine state includes trace: [...previous states...]
Closure detected when: trace token τ recurs independently
```

This reframes "iterate until stable" as "accumulate trace until closure" - which IS structural (trace is a linked list).

---

## Approaches Evaluated (9-Agent Consensus)

### A. Fuel-Based Recursion (REJECTED)

**6-agent review:** Fuel doesn't eliminate loop, just moves it.

**Problem:** Still need Python to repeatedly call eval_step until fuel exhausted.

### B. Truly Recursive Projections (REJECTED)

**Adversary finding:** Python stack limit (1000 frames) makes this IMPOSSIBLE at scale.

**Problem:** Deeply nested structures overflow stack before completion.

### C. CPS Transform (REJECTED)

**Expert finding:** Massive complexity with no clear benefit.

**Problem:** Would need to rewrite match.v2, subst.v2 entirely.

### D. Meta-Kernel (REJECTED)

**Structural-proof finding:** Infinite regress - who runs the meta-kernel?

**Problem:** Doesn't solve the fundamental bootstrap problem.

### E. Minimal Python Substrate (SELECTED)

**Advisor recommendation:** Accept honest boundaries.

**Approach:** Define and document the irreducible primitives, maximize everything above.

### F. Trace-Driven Iteration (SELECTED - supplementary)

**Advisor recommendation:** Reframe as closure detection.

**Approach:** EngineNews engine cycle IS the iteration model - stall/fix/promote/close.

---

## Detailed Design: Honest Substrate + Structural Maximum

### Layer 1: Python Bootstrap Primitives

These are DOCUMENTED as irreducible:

```python
# eval_step: First-match-wins projection application
# This IS the bootstrap primitive (like Forth's NEXT)
def eval_step(projections: list, value: Mu) -> Mu:
    for proj in projections:  # PRIMITIVE loop - documented as hardware
        bindings = match(proj["pattern"], value)
        if bindings is not NO_MATCH:
            return substitute(proj["body"], bindings)
    return value  # stall

# mu_equal: Hash-based fixed-point detection
# Structural comparison via content hash
def mu_equal(a: Mu, b: Mu) -> bool:
    return content_hash(a) == content_hash(b)  # PRIMITIVE

# Resource limits: Termination guarantee
MAX_STEPS = 10000  # PRIMITIVE - prevents runaway
STACK_LIMIT = 900  # PRIMITIVE - prevents overflow
```

### Layer 2: Structural Kernel (kernel.v1 + match.v2 + subst.v2)

All projection SELECTION is structural:

```json
{
    "id": "kernel.try",
    "pattern": {
        "_mode": "kernel",
        "_phase": "try",
        "_projs": {"head": {"var": "proj"}, "tail": {"var": "rest"}}
    },
    "body": {
        "_mode": "match",
        "_pattern": {"var": "proj.pattern"},
        "_input": {"var": "input"},
        "_on_success": "subst",
        "_on_fail": "try_next",
        "_remaining": {"var": "rest"}
    }
}
```

### Layer 3: Domain Projections (User Code)

User projections run WITHIN the structural kernel:

```json
{
    "id": "classify.primitive",
    "pattern": {"_c": {"var": "v"}},
    "body": {"kind": "primitive", "value": {"var": "v"}}
}
```

### How The Layers Interact

```
User calls: run_mu(user_projections, input)
                │
                ▼
        ┌───────────────────┐
        │    run_mu loop    │  ← L3 boundary (scaffolding)
        │   (Python cycle)  │
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  step_kernel_mu   │  ← STRUCTURAL (kernel.v1)
        │  (structural sel) │     Python only checks termination
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │    eval_step      │  ← PRIMITIVE (bootstrap hardware)
        │  (first-match)    │     Documented as irreducible
        └───────────────────┘
```

---

## Implementation Plan

### Phase 8a: Document Bootstrap Primitives

1. Create `docs/core/BootstrapPrimitives.v0.md`
2. List all irreducible Python operations
3. Justify WHY each is primitive (cannot be projection)
4. Agent verification: Are these truly minimal?

### Phase 8b: Simplify step_kernel_mu

1. Remove semantic branching from the loop
2. Make termination check purely mechanical: `is_terminal(result)`
3. Document that loop is MECHANICAL not SEMANTIC
4. Test: All existing tests pass

### Phase 8c: Add Oscillation Detection

**Fuzzer finding:** Hash comparison misses A→B→A cycles.

1. Add optional cycle detection (trace last N states)
2. Detect oscillation structurally (pattern in trace list)
3. This is SUPPLEMENTARY protection, not core

### Phase 8d: Align with EngineNews Trace Model

1. Add structural trace accumulation to kernel state
2. Closure = trace token recurs independently
3. This enables Rule 2.2 (closure-on-second-demand)

### Phase 8e: Update Debt Tracking

1. Reclassify `eval_step` loop as PRIMITIVE (not debt)
2. Reclassify `run_mu` loop as L3 BOUNDARY (scaffolding)
3. Only `step_kernel_mu` semantic decisions are debt
4. Update STATUS.md with honest counts

### Phase 8f: Verification Suite

1. Grounding tests: Document what IS structural
2. Fuzzer tests: Stress test the boundaries
3. Agent review: 9-agent consensus on honesty

---

## Success Criteria

### Honest Boundaries Documented

- [ ] Bootstrap primitives documented in `docs/core/BootstrapPrimitives.v0.md`
- [ ] Each primitive justified (why irreducible)
- [ ] 9-agent consensus on completeness

### Structural Maximization Achieved

- [ ] `step_kernel_mu` has NO semantic branching (only terminal check)
- [ ] Projection SELECTION is fully structural (kernel.v1)
- [ ] Trace accumulation is structural (linked list)

### Debt Reclassification

- [ ] `eval_step` loop marked as PRIMITIVE (not debt)
- [ ] `run_mu` loop marked as L3 BOUNDARY (scaffolding)
- [ ] Only true debt tracked: semantic decisions in Python

### Test Suite Passing

- [ ] All 1300+ existing tests pass
- [ ] Grounding tests document structural claims
- [ ] Fuzzer tests stress boundaries (3500+ examples)

### EngineNews Compatibility

- [ ] Trace model supports Rule 2.2 (closure-on-second-demand)
- [ ] Engine cycle (stall/fix/promote) expressible as projections
- [ ] EngineNews can run on RCX substrate

---

## Open Questions

1. **Is `eval_step` truly primitive?** Could first-match-wins be expressed structurally somehow?

2. **Oscillation vs. intended cycles?** Some programs legitimately cycle (e.g., clock). How to distinguish from stuck oscillation?

3. **Independence checking:** Rule 2.2 requires "τ recurs independently" - this seems to require log comparison. Can this be structural?

4. **Trace depth:** How many states to keep in trace for closure detection? Memory vs. accuracy tradeoff.

5. **L3 Bootstrap:** When do we tackle the `run_mu` outer loop? Is L3 even achievable, or is it the "edge of structure"?

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Primitives not minimal | Low | False claims | 9-agent verification |
| Oscillation undetected | Medium | Stuck programs | Trace-based cycle detection |
| EngineNews incompatible | Low | Goal missed | Early integration testing |
| Debt reclassification disputed | Medium | Confusion | Clear documentation, agent consensus |
| Performance regression | Low | Slower tests | Profile if needed |

---

## Appendix A: Current Code Locations

- Kernel projections: `seeds/kernel.v1.json`
- Match projections: `seeds/match.v2.json`
- Subst projections: `seeds/subst.v2.json`
- Python execution loop: `rcx_pi/selfhost/step_mu.py:243-276`
- Debt marker: `rcx_pi/selfhost/step_mu.py:190` (@host_iteration)

## Appendix B: EngineNews Alignment

EngineNews (RCXEngineNew.pdf) defines the engine cycle:

```
stall → fix → promote → closure
```

Where:
- **stall:** `Ξ(O(G)) = Ξ(G)` (fixed-point)
- **fix:** Apply ω operator
- **promote:** Lift grounded values
- **closure:** Rule 2.2 (trace token recurs independently)

RCX substrate must support this cycle. The bootstrap primitives provide:
- `mu_equal` → stall detection
- `eval_step` → projection application (fix)
- Trace accumulation → closure detection

## Appendix C: Agent Review History

| Date | Agents | Focus | Outcome |
|------|--------|-------|---------|
| 2026-01-28 (Round 1) | 6 | Fuel-based approach | REJECTED - moves loop, doesn't eliminate |
| 2026-01-28 (Round 2) | 9 | Loops as projections | PARTIAL - honest boundaries needed |
| 2026-01-28 (Round 2) | 9 | EngineNews alignment | CLARIFIED - EngineNews assumes substrate |

---

**Author:** Claude Code (Phase 8 Design v2)
**Date:** 2026-01-28
**Status:** DESIGN - v2 based on 9-agent consensus
