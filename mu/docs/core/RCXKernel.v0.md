<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-03
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

# RCX Kernel Specification v0

Status: IMPLEMENTED (mu/substrate/kernel.v1.json, 7 projections)

## Purpose

Define the minimal RCX kernel - the immutable substrate upon which different "overlays" (rule configurations) can run. The kernel is like hardware/BIOS: it never changes. Seeds provide the "software" that configures behavior.

This document defines WHAT the kernel does, not HOW it does it. Implementation follows after spec approval.

## Design Principles

1. **Everything is Structure**: No strings, no symbols, only μ (Mu/motif/graph)
2. **No Arbitrary Limits**: Detection emerges from structural properties
3. **Patterns Over Halting**: Multiple meaningful types of non-termination (Ω-classes)
4. **Traces are Values**: Computation history is first-class data
5. **Kernel = Hardware**: Immutable, minimal, dumb
6. **Seeds = Software**: Configurable rules, handlers, behavior
7. **Self-Hosting Required**: RCX must run RCX to prove emergence (not simulate it)

## Why Self-Hosting Matters

If Python runs RCX, any "emergence" might be a Python artifact. For the theory to hold:
- RCX must evaluate RCX
- The evaluator (EVAL_SEED) is itself structure (Mu)
- What emerges comes from structure alone, not host language semantics

This is the difference between simulating physics and being physics.

## Core Concepts

### Mu (μ)

The universal data type. A Mu is:
- A JSON-compatible value (see `mu/docs/core/MuType.v0.md`)
- Equivalently: a tree/DAG structure serialized as JSON
- Equivalently: a "motif" - a pattern that can be matched and transformed

All three views (Mu, graph, motif) are the same thing at different abstraction levels.

```
Mu = None | bool | int | float | str | List[Mu] | Dict[str, Mu]
```

### Projection (→)

A projection transforms one Mu into another:

```
Projection = {
    "pattern": Mu,   -- What to match
    "body": Mu       -- What to produce
}
```

A projection is itself a Mu (data = code).

### Activation (*)

Apply a projection to a Mu:

```
activate(projection, mu) → Mu | None
```

Returns the transformed Mu if pattern matches, None if no match.

### Identity Hash (Ξ)

A deterministic hash of any Mu:

```
identity(mu) → str  (SHA-256 of canonical JSON)
```

The kernel knows when structure changes by comparing identity hashes.

### Trace (τ)

A history of transformations:

```
Trace = List[TraceEntry]

TraceEntry = {
    "before_hash": str,
    "after_hash": str,
    "projection_id": str,
    "timestamp": int  -- logical clock, not wall time
}
```

Traces are Mu (history is data).

### Stall

A stall occurs when:
1. A projection was attempted
2. The identity hash did NOT change (Ξ_before == Ξ_after)
3. The structure is unchanged

```
stall(before, after, projection) := identity(before) == identity(after)
```

## Kernel Primitives

The kernel provides exactly these operations:

| Primitive | Signature | Purpose |
|-----------|-----------|---------|
| `compute_identity` | `(mu: Mu) → str` | Compute Ξ hash |
| `detect_stall` | `(before: str, after: str) → bool` | Check if Ξ unchanged |
| `record_trace` | `(entry: TraceEntry) → None` | Append to trace history |
| `gate_dispatch` | `(event: str, context: Mu) → Mu` | Call seed-provided handler |
| `get_trace` | `() → Trace` | Return current trace |

**NOT a kernel primitive:**
- `apply_projection` - This is SEED responsibility, not kernel

Note: Memory management (get_mem, copy_mem) is handled by the host language (Python). The kernel doesn't expose raw memory operations.

**See `mu/docs/core/BootstrapPrimitives.v0.md`** for the canonical list of 4 irreducible bootstrap primitives (eval_step, max_steps, stack_guard, projection_loader). mu_equal was eliminated via Level 1 Content-Addressed Mu (2026-02-10).

## Why apply_projection is NOT in the Kernel

Different seeds may have different matching semantics:
- **Seed A**: Pure structural equality (pattern must exactly equal input)
- **Seed B**: Variable binding (`{"var": "x"}` matches anything)
- **Seed C**: Unification (bidirectional matching)
- **Seed D**: Something we haven't imagined

The kernel doesn't choose. Seeds choose. This keeps the kernel maximally general.

## Gate Interface

Seeds register handlers for events. The kernel calls these handlers via `gate_dispatch`.

### Events

| Event | When | Context Provided |
|-------|------|------------------|
| `"stall"` | Stall detected | `{mu, projection_id, trace}` |
| `"pattern"` | Trace pattern detected | `{pattern, trace}` |
| `"step"` | Normal execution step | `{mu}` |
| `"init"` | Kernel startup | `{config}` |

### Gate Table

```python
GateTable = Dict[str, Callable[[Mu], Mu]]

# Example:
{
    "stall": handle_stall,      # Seed provides
    "pattern": handle_pattern,  # Seed provides
    "step": handle_step,        # Seed provides
    "init": handle_init,        # Seed provides
}
```

Seeds are responsible for defining what happens at each event.

## Seed Hierarchy

Seeds form a hierarchy:

```
EVAL_SEED (hard, written once)
    ↓ runs
Application Seeds (easier, define domain projections)
    ↓ e.g.
EngineeNews, Wolfram-style, Cyclic, etc.
```

### EVAL_SEED (The Foundation)

The first seed. Defines how to match, apply, dispatch. Written once.

```
EVAL_SEED := [
    # Structural equality check
    μ(EQUAL?, a, a) → μ(TRUE)
    μ(EQUAL?, a, b) → μ(FALSE)  # when a ≠ b

    # Apply projection (pure structural)
    μ(APPLY, pattern, body, input) →
        μ(IF, μ(EQUAL?, pattern, input), body, μ(NO_MATCH))

    # Gate dispatch
    μ(DISPATCH, event, handlers) → μ(LOOKUP, event, handlers)

    # ... more primitives ...
]
```

This is Mu. The evaluator is structure evaluating structure.

### Application Seeds

Run on top of EVAL_SEED. Just define projections:

```json
{
    "seed": {
        "id": "enginenews.v1",
        "projections": [
            {"id": "add.zero", "pattern": {...}, "body": {...}},
            {"id": "mul.one", "pattern": {...}, "body": {...}}
        ],
        "config": {
            "closure_threshold": 2,
            "acyclic_only": true
        }
    }
}
```

Application seeds are easier because EVAL_SEED does the hard work.

## Bootstrap Sequence

1. **Python provides kernel** (minimal, ~200 lines of plumbing)
2. **Python provides EVAL_SEED** (initially as Python code, then as Mu)
3. **EVAL_SEED runs application seeds** (EngineeNews, etc.)
4. **EVAL_SEED runs a copy of itself** ← self-hosting achieved
5. **Emergence proven** - structure running structure, no host contamination

Python is only the spark. Once step 4 works, RCX runs RCX.

## Main Loop

```
LOOP:
    1. current_hash = compute_identity(mu)

    2. result = gate_dispatch("step", {mu, current_hash})
       -- Seed does EVERYTHING: selects projection, applies it, returns result
       -- Kernel doesn't know how matching works

    3. new_hash = compute_identity(result)

    4. record_trace({
           before_hash: current_hash,
           after_hash: new_hash
       })

    5. IF detect_stall(current_hash, new_hash):
           mu = gate_dispatch("stall", {mu, trace})
           -- Seed handles stall
       ELSE:
           mu = result

    6. GOTO LOOP
```

The kernel is maximally dumb:
- Computes hashes
- Detects stalls (hash unchanged)
- Records trace
- Calls seed handlers

Everything else (projection selection, pattern matching, application) is seed responsibility.

## Ω-Classes (Recursive Behavior Types)

Different types of non-termination, detected by trace analysis:

| Class | Name | Detection | Meaning |
|-------|------|-----------|---------|
| Ω² | Fixpoint | `Ξ(μ) == Ξ(μ')` | Stable state reached |
| Ω⁰ | Flip Loop | `trace[n] == trace[n-2]` | Oscillation between 2 states |
| Ω¹ | Self-Inverse | `f(f(x)) == x` | Operation undoes itself |
| Ω³ | Paradox | `trace[n] == NOT(trace[n-1])` | Self-contradiction |
| Ω⁴ | Unbounded Drift | `|trace| > limit && !pattern` | Growing without structure |
| Ω^∞ | Collapse | Identity becomes degenerate | Information loss |
| Ω^5* | Convergent | `distance(μ_n, μ_{n+1}) → 0` | Approaching fixpoint |

Seeds can define handlers for each Ω-class.

## What the Kernel Does NOT Do

1. **Does not decide which projection to apply** - seed does via `step` handler
2. **Does not interpret stalls** - seed handles via `stall` handler
3. **Does not define closure rules** - seed configures
4. **Does not limit trace length** - seed configures
5. **Does not know about operators (Δ, P, etc.)** - these are projections defined by seeds

The kernel is maximally general. Specific behaviors (EngineeNews, Wolfram-style, etc.) are overlays provided by seeds.

## Relationship to Existing Code

**Note:** See STATUS.md for current phase (L1/L2/L3 complete).

| Component | Role | Status |
|-----------|------|--------|
| `rcx_pi/selfhost/mu_type.py` | Implements Mu validation | Active |
| `mu/substrate/kernel.v1.json` | Structural kernel (7 Mu projections) | **Canonical kernel** |
| `mu/substrate/match.v2.json` | Pattern matching (8 projections) | Active |
| `mu/substrate/subst.v2.json` | Substitution (12 projections) | Active |
| `mu/closures/recurrence.v1.json` | Closure detection (9 projections) | Active |
| `mu/closures/exhaustion.v1.json` | Exhaustion handling (11 projections) | Active |
| `rcx_pi/selfhost/step_mu.py` | step_kernel_mu() orchestrates projections | Active |
| `rcx_pi/selfhost/eval_seed.py` | Bootstrap match/substitute (5 primitives) | Active |
| `mu/host/js/eval_step.js` | JavaScript substrate (L3 parity) | Active |

## Implementation Order

### Phase 1: Minimal Kernel (Python)
1. `compute_identity(mu)` - SHA-256 of canonical JSON
2. `detect_stall(before, after)` - Compare hashes
3. `record_trace(entry)` - Append to list
4. `gate_dispatch(event, context)` - Call registered handler
5. Main loop - Tie primitives together

### Phase 2: EVAL_SEED (Python first, then Mu)
1. Write EVAL_SEED logic in Python (understand what's needed)
2. Translate to Mu (projections as data)
3. Verify Python-EVAL and Mu-EVAL produce same results

### Phase 3: Self-Hosting
1. Mu-EVAL runs Mu-EVAL
2. Compare traces: Python→EVAL vs EVAL→EVAL
3. If identical, self-hosting achieved

### Phase 4: Application Seeds
1. EngineeNews as first real seed
2. Run on self-hosted EVAL
3. Verify expected behavior

Each step gets tests. Failure at any step → stop, understand, adjust.

## Test Strategy

### Phase 1 Tests (Kernel Primitives)
- `test_compute_identity_deterministic` - Same Mu → same hash
- `test_compute_identity_different` - Different Mu → different hash
- `test_detect_stall_true` - Same hash → stall
- `test_detect_stall_false` - Different hash → no stall
- `test_record_trace_appends` - Trace grows
- `test_gate_dispatch_calls_handler` - Handler receives context

### Phase 2 Tests (EVAL_SEED)
- `test_eval_structural_equality` - μ(a) equals μ(a)
- `test_eval_apply_match` - Pattern matches, body returned
- `test_eval_apply_no_match` - Pattern doesn't match
- `test_eval_dispatch` - Event routes to handler

### Phase 3 Tests (Self-Hosting)
- `test_python_eval_equals_mu_eval` - Same input → same output
- `test_eval_runs_eval` - EVAL_SEED evaluates EVAL_SEED
- `test_trace_equivalence` - Python and self-hosted traces match

### Phase 4 Tests (Recurrence)
- `test_recurrence_basic_reduction`
- `test_recurrence_stall_detection`
- `test_recurrence_closure_formation`

## Open Questions

1. **Can we write EVAL_SEED?** - This is THE question. If yes, everything else follows. If no, we learn why and adjust.

2. **EVAL_SEED complexity**: How many projections does EVAL_SEED need? 10? 100? 1000?

3. **Termination**: How does the kernel know when to stop? Seed signals via special Mu? Max iterations? Both?

4. **Trace pattern detection**: Is this kernel or seed responsibility? Leaning toward seed.

5. **Bootstrap validation**: How do we verify that EVAL_SEED running EVAL_SEED produces identical behavior to Python running EVAL_SEED?

## Historical Promotion Notes (VECTOR → NEXT Draft)

- Decided: Kernel has 4 primitives (identity, stall, trace, dispatch).
- Decided: `apply_projection` is seed responsibility, not kernel.
- Decided: Self-hosting is required to prove emergence.
- Historical gating question (resolved in later phases): write EVAL_SEED in Python to understand complexity.
- Historical gating question (resolved in later phases): verify EVAL_SEED tractability.

## Historical Next Steps (Draft-Era)

1. ~~Review spec with user~~ ✓ (this conversation)
2. Implement Phase 1: Minimal kernel in Python
3. Attempt Phase 2: EVAL_SEED (Python first)
4. Learn: Is EVAL_SEED tractable? If not, why?
5. Adjust based on what we learn

## References

- `mu/docs/core/MuType.v0.md` - Mu type definition
- `mu/docs/core/BootstrapPrimitives.v0.md` - 4 irreducible bootstrap primitives (mu_equal eliminated)
- `mu/docs/core/MetaCircularKernel.v0.md` - Kernel state machine design
- `mu/docs/core/EngineNewsStructural.v0.md` - Recurrence closure detection
- `RCXEngineNew.pdf` - Recurrence formal specification (canonical reference)
