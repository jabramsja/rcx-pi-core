# Recursive Kernel Design (Phase 8)

**Status:** DESIGN - NEEDS REVISION (agent review 2026-01-28)
**Goal:** Eliminate Python execution loop from `step_kernel_mu()` to achieve true L2

---

## Agent Review Summary (2026-01-28)

6-agent review identified issues with the fuel-based approach:

- **Verifier:** Fuel mechanism doesn't actually eliminate Python loop - it moves it
- **Adversary:** Security concerns with fuel forgery, continuation hijacking
- **Expert:** Over-engineered; current L2 PARTIAL may be acceptable boundary
- **Structural-proof:** Fuel IS structural, but "single eval_step call" claim is misleading

**Key insight:** `eval_step()` only applies ONE projection per call. Someone must iterate.

**Status:** This design needs revision. The goal (eliminate execution loop) is correct, but the fuel-based approach doesn't achieve it. Alternative approaches to consider:
1. Trampoline with explicit thunk queue
2. Compile projections to bytecode (∇R/Δ/Fix rules)
3. Accept execution loop as L2/L3 boundary (current state = L2 DONE by revised definition)

**See also:** `docs/archive/withdrawn/KernelSeedRealignment.v0.md` for related investigation.

---

## Problem Statement

Phase 7d-1 achieved "L2 PARTIAL":
- **Projection SELECTION** is structural (linked-list cursor in kernel.v1)
- **Projection EXECUTION** is still Python (for-loop in `step_kernel_mu`)

The Python execution loop at `step_mu.py:234-268`:
```python
for _ in range(max_steps):
    result = eval_step(kernel_projs, current)
    # ... check for done/stall ...
    current = result
```

This loop must become structural for true L2.

---

## Design Question

**How do kernel projections execute themselves without Python's call stack?**

The challenge: When kernel.try fires, it creates a match request. The match projections run, producing match_done. Then kernel.match_success fires, creating a subst request. The subst projections run...

**Who drives this iteration?** Currently Python's for-loop. We need the kernel itself to drive it.

---

## Proposed Solution: Continuation-Passing Kernel

### Core Idea

Instead of Python calling `eval_step()` repeatedly, the kernel state includes a **continuation** that tells the next step what to do.

```
State = {
    _mode: "kernel" | "match" | "subst" | "done",
    _cont: <what to do after current mode completes>,
    _input: <current value being processed>,
    _remaining: <linked list of untried projections>,
    ...mode-specific fields...
}
```

### Key Insight: Single eval_step Call

The kernel becomes a **single projection application** that returns either:
1. **Done state** - final result ready
2. **Next state** - kernel state with updated continuation

Python only needs to call `eval_step` **once per external step_mu call**. The kernel internally chains through modes via continuations.

### State Machine with Continuations

```
Entry: {_step: input, _projs: linked_list}
    ↓ kernel.wrap
State: {_mode: "kernel", _phase: "try", _cont: null, ...}
    ↓ kernel.try (extracts first projection)
State: {_mode: "match", _cont: {on_success: "subst", on_fail: "next"}, ...}
    ↓ match projections run (possibly multiple steps)
State: {_mode: "match_done", _status: "success", _cont: ..., ...}
    ↓ kernel.match_success (reads continuation)
State: {_mode: "subst", _cont: {on_done: "unwrap"}, ...}
    ↓ subst projections run
State: {_mode: "subst_done", _cont: ..., ...}
    ↓ kernel.subst_success (reads continuation)
State: {_mode: "done", _result: ..., _stall: false}
    ↓ kernel.unwrap
Final: unwrapped result
```

### Handling Multiple Steps Within Match/Subst

Match and subst each take multiple internal steps (traverse, descend, bind, etc.). These are already structural via match.v2 and subst.v2 projections.

The continuation tells the kernel what to do when match/subst completes:
- `on_success: "subst"` - proceed to substitution
- `on_fail: "next"` - try next projection
- `on_done: "unwrap"` - extract final result

---

## Alternative Approaches Considered

### A. Trampoline Pattern

Python calls kernel once, kernel returns "thunk" (next computation), Python calls again.

**Problem:** Still requires Python loop to process thunks. Doesn't eliminate Python iteration.

### B. CPS Transform All Projections

Transform every projection to continuation-passing style.

**Problem:** Massive complexity. Would require rewriting match.v2 and subst.v2 entirely.

### C. Meta-Kernel That Runs Kernel

A "super-kernel" that runs the regular kernel.

**Problem:** Infinite regress. Who runs the meta-kernel?

### D. Fuel-Based Recursion (Selected Approach)

Kernel tracks "fuel" (step budget) structurally. Each step decrements fuel. When fuel = 0, stall.

**This avoids Python loop** because:
1. Kernel checks fuel before each transition
2. Fuel is a linked-list (structural countdown)
3. Empty fuel = stall (pattern match on null)

---

## Detailed Design: Fuel-Based Recursive Kernel

### Fuel Representation

```json
{
    "_fuel": {"tick": null, "remaining": {"tick": null, "remaining": {"tick": null, "remaining": null}}}
}
```

This is a linked list of "tick" markers. 3 ticks = 3 steps remaining.

### Fuel Consumption Projection

```json
{
    "id": "kernel.consume_fuel",
    "pattern": {
        "_mode": "kernel",
        "_fuel": {"tick": null, "remaining": {"var": "rest"}}
    },
    "body": {
        "_mode": "kernel",
        "_fuel": {"var": "rest"},
        "...": "...rest of state..."
    }
}
```

### Fuel Exhaustion = Stall

```json
{
    "id": "kernel.fuel_exhausted",
    "pattern": {
        "_mode": "kernel",
        "_fuel": null
    },
    "body": {
        "_mode": "done",
        "_result": "...original input...",
        "_stall": true
    }
}
```

### How This Eliminates Python Loop

1. Python calls `eval_step(kernel_projs, entry_state)` **once**
2. Kernel projections fire in sequence:
   - kernel.wrap (adds fuel)
   - kernel.try (consumes fuel, extracts projection)
   - match projections (each consumes fuel)
   - kernel.match_success (consumes fuel)
   - subst projections (each consumes fuel)
   - kernel.subst_success (consumes fuel)
   - kernel.unwrap (extracts result)
3. If fuel runs out at any point, kernel.fuel_exhausted fires → stall
4. Python receives final state (done or stall)

**No Python loop needed.** The kernel self-iterates via projections.

---

## Implementation Plan

### Phase 8a: Add Fuel to Kernel State

1. Modify kernel.wrap to add `_fuel` field
2. Add kernel.consume_fuel projection
3. Add kernel.fuel_exhausted projection
4. Test: kernel with 1 fuel tick stalls after 1 step

### Phase 8b: Chain Match Projections

1. Modify match.v2 projections to consume fuel
2. Each match.* projection decrements fuel
3. Test: match completes within fuel budget

### Phase 8c: Chain Subst Projections

1. Modify subst.v2 projections to consume fuel
2. Each subst.* projection decrements fuel
3. Test: subst completes within fuel budget

### Phase 8d: Remove Python Loop

1. Modify step_kernel_mu to call eval_step **once**
2. Remove `for _ in range(max_steps)` loop
3. Remove `@host_iteration` decorator
4. Debt: 15 → 14 (one fewer @host_iteration)

### Phase 8e: Eliminate eval_seed.step Usage

1. projection_runner uses step_mu (which uses kernel)
2. Remove eval_seed.step calls from hot path
3. Debt: 14 → 13

### Phase 8f: Clean Up projection_runner

1. Inline or remove projection_runner factory
2. match_mu/subst_mu call kernel directly
3. Debt: 13 → 12

---

## Success Criteria

- [ ] Kernel self-iterates without Python loop
- [ ] Fuel-based termination (structural, not arithmetic)
- [ ] `@host_iteration` removed from step_kernel_mu
- [ ] Debt reduced: 15 → 12
- [ ] All 1300+ tests pass
- [ ] Parity with current behavior (fuel budget = old max_steps)

---

## Open Questions

1. **Fuel budget:** How many ticks for typical operations? Need empirical data.

2. **Fuel refill:** Should outer run_mu add more fuel on each cycle? Or is fuel per-step only?

3. **Debugging:** How to trace execution when kernel self-iterates? Need structural trace.

4. **Performance:** Is fuel-based iteration slower than Python loop? Measure.

5. **Error handling:** How does fuel exhaustion interact with error states?

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Fuel budget wrong | Medium | Test failures | Empirical tuning, generous default |
| Performance regression | Low | Slower tests | Profile, optimize if needed |
| Match/subst rewrite complex | Medium | Delays | Incremental approach (8a-8f) |
| Subtle behavioral differences | Medium | Bugs | Extensive parity testing |

---

## Appendix: Current Code Location

- Kernel projections: `seeds/kernel.v1.json`
- Match projections: `seeds/match.v2.json`
- Subst projections: `seeds/subst.v2.json`
- Python execution loop: `rcx_pi/selfhost/step_mu.py:234-268`
- Debt marker: `rcx_pi/selfhost/step_mu.py:181` (@host_iteration)

---

**Author:** Claude Code (Phase 8 Design)
**Date:** 2026-01-28
**Status:** DESIGN - awaiting agent review
