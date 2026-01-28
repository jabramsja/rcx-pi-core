# Bootstrap Primitives (Phase 8a)

**Status:** IMPLEMENTATION - 9-agent review v2
**Goal:** Define the minimal, irreducible Python substrate for honest self-hosting

---

## Executive Summary

RCX achieves self-hosting/meta-circularity with an explicit bootstrap boundary. This document defines the **five primitives** that Python must provide - everything above this layer is structural Mu projections.

This is analogous to:
- **Forth's NEXT** - the inner interpreter that runs threaded code
- **Lisp's eval/apply** - the substrate that runs s-expressions
- **Hardware instruction fetch** - the cycle that executes machine code

No self-hosting system eliminates its bootstrap primitive. The goal is making it **minimal, mechanical, and documented**.

---

## Scope and Self-Hosting Levels

**This document defines ONLY the irreducible Python substrate (the "hardware").**

It does NOT define the complete architecture for self-hosting. The primitives are **necessary but not sufficient**.

| Level | What | Status | Enabled By |
|-------|------|--------|------------|
| **L1: Algorithmic** | match/subst as projections | DONE | eval_step + mu_equal |
| **L2: Operational** | kernel loop as projections | PARTIAL | All 5 primitives |
| **L3: Full Bootstrap** | RCX runs RCX | FUTURE | All 5 primitives + structural outer loop |

All three levels USE these primitives. The primitives enable self-hosting but don't guarantee it.

### Primitives vs. Debt vs. Scaffolding

| Category | Definition | Examples |
|----------|------------|----------|
| **Bootstrap Primitive** | Irreducible - cannot be expressed as projection | eval_step, mu_equal, max_steps, stack_guard, loader |
| **Scaffolding** | Temporary Python that COULD become structural | run_mu outer loop (L3 boundary) |
| **Debt** | Python making semantic decisions that SHOULD be projections | Unmarked semantic branching |

**Key distinction:** Primitives are NOT debt. They are the honest boundary where structure ends and hardware begins.

---

## The Five Bootstrap Primitives

### 1. `eval_step` - Projection Application

**What it does:**
```python
def eval_step(projections: list[Projection], value: Mu) -> Mu:
    """Apply first matching projection to value."""
    for proj in projections:
        bindings = match(proj["pattern"], value)
        if bindings is not NO_MATCH:
            return substitute(proj["body"], bindings)
    return value  # stall - no projection matched
```

**Why irreducible:**
- This IS the execution primitive - like Forth's NEXT
- Projections cannot "apply themselves" - something must try them
- The for-loop is the bootstrap iteration - it cannot be a projection

**What it does NOT do:**
- No semantic decisions (just pattern match + substitute)
- No arithmetic on data values
- No control flow choices beyond "first match wins"

**Analogy:** CPU instruction fetch-decode-execute cycle

---

### 2. `mu_equal` - Fixed-Point Detection

**What it does:**
```python
def mu_equal(a: Mu, b: Mu) -> bool:
    """Structural equality via content hash."""
    return content_hash(a) == content_hash(b)
```

**Why irreducible:**
- Stall detection requires comparing "before" and "after"
- Comparison must be structural (not Python object identity)
- Hash computation touches every node - cannot be partial

**What it does NOT do:**
- No semantic interpretation of values
- No type-specific comparison logic
- No ordering or ranking

**Analogy:** Hardware comparator circuit

---

### 3. `max_steps` - Resource Exhaustion Guard

**What it does:**
```python
MAX_STEPS = 10000  # Configurable limit

def run_with_limit(projections, value, max_steps=MAX_STEPS):
    steps = 0
    while steps < max_steps:
        result = eval_step(projections, value)
        if mu_equal(result, value):
            return result  # stall
        value = result
        steps += 1
    return value  # resource exhaustion
```

**Why irreducible:**
- Termination guarantee - prevents infinite execution
- Cannot be structural (would require arithmetic on fuel)
- Linked-list fuel was REJECTED by 9-agent review (still needs counter)

**What it does NOT do:**
- No semantic decisions about "how much" work
- No prioritization or scheduling
- No interpretation of what "progress" means

**Analogy:** Watchdog timer / hardware interrupt

---

### 4. `stack_guard` - Overflow Protection

**What it does:**
```python
# In mu_type.py - depth validation during is_mu() checks
MAX_MU_DEPTH = 200  # Conservative limit below Python's ~1000 frame stack

def is_mu(value: Any, _seen: set | None = None, _depth: int = 0) -> bool:
    # Depth limit check (prevents RecursionError attacks)
    if _depth > MAX_MU_DEPTH:
        return False  # Reject structures deeper than limit
    # ... validation continues
```

**Implementation note:** Stack guard is implemented via `MAX_MU_DEPTH` validation in `is_mu()`, not as a separate function. This catches deep structures at the boundary BEFORE they can cause stack overflow during pattern matching or substitution.

**Why irreducible:**
- Python has finite stack (default 1000 frames)
- Deeply nested Mu structures can overflow during traversal
- Cannot be structural (stack is Python runtime, not Mu data)

**What it does NOT do:**
- No semantic decisions about nesting
- No modification of data
- No control flow beyond "reject if too deep"

**Analogy:** Memory protection / segfault handler

---

### 5. `projection_loader` - Seed Bootstrap

**What it does:**
```python
def load_verified_seed(path: Path) -> dict:
    """Load and validate a seed file."""
    with open(path) as f:
        seed = json.load(f)
    validate_schema(seed)  # Has id, projections list
    verify_checksum(seed)  # Integrity check
    return seed
```

**Why irreducible:**
- Projections must come from somewhere (seeds are JSON files)
- JSON parsing is Python's job (not expressible as projections)
- Schema validation ensures well-formed projections

**What it does NOT do:**
- No interpretation of projection semantics
- No ordering decisions (seed order is authoritative)
- No modification of loaded content

**Analogy:** ROM bootstrap / BIOS loading

---

## What These Primitives Enable

With only these five primitives, RCX can:

| Capability | How |
|------------|-----|
| **Pattern matching** | match.v2 projections (structural) |
| **Substitution** | subst.v2 projections (structural) |
| **Projection selection** | kernel.v1 projections (structural) |
| **Fixed-point iteration** | `eval_step` + `mu_equal` (primitives) |
| **Domain logic** | User projections (structural) |
| **EngineNews engine cycle** | stall/fix/promote as projections |

Everything in the left column is **structural**. The primitives just provide the execution substrate.

---

## What These Primitives Do NOT Provide

| Prohibited Operation | Why Prohibited | Alternative |
|---------------------|----------------|-------------|
| Semantic branching | Hides decisions in Python | Projection patterns |
| Arithmetic on data | Non-structural | Linked-list operations |
| String manipulation | Host smuggling | Structural keys only |
| Type-specific logic | Breaks uniformity | Classify projections |
| Control flow choices | Python artifact | State machine patterns |

If code needs any of these, it must be expressed as **projections**, not Python.

---

## The Honest Boundary

```
┌─────────────────────────────────────────────────────────────┐
│                    STRUCTURAL LAYER                         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  kernel.v1  │  │  match.v2   │  │  subst.v2   │         │
│  │ (selection) │  │ (matching)  │  │ (substitute)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  classify   │  │    eval     │  │   domain    │         │
│  │ projections │  │ projections │  │ projections │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  All MEANING lives here. Code = Data. Projections select   │
│  projections. This is where emergence happens.             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                    ══════════════════════
                      HONEST BOUNDARY
                    ══════════════════════
                              │
┌─────────────────────────────────────────────────────────────┐
│                   BOOTSTRAP PRIMITIVES                      │
│                                                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │ eval_step  │ │  mu_equal  │ │ max_steps  │              │
│  │ (execute)  │ │  (compare) │ │  (limit)   │              │
│  └────────────┘ └────────────┘ └────────────┘              │
│                                                             │
│  ┌────────────┐ ┌────────────┐                             │
│  │stack_guard │ │  loader    │                             │
│  │ (protect)  │ │ (bootstrap)│                             │
│  └────────────┘ └────────────┘                             │
│                                                             │
│  Minimal, mechanical, documented. No semantic decisions.   │
│  This is the "hardware" that runs the structural layer.    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Hidden/Implicit Primitives

The five named primitives depend on these Python capabilities that are baked into the host:

| Implicit Primitive | Used By | Why Irreducible |
|-------------------|---------|-----------------|
| **Python for-loop** | eval_step | Iteration over projection list |
| **json.dumps** | mu_equal, mu_hash | Canonical serialization for comparison |
| **hashlib.sha256** | mu_hash | Content hashing for equality |
| **NO_MATCH sentinel** | eval_step | Distinguish "no match" from "matched to None" |
| **Type validation (is_mu)** | All primitives | Reject non-Mu values at boundary |
| **File I/O** | projection_loader | Read seed JSON from disk |

**Why not count these separately?**
- They are implementation details OF the five primitives
- No RCX code interacts with them directly
- They don't make semantic decisions

The five named primitives form the API boundary. The implicit primitives are their implementation.

---

## EngineNews Compatibility

EngineNews (stall/fix/promote/closure) is **NOT** part of the bootstrap layer. It is a **PROGRAM** that runs ON TOP of the structural substrate.

| EngineNews Concept | RCX Implementation | Layer |
|--------------------|---------------------|-------|
| **Stall detection** (Ξ(O(G)) = Ξ(G)) | `mu_equal(before, after)` | Primitive |
| **Fix operation** (apply ω) | Domain projections | Structural |
| **Promote** (lift grounded values) | Kernel selection (kernel.v1) | Structural |
| **Closure** (Rule 2.2: τ recurs independently) | Trace accumulation (structural linked-list) | Structural |

**The primitives provide the execution substrate. EngineNews provides the engine semantics.**

### What EngineNews Requires From Primitives

1. **eval_step** - Apply projections (fix operations)
2. **mu_equal** - Detect stalls (fixed-point)
3. **max_steps** - Prevent runaway (resource guard)

EngineNews does NOT require direct access to stack_guard or projection_loader.

---

## Comparison to Other Self-Hosting Systems

| System | Bootstrap Primitive | Structural Layer | Status |
|--------|--------------------|--------------------|--------|
| **Forth** | NEXT (inner interpreter) | Threaded code words | Accepted |
| **Lisp** | eval/apply in C | S-expressions | Accepted |
| **PyPy** | CPython interpreter | RPython code | Accepted |
| **RCX** | eval_step + 4 others | Mu projections | **This doc** |

RCX's bootstrap is **comparable in minimality** to Forth's NEXT. Both provide:
- A way to apply the next operation (NEXT / eval_step)
- A way to detect termination (stack empty / mu_equal)
- Resource protection (return stack / max_steps + stack_guard)

---

## Verification Questions for Agents

1. **Verifier:** Do these five primitives violate any North Star invariants?

2. **Adversary:** Can any primitive be exploited to forge structural results?

3. **Expert:** Are these truly minimal? Can any be eliminated or simplified?

4. **Structural-proof:** Is everything ABOVE these primitives provably structural?

5. **Grounding:** What tests would verify these claims?

6. **Fuzzer:** What edge cases might break the boundary?

7. **Translator:** Does this explanation make sense to a non-technical founder?

8. **Visualizer:** Is the boundary diagram accurate?

9. **Advisor:** Is this the right framing for achieving the self-hosting goal?

---

## Implementation Status

| Primitive | Current Location | Status |
|-----------|------------------|--------|
| `eval_step` | `rcx_pi/selfhost/eval_seed.py:step()` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `mu_equal` | `rcx_pi/selfhost/mu_type.py:mu_equal()` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `max_steps` | `rcx_pi/selfhost/step_mu.py:241` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `stack_guard` | `rcx_pi/selfhost/mu_type.py:MAX_MU_DEPTH` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `projection_loader` | `rcx_pi/selfhost/seed_integrity.py` | MARKED - `# BOOTSTRAP_PRIMITIVE` |

---

## Success Criteria

- [x] All five primitives marked with `# BOOTSTRAP_PRIMITIVE` comment
- [x] Each primitive has docstring explaining why irreducible
- [ ] No other Python code makes semantic decisions (Phase 8b)
- [ ] 9-agent consensus that boundary is honest and minimal
- [ ] Grounding tests verify structural claims
- [ ] Documentation complete for external review

---

## Known Limitations

Per fuzzer agent analysis:

1. **Oscillation undetected** - Hash comparison catches A→A (stall) but not A→B→A (cycle). This is a design limitation, not a bug. Cycles hit max_steps.

2. **Deeply nested operations** - MAX_MU_DEPTH protects DATA depth. OPERATION depth (recursive match/subst) is protected by match_mu/subst_mu using structural stack-based traversal.

---

**Author:** Claude Code (Phase 8a)
**Date:** 2026-01-28
**Status:** IMPLEMENTATION - 9-agent review v2
