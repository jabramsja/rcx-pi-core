<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-09
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Bootstrap Primitives (Phase 8a)

**Status:** IMPLEMENTATION - 9-agent review v2
**Goal:** Define the minimal, irreducible Python substrate for honest self-hosting

---

## Executive Summary

RCX achieves self-hosting/meta-circularity with an explicit bootstrap boundary. This document defines the **four primitives** that Python must provide - everything above this layer is structural Mu projections. (Originally five; `mu_equal` was eliminated via Content-Addressed Mu Level 1 — see below.)

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
| **L1: Algorithmic** | match/subst as projections | DONE | eval_step + mu_hash_cached |
| **L2: Operational** | kernel loop as projections | FULL | All 4 primitives |
| **L3: Substrate Portability** | Same projections run on Python + JS | COMPLETE | All 4 primitives on both substrates |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated | SINK | Research question |

All three levels USE these primitives. The primitives enable self-hosting but don't guarantee it.

### Primitives vs. Debt vs. Scaffolding

| Category | Definition | Examples |
|----------|------------|----------|
| **Bootstrap Primitive** | Irreducible - cannot be expressed as projection | eval_step, max_steps, stack_guard, loader |
| **Scaffolding** | Temporary Python that COULD become structural | run_mu outer loop (L3 boundary) |
| **Debt** | Python making semantic decisions that SHOULD be projections | Unmarked semantic branching |

**Key distinction:** Primitives are NOT debt. They are the honest boundary where structure ends and hardware begins.

---

## The Four Bootstrap Primitives (+ 1 Eliminated)

### Taxonomy Overlay (Docs-Only Classification)

Each bootstrap primitive falls into one of these categories. This is a documentation-level taxonomy for precision; it does not change runtime markers or `@host_*` decorators.

| Primitive | Category | Why This Category |
|-----------|----------|-------------------|
| `eval_step` | **Execution primitive** | The irreducible "apply" step — like Forth's NEXT |
| `max_steps` | **Iteration / clock primitive** | Provides the termination clock — cannot be structural fuel |
| `stack_guard` | **Host resource limit** (host safety constraint) | Python stack is hardware, not Mu data; see note below |
| `projection_loader` | **I/O & trust primitive** | JSON parsing + integrity verification — file I/O is host-only |

**stack_guard note:** `stack_guard` is a bootstrap primitive (it must exist), but its nature is a **host safety constraint** — it protects against Python's finite call stack, which is a hardware limitation. Unlike `eval_step` (which embodies execution semantics), `stack_guard` embodies a physical resource boundary. It remains in the bootstrap set because removing it would allow crash-by-depth attacks.

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

**Non-linear Pattern Support (binding conflict detection):**
- When a variable like `{"var": "x"}` appears twice in a pattern, both occurrences must bind to equal values
- eval_seed.match() implements this via binding conflict detection in `_match_inner()`
- If `x` is already bound to `A`, and the pattern tries to bind `x` to `B`, match FAILS
- This is how `recurrence.found_in_seen` detects state equality structurally
- Both Python and JS substrates handle binding conflicts identically

**Analogy:** CPU instruction fetch-decode-execute cycle

---

### ~~2. `mu_equal` - Fixed-Point Detection~~ (DEMOTED)

**Status:** DEMOTED from bootstrap primitive (Content-Addressed Mu Level 1, 2026-02-10).

`mu_equal` is now derivable from `mu_hash_cached`: `mu_equal(a, b) ≡ mu_hash_cached(a) == mu_hash_cached(b)`. Production code uses `mu_hash_cached` directly for stall detection and binding conflict. The `mu_equal` function remains as a convenience wrapper (~30 test call sites + JS parity `muEqual()`).

**How it was demoted:** Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) Level 1: hash-identity at construction. All 8 production call sites replaced with `mu_hash_cached()` comparisons. Bootstrap primitives reduced from 5 to 4.

**Historical role:** Stall detection (comparing "before" and "after" structurally).

---

### 2. `max_steps` - Resource Exhaustion Guard

**What it does:**
```python
MAX_STEPS = 10000  # Configurable limit

def run_with_limit(projections, value, max_steps=MAX_STEPS):
    steps = 0
    while steps < max_steps:
        result = eval_step(projections, value)
        if mu_hash_cached(result) == mu_hash_cached(value):
            return result  # stall (hash comparison)
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

### 3. `stack_guard` - Overflow Protection

**What it does:**
```python
# In mu_type.py - depth validation during is_mu() checks
MAX_MU_DEPTH = 300  # Conservative limit below Python's ~1000 frame stack

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

### 4. `projection_loader` - Seed Bootstrap

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

With only these four primitives, RCX can:

| Capability | How |
|------------|-----|
| **Pattern matching** | match.v2 projections (structural); match.v2 + bridge for non-linear via match_mu |
| **Substitution** | subst.v2 projections (structural) |
| **Projection selection** | kernel.v1 projections (structural) |
| **Fixed-point iteration** | `eval_step` + `mu_hash_cached` (hash comparison) |
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
│  │ eval_step  │ │ max_steps  │ │stack_guard │              │
│  │ (execute)  │ │  (limit)   │ │ (protect)  │              │
│  └────────────┘ └────────────┘ └────────────┘              │
│                                                             │
│  ┌────────────┐                                            │
│  │  loader    │  (mu_equal DEMOTED — now derived from      │
│  │ (bootstrap)│   mu_hash_cached, Content-Addressed Mu L1) │
│  └────────────┘                                            │
│                                                             │
│  Minimal, mechanical, documented. No semantic decisions.   │
│  This is the "hardware" that runs the structural layer.    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Hidden/Implicit Primitives

The four named primitives depend on these Python capabilities that are baked into the host:

| Implicit Primitive | Used By | Why Irreducible |
|-------------------|---------|-----------------|
| **Python for-loop** | eval_step | Iteration over projection list |
| **json.dumps** | mu_hash_cached, mu_hash | Canonical serialization for comparison |
| **hashlib.sha256** | mu_hash | Content hashing for equality |
| **NO_MATCH sentinel** | eval_step | Distinguish "no match" from "matched to None" |
| **Type validation (is_mu)** | All primitives | Reject non-Mu values at boundary |
| **File I/O** | projection_loader | Read seed JSON from disk |

**Why not count these separately?**
- They are implementation details OF the four primitives
- No RCX code interacts with them directly
- They don't make semantic decisions

The four named primitives form the API boundary. The implicit primitives are their implementation.

---

## Recurrence Compatibility

EngineNews (stall/fix/promote/closure) is **NOT** part of the bootstrap layer. It is a **PROGRAM** that runs ON TOP of the structural substrate.

| EngineNews Concept | RCX Implementation | Layer |
|--------------------|---------------------|-------|
| **Stall detection** (Ξ(O(G)) = Ξ(G)) | `mu_hash_cached(before) == mu_hash_cached(after)` | Boundary (derived) |
| **Fix operation** (apply ω) | Domain projections | Structural |
| **Promote** (lift grounded values) | Kernel selection (kernel.v1) | Structural |
| **Closure** (Rule 2.2: τ recurs independently) | Trace accumulation (structural linked-list) | Structural |

**The primitives provide the execution substrate. EngineNews provides the engine semantics.**

### What EngineNews Requires From Primitives

1. **eval_step** - Apply projections (fix operations)
2. **mu_hash_cached** - Detect stalls (hash comparison, derived from boundary hashing)
3. **max_steps** - Prevent runaway (resource guard)

EngineNews does NOT require direct access to stack_guard or projection_loader.

---

## Comparison to Other Self-Hosting Systems

| System | Bootstrap Primitive | Structural Layer | Status |
|--------|--------------------|--------------------|--------|
| **Forth** | NEXT (inner interpreter) | Threaded code words | Accepted |
| **Lisp** | eval/apply in C | S-expressions | Accepted |
| **PyPy** | CPython interpreter | RPython code | Accepted |
| **RCX** | eval_step + 3 others | Mu projections | **This doc** |

RCX's bootstrap is **comparable in minimality** to Forth's NEXT. Both provide:
- A way to apply the next operation (NEXT / eval_step)
- A way to detect termination (stack empty / mu_hash_cached)
- Resource protection (return stack / max_steps + stack_guard)

---

## L3 Substrate Portability: JavaScript POC

**Location:** `mu/host/js/` (15 modules; ~4800 LOC core + ~480 LOC inline tests; `eval_step.js` is a compatibility shim that delegates to `cli/main.js`)

**What it proves:** The same projections (kernel.v1.json, match.v2.json, subst.v2.json, recurrence.v1.json, exhaustion.v1.json, hemispheres.v1.json) run identically on JavaScript. This demonstrates that all meaning is in the projections, not the host language.

| Primitive | Python Implementation | JavaScript Implementation |
|-----------|----------------------|---------------------------|
| eval_step | `eval_seed.py:step()` | `bootstrap_core.js:step()` |
| mu_hash_cached | `mu_type.py:mu_hash_cached()` | `types.js:muHashCached()` |
| max_steps | `step_mu.py:max_steps` | `constants.js:MAX_STEPS` |
| stack_guard | `mu_type.py:MAX_MU_DEPTH` | `constants.js:MAX_DEPTH` |
| projection_loader | `seed_integrity.py` | `seed_loader.js:loadSeed()` |

**Security hardening (completed 2026-01-30, updated 2026-02-02):**
- [x] `KERNEL_RESERVED_FIELDS` validation (25 fields: 12 base + 3 Engine/Boot1 + 3 Recurrence + 3 Exhaustion + 4 Bridge)
- [x] `validate_type_tag()` - whitelist enforcement
- [x] Dict kv-pair normalization parity fix
- Deferred: Lambda calculus guard (future; not critical for L3)

**Cross-substrate parity tests (completed 2026-01-30):**
- `tests/parity/test_parity_python.py` - 20 parity + 3 security vectors
- `tests/engine/test_structural_trace.py` - 14 trace model tests
- `tests/fixtures/parity_vectors.json` - shared test vectors (23 total)

**Role clarification:**
- **Python:** Primary development substrate (comprehensive test coverage, agent-reviewed - see STATUS.md)
- **JavaScript:** Portability proof (all parity tests pass)

---

## Verification Questions for Agents

1. **Verifier:** Do these four primitives violate any North Star invariants?

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
| `mu_equal` | `rcx_pi/selfhost/mu_type.py:mu_equal()` | DEMOTED - `# DEMOTED PRIMITIVE` (convenience wrapper around mu_hash_cached, ~30 test sites) |
| `max_steps` | `rcx_pi/selfhost/step_mu.py:step_kernel_mu()` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `stack_guard` | `rcx_pi/selfhost/mu_type.py:MAX_MU_DEPTH` | MARKED - `# BOOTSTRAP_PRIMITIVE` |
| `projection_loader` | `rcx_pi/selfhost/seed_integrity.py` | MARKED - `# BOOTSTRAP_PRIMITIVE` |

---

## Success Criteria

- Completed: All four active primitives marked with `# BOOTSTRAP_PRIMITIVE` comment (mu_equal eliminated)
- Completed: Each primitive has docstring explaining why irreducible
- Open external-review targets:
  1. No other Python code makes semantic decisions (Phase 8b)
  2. 9-agent consensus that boundary is honest and minimal
  3. Grounding tests verify structural claims
  4. Documentation complete for external review

---

## Known Limitations

Per fuzzer agent analysis:

1. **Oscillation undetected** - Hash comparison catches A→A (stall) but not A→B→A (cycle). This is a design limitation, not a bug. Cycles hit max_steps.

2. **Deeply nested operations** - MAX_MU_DEPTH protects DATA depth. OPERATION depth (recursive match/subst) is protected by match_mu/subst_mu using structural stack-based traversal.

---

## Boundary Scaffolding (Precision Note)

The `while` loops in `match_mu.py` (normalize_for_match, denormalize_from_match, bindings_to_dict) are **API/UX adapter scaffolding** — they convert between Python types and Mu linked-list format at the boundary. They are not bootstrap primitives and not semantic debt.

However, normalization is not fully outside `step_kernel_mu` today: the kernel bridge path calls `normalize_projection` on each projection before structural dispatch. This normalization step is host scaffolding that remains part of the execution path. It is documented, marked `AST_OK:infra`, and capped by the scaffolding ceiling (48). It is NOT claimed to be structural.

---

## Boot1 Recursion Framing (Precision Note)

`_run_engine_recursive()` (Python) and `runEnginePipelineRecursive()` (JS) provide an alternative engine loop that uses host call-stack recursion instead of the trampoline's iterative for-loop.

**What Boot1 recursive is:** A host-call-stack-dependent shadow path. The loop-back decision is structural (projections produce `{_run_engine: ...}` envelopes); the loop-back execution is host recursion.

**What Boot1 recursive is NOT:** A structural CPS proof. It does not eliminate the host iteration primitive — it replaces one host loop mechanism (for-loop) with another (call stack). Both remain host code.

**Default:** Boot1 recursive (`_run_engine_recursive`) is the production default (`use_boot1_recursive=True` at step_mu.py:run_engine_pipeline()). Trampoline is fallback via `use_boot1_recursive=False` / `boot1LoopMode` JSON API. Note: Boot1 is NOT meta-circular progress — it changes host execution strategy only.

---

**Author:** Claude Code (Phase 8a)
**Date:** 2026-01-28
**Status:** IMPLEMENTATION - 9-agent review v2
