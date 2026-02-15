# Kernel/Seed Realignment Plan v0

**Status:** WITHDRAWN (2026-01-28)

---

## Withdrawal Notice

This plan was **withdrawn after 4-agent review** (verifier, adversary, expert, structural-proof).

### Why It Was Withdrawn

The plan was based on a fundamental misunderstanding about two concepts that share the word "kernel":

| Term | What It Actually Is | Role |
|------|---------------------|------|
| **kernel.v1.json** | 7 Mu projections for structural iteration | THE structural kernel |
| **Kernel class** | Python hash/trace/dispatch infrastructure | Scaffolding |

**The misunderstanding:** The plan assumed the `Kernel` class was "the kernel" being bypassed, when in reality `kernel.v1.json` IS the structural kernel, and Phase 7d-1 correctly uses it.

**The consequence:** Implementing this plan would have REMOVED structural iteration (kernel.v1.json) and replaced it with Python for-loops - an architectural regression.

### Agent Verdicts

- **Verifier:** REJECT - "Plan proposes REVERSING Phase 7d-1 structural achievement"
- **Adversary:** NEEDS HARDENING - Found 6 vulnerabilities in proposed implementation
- **Expert:** REJECT - "Current implementation is CORRECT. kernel.v1.json IS the structural kernel"
- **Structural-proof:** MIXED - L1 proven complete, but plan's L2 claims unproven

### What We Learned

1. `kernel.v1.json` = structural kernel (linked-list cursor, no arithmetic)
2. `Kernel` class = Python scaffolding (hash, trace, dispatch)
3. Phase 7d-1 correctly uses the structural kernel
4. The "bypass" was not architectural divergence - it was correct design
5. Phase 8 (recursive kernel projections) remains the path to L2 FULL

### Valid Insight Preserved

One idea from this plan was worth preserving: **projection caching** for performance. Added to SINK for post-Phase 8 consideration (with corrected implementation - use content hash, not id()).

---

## Original Plan (For Historical Reference)

**Original Goal:** Realign step_mu to use the kernel/seed architecture as originally designed

---

## Problem Statement

The kernel/seed architecture was designed but not followed in implementation:

**Designed (per RCXKernel.v0.md, EVAL_SEED.v0.md):**
```
kernel.run(input)
  → kernel.step()
    → gate_dispatch("step", context)
      → [seed's step_handler]
        → step(projections, mu)
```

**Implemented (step_mu.py):**
```
step_mu(input)
  → step_kernel_mu(input)
    → [own for-loop, bypassing kernel entirely]
```

This divergence means:
- The `Kernel` class is largely unused
- `register_eval_seed()` is never called
- `gate_dispatch` is bypassed
- We have parallel loops instead of one controlled loop

---

## Design Principles (From Documentation)

### From RCXKernel.v0.md:
> "The kernel is maximally dumb: Computes hashes, detects stalls, records trace, calls seed handlers. Everything else is seed responsibility."

### From EVAL_SEED.v0.md:
> "EVAL_SEED provides handlers for kernel events: step_handler, stall_handler, init_handler"

### From RCX-π Technical Master Guide:
> "The substrate doesn't interpret your logic — it mechanically applies operations"

The kernel IS the substrate. Seeds ARE the structure. This is the correct separation.

---

## Realignment Plan

### Phase R1: Create Structural EVAL_SEED

Create a new seed configuration that uses match_mu + subst_mu:

```python
# rcx_pi/selfhost/eval_seed_structural.py

def create_structural_step_handler(projections: list[Mu]):
    """
    Create step handler using structural match_mu + subst_mu.

    This replaces the Python-based step() with Mu projections.
    """
    def step_handler(context: Mu) -> Mu:
        assert_mu(context, "step_handler.context")
        mu = context["mu"]

        # Use structural apply (match_mu + subst_mu)
        for proj in projections:
            result = apply_mu(proj, mu)
            if result is not NO_MATCH:
                return result
        return mu  # stall

    return step_handler


def create_structural_eval_seed(projections: list[Mu]) -> dict:
    """Create EVAL_SEED with structural match/subst."""
    return {
        "step": create_structural_step_handler(projections),
        "stall": create_stall_handler(),
        "init": create_init_handler(),
    }


def register_structural_eval_seed(kernel, projections: list[Mu]) -> None:
    """Register structural EVAL_SEED with kernel."""
    handlers = create_structural_eval_seed(projections)
    for event, handler in handlers.items():
        kernel.register_handler(event, handler)
```

**Key insight:** The for-loop in step_handler is acceptable because it's INSIDE the seed, not the kernel. The kernel just dispatches; the seed decides how to try projections.

### Phase R2: Wire step_mu Through Kernel

Modify `step_mu()` to use the kernel:

```python
# rcx_pi/selfhost/step_mu.py

from .kernel import Kernel
from .eval_seed_structural import register_structural_eval_seed

def step_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try projections using kernel/seed architecture.

    This wires through the kernel's gate_dispatch mechanism
    as originally designed.
    """
    kernel = Kernel()
    register_structural_eval_seed(kernel, projections)

    # Single step through kernel
    result, is_stall = kernel.step(input_value)
    return result


def run_mu(projections: list[Mu], initial: Mu, max_steps: int = 1000):
    """
    Run projections using kernel/seed architecture.

    Uses kernel.run() as the ONE loop.
    """
    kernel = Kernel()
    register_structural_eval_seed(kernel, projections)

    return kernel.run(initial, max_steps=max_steps)
```

**Key changes:**
- `step_mu` creates kernel, registers seed, calls `kernel.step()`
- `run_mu` uses `kernel.run()` as the loop
- No more parallel loops in step_mu.py

### Phase R3: Kernel Caching (Performance)

Creating a new Kernel instance per call is inefficient. Add caching:

```python
# Module-level cache
_kernel_cache: dict[int, Kernel] = {}

def get_kernel_for_projections(projections: list[Mu]) -> Kernel:
    """Get or create cached kernel for projection set."""
    # Use id of projection list as cache key
    key = id(tuple(projections))
    if key not in _kernel_cache:
        kernel = Kernel()
        register_structural_eval_seed(kernel, projections)
        _kernel_cache[key] = kernel
    return _kernel_cache[key]
```

### Phase R4: Remove Bypassing Code

Once realigned, remove:
- `step_kernel_mu()` function
- `load_combined_kernel_projections()` (kernel projections become seed config)
- Direct `eval_step()` calls from step_mu.py

### Phase R5: Update Debt Markers

The `@host_iteration` marker moves:
- **Remove from:** `step_kernel_mu()` (deleted)
- **Keep on:** `kernel.run()` (the ONE loop, substrate-level)
- **Remove from:** `run_mu()` (now just calls kernel.run())

Debt change: The iteration is now in ONE place (kernel.run), not scattered.

---

## File Changes Summary

| File | Change |
|------|--------|
| `rcx_pi/selfhost/eval_seed_structural.py` | NEW - structural seed handlers |
| `rcx_pi/selfhost/step_mu.py` | MODIFY - wire through kernel |
| `rcx_pi/selfhost/kernel.py` | UNCHANGED - already correct |
| `rcx_pi/selfhost/eval_seed.py` | UNCHANGED - keep Python version |

---

## Architectural Clarification

### Q: Where is the iteration?

**Answer:** In `kernel.run()` only.

```
kernel.run()           ← ONE Python loop (substrate)
  → kernel.step()
    → gate_dispatch("step")
      → seed.step_handler()
        → for proj in projections:  ← Seed-level iteration (structural selection)
            apply_mu(proj, mu)
              → match_mu()          ← Structural (Mu projections)
              → subst_mu()          ← Structural (Mu projections)
```

The seed's for-loop is acceptable because:
1. It's selection logic, not execution
2. It's encapsulated in the seed (configurable)
3. The kernel doesn't know about it (stays dumb)

### Q: What about kernel.v1.json projections?

The kernel projections (kernel.wrap, kernel.try, etc.) were designed to make projection SELECTION structural. But with the kernel/seed architecture:

- **Kernel** provides the execution loop (substrate)
- **Seed** provides selection logic (currently Python for-loop)
- **Projections** (match.v2, subst.v2) are structural

The kernel.v1.json projections become OPTIONAL - they're a way to make selection structural too, but the architecture works without them.

**Future (L3):** Replace seed's for-loop with kernel.v1 projections for fully structural selection.

### Q: What is "L2 Complete"?

With this realignment:
- **L1 (Algorithms):** match_mu, subst_mu are structural ✓
- **L2 (Operations):** Kernel/seed architecture with one loop ✓
- **L3 (Full Bootstrap):** Eliminate kernel.run() loop (future)

L2 is achieved when the architecture matches the design and there's ONE controlled loop.

---

## Testing Strategy

### Parity Tests
- `step_mu(projs, input)` produces same results as before
- `run_mu(projs, input)` produces same results as before
- All existing 1300+ tests pass

### Architecture Tests
- Verify kernel.step() is called (not bypassed)
- Verify gate_dispatch("step") routes to handler
- Verify seed handler uses match_mu + subst_mu

### Performance Tests
- Kernel caching works (no regression)
- Benchmark against old implementation

---

## Success Criteria

1. [ ] `step_mu` calls `kernel.step()` (not its own loop)
2. [ ] `run_mu` calls `kernel.run()` (not its own loop)
3. [ ] Seed handlers use `match_mu` + `subst_mu`
4. [ ] All 1300+ tests pass
5. [ ] `@host_iteration` only on `kernel.run()`
6. [ ] `step_kernel_mu()` removed (no parallel loop)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Parity regression | Medium | High | Extensive parity tests |
| Performance regression | Low | Medium | Kernel caching |
| Circular imports | Low | Medium | Careful module structure |
| Test failures | Medium | Medium | Incremental changes |

---

## Relationship to Phase 8

This realignment REPLACES the Phase 8 "fuel-based recursive kernel" design:

| Phase 8 (Old) | Realignment (New) |
|---------------|-------------------|
| Add fuel mechanism | Use existing kernel |
| Eliminate Python loop | Accept kernel.run() as substrate |
| Complex state machine | Clean kernel/seed separation |
| Zero debt reduction | Architectural clarity |

The fuel design was solving the wrong problem. The real issue was architectural divergence, not missing mechanisms.

---

## Implementation Order

1. **R1:** Create `eval_seed_structural.py` with structural handlers
2. **R2:** Modify `step_mu()` to use kernel
3. **R3:** Add kernel caching for performance
4. **R4:** Remove bypassing code (`step_kernel_mu`, etc.)
5. **R5:** Update debt markers
6. **R6:** Run full test suite
7. **R7:** Update STATUS.md and docs

---

**Author:** Claude Code
**Date:** 2026-01-28
**Status:** WITHDRAWN after agent review
