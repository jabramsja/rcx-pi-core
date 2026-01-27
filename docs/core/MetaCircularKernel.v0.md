# Meta-Circular Kernel Specification v0

Status: **VECTOR** (design-only, no implementation until approved)

**Agent Review:** structural-proof agent verified linked-list cursor is SOUND and STRUCTURAL. Gaps in state machine transitions addressed in "Structural-Proof Agent Findings" section.

## Purpose

Define how the kernel loop itself becomes structural. Currently, `step_mu()` uses a Python for-loop to try projections in order. Phase 7 eliminates this by expressing projection selection as Mu projections.

## Problem Statement

Phase 5/6 achieved:
- `match_mu`: Pattern matching as Mu projections (13 projections)
- `subst_mu`: Substitution as Mu projections (13 projections)
- `classify_mu`: Classification as Mu projections (6 projections)
- `step_mu`: Composition of match_mu + subst_mu

But `step_mu` still has Python iteration:
```python
def step_mu(projections: list[Mu], input_value: Mu) -> Mu:
    for proj in projections:                    # <- Python for-loop
        result = apply_mu(proj, input_value)
        if result is not NO_MATCH:              # <- Python conditional
            return result
    return input_value                          # <- Python return (stall)
```

This is "scaffolding debt" - the last major Python iteration in the self-hosting stack.

## Design Goal

```
BEFORE (Phase 6):
  Python for-loop → calls apply_mu() → returns result

AFTER (Phase 7):
  Mu projections → select/apply projection → return result or stall
```

## Key Questions

### Q1: How do we represent "try projections in order"?

**Answer: Explicit projection cursor state**

The kernel loop state becomes:
```json
{
  "mode": "kernel",
  "input": <value to transform>,
  "projections": [<p1>, <p2>, ..., <pn>],
  "cursor": 0,
  "phase": "try"
}
```

Projections advance the cursor or return result.

### Q2: What is the meta-representation of "first match wins"?

**Answer: Two-phase apply**

Each projection application has two phases:
1. **try**: Attempt to apply projection at cursor
2. **advance**: Move cursor to next projection (if no match)

```json
// Phase: try
{
  "mode": "kernel",
  "input": {"var": "x"},
  "projections": [p1, p2],
  "cursor": 0,
  "phase": "try"
}
// → Applies p1 to input. If match, phase="done". If no match, phase="advance".

// Phase: advance
{
  "mode": "kernel",
  "input": {"var": "x"},
  "projections": [p1, p2],
  "cursor": 0,
  "phase": "advance"
}
// → Increments cursor to 1, sets phase="try"
```

### Q3: How does the kernel loop terminate?

**Three termination conditions:**

1. **Match found**: `phase="done"` with result
2. **All projections tried**: `cursor >= len(projections)` → stall
3. **Max steps exceeded**: External limit (unchanged from current)

### Q4: What is the bootstrap problem?

**The meta-circularity challenge:**

If we use projections to select projections, what selects those projections?

**Answer: Kernel projections are fixed**

```
┌─────────────────────────────────────────────────────┐
│  KERNEL PROJECTIONS (fixed, never change)           │
│  - kernel.try     : attempt current projection      │
│  - kernel.advance : move to next projection         │
│  - kernel.done    : return result                   │
│  - kernel.stall   : all projections tried           │
│  - kernel.wrap    : entry point                     │
└─────────────────────────────────────────────────────┘
                        │
                        ▼ applies
┌─────────────────────────────────────────────────────┐
│  DOMAIN PROJECTIONS (from seeds, configurable)      │
│  - match.*, subst.*, classify.*, user-defined       │
└─────────────────────────────────────────────────────┘
```

The kernel projections are the "hardware" - they implement the iteration primitive. Domain projections are the "software" - they define what each step does.

## Kernel Projections (5 total)

### 1. kernel.wrap - Entry point
```json
{
  "id": "kernel.wrap",
  "pattern": {
    "step": {"var": "input"},
    "projections": {"var": "projs"}
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": 0,
    "phase": "try"
  }
}
```

### 2. kernel.try - Attempt current projection
```json
{
  "id": "kernel.try",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": {"var": "i"},
    "phase": "try"
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": {"var": "i"},
    "phase": "apply",
    "applying": {"op": "get", "list": {"var": "projs"}, "index": {"var": "i"}}
  }
}
```

**Note:** This requires a `get` operation to extract projection at index. Options:
- Add `get` as kernel primitive (not ideal - adds complexity)
- Represent projections as linked list with cursor as "rest" pointer
- Use match to destructure projection list

### 3. kernel.advance - Move to next projection
```json
{
  "id": "kernel.advance",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": {"var": "i"},
    "phase": "no_match"
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": {"op": "inc", "value": {"var": "i"}},
    "phase": "try"
  }
}
```

**Note:** This requires an `inc` operation to increment cursor. Same options as above.

### 4. kernel.done - Match found
```json
{
  "id": "kernel.done",
  "pattern": {
    "mode": "kernel",
    "phase": "match",
    "result": {"var": "result"}
  },
  "body": {
    "mode": "kernel_done",
    "result": {"var": "result"}
  }
}
```

### 5. kernel.stall - All projections exhausted
```json
{
  "id": "kernel.stall",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "projections": {"var": "projs"},
    "cursor": {"var": "i"},
    "phase": "try"
  },
  "guard": {"op": "gte", "left": {"var": "i"}, "right": {"op": "len", "list": {"var": "projs"}}},
  "body": {
    "mode": "kernel_done",
    "result": {"var": "input"},
    "stall": true
  }
}
```

**Note:** This requires `gte` (greater-than-or-equal) and `len` operations. This is problematic.

## The Arithmetic Problem

The naive design above requires:
- `get(list, index)` - array access
- `inc(n)` - increment
- `len(list)` - length
- `gte(a, b)` - comparison

These are **host operations** that violate the "structure is primitive" invariant.

## Alternative Design: Linked List Cursor

Instead of integer cursors, use the projection list itself as the cursor:

```json
{
  "mode": "kernel",
  "input": <value>,
  "remaining": [<p1>, <p2>, ...],  // projections not yet tried
  "phase": "try"
}
```

### Revised Projections

**1. kernel.try** - Attempt first remaining projection
```json
{
  "id": "kernel.try",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {
      "head": {"var": "proj"},
      "tail": {"var": "rest"}
    },
    "phase": "try"
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "apply",
    "applying": {"var": "proj"}
  }
}
```

**2. kernel.advance** - Move to next (after no match)
```json
{
  "id": "kernel.advance",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "no_match"
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "try"
  }
}
```

**3. kernel.stall** - Empty remaining list
```json
{
  "id": "kernel.stall",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": null,
    "phase": "try"
  },
  "body": {
    "mode": "kernel_done",
    "result": {"var": "input"},
    "stall": true
  }
}
```

**4. kernel.done** - Match found
```json
{
  "id": "kernel.done",
  "pattern": {
    "mode": "kernel",
    "phase": "match",
    "result": {"var": "result"}
  },
  "body": {
    "mode": "kernel_done",
    "result": {"var": "result"}
  }
}
```

**5. kernel.wrap** - Entry point
```json
{
  "id": "kernel.wrap",
  "pattern": {
    "step": {"var": "input"},
    "projections": {"var": "projs"}
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "projs"},
    "phase": "try"
  }
}
```

This design uses **only structural operations** (pattern matching on head/tail). No arithmetic needed.

## The Apply Problem

The above handles projection SELECTION. But how do we APPLY the selected projection?

Current `apply_mu`:
```python
bindings = match_mu(pattern, input_value)
if bindings is NO_MATCH:
    return NO_MATCH
return subst_mu(body, bindings)
```

This is already Mu projections (match_mu, subst_mu). But the sequencing (match → check → subst) is still Python.

### Option A: Inline application phases

Add phases for application within kernel state:
```json
{
  "mode": "kernel",
  "input": {...},
  "remaining": [...],
  "phase": "applying",
  "applying": {"pattern": {...}, "body": {...}},
  "apply_phase": "match"  // → "check" → "subst" → "done"
}
```

This makes the kernel projections more complex but keeps everything structural.

### Option B: Nested kernel calls

The kernel can call itself to run match/subst projections:
```
kernel(input, domain_projections)
  → kernel(match_state, match_projections)
  → kernel(subst_state, subst_projections)
  → result
```

This is cleaner but requires "continuation" handling to return to the outer kernel.

### Option C: Unified projection format (Recommended)

All projections (kernel, match, subst, domain) share the same format and run in the same kernel loop. The "mode" field distinguishes them:

```
kernel.* → kernel loop control
match.*  → pattern matching
subst.*  → substitution
domain.* → user projections
```

The kernel loop just runs ALL projections until stall. Mode transitions happen naturally via projection bodies.

## Recommended Design: Option C

**Key insight:** The kernel loop doesn't need to "call" match_mu and subst_mu. It just needs to run projections until stall. Match and subst projections already exist and work.

### Unified State Machine

```
┌─────────────────────────────────────────────────────┐
│ State: {mode: "kernel", input: X, remaining: [P...]}│
└─────────────────────────────────────────────────────┘
          │
          ▼ kernel.try
┌─────────────────────────────────────────────────────┐
│ State: {mode: "kernel", phase: "apply", ...}        │
│        {applying: {pattern: P, body: B}}            │
└─────────────────────────────────────────────────────┘
          │
          ▼ kernel.match_wrap
┌─────────────────────────────────────────────────────┐
│ State: {mode: "match", pattern_focus: P, ...}       │
└─────────────────────────────────────────────────────┘
          │
          ▼ match.* projections run
          │
          ▼ match.done
┌─────────────────────────────────────────────────────┐
│ State: {mode: "kernel", phase: "matched", ...}      │
│        {bindings: {...}}                            │
└─────────────────────────────────────────────────────┘
          │
          ▼ kernel.subst_wrap
┌─────────────────────────────────────────────────────┐
│ State: {mode: "subst", focus: B, bindings: {...}}   │
└─────────────────────────────────────────────────────┘
          │
          ▼ subst.* projections run
          │
          ▼ subst.done
┌─────────────────────────────────────────────────────┐
│ State: {mode: "kernel", phase: "match", result: R}  │
└─────────────────────────────────────────────────────┘
          │
          ▼ kernel.done
┌─────────────────────────────────────────────────────┐
│ State: {mode: "kernel_done", result: R}             │
└─────────────────────────────────────────────────────┘
```

### Full Projection Set

**Kernel projections (7):**
1. `kernel.wrap` - Entry: `{step, projections}` → kernel state
2. `kernel.try` - Start applying first remaining projection
3. `kernel.match_wrap` - Transition to match mode
4. `kernel.match_done` - Match succeeded, transition to subst
5. `kernel.no_match` - Match failed, advance cursor
6. `kernel.subst_done` - Subst complete, return result
7. `kernel.stall` - No remaining projections

**Plus existing (32):**
- match.* (13 projections)
- subst.* (13 projections)
- classify.* (6 projections)

**Total: 39 projections** for fully self-hosted kernel.

## Implementation Plan

### Phase 7a: Kernel projections seed
1. Create `seeds/kernel.v1.json` with 7 projections
2. Test kernel projections in isolation
3. Verify cursor advancement works correctly

### Phase 7b: Integration with match/subst
1. Add mode transition projections
2. Test full apply cycle: kernel → match → subst → kernel
3. Verify parity with Python `apply_mu`

### Phase 7c: Full self-hosting
1. Combine all projections (kernel + match + subst + classify)
2. Run domain projections through structural kernel
3. Verify parity with Python `step_mu`

### Phase 7d: Remove Python scaffolding
1. `step_mu` calls structural kernel instead of Python loop
2. Remove `@host_iteration` debt markers
3. Final debt count should decrease

## Success Criteria

1. [ ] `seeds/kernel.v1.json` exists with 7 projections
2. [ ] Kernel projections pass parity tests with Python `step_mu`
3. [ ] No Python for-loop in step_mu execution path
4. [ ] All 1000+ existing tests still pass
5. [ ] Debt threshold decreases (target: 11 → 9 or lower)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mode transition complexity | Extensive state machine tests |
| Performance degradation | Benchmark before/after |
| Projection explosion | Keep kernel projections minimal (7) |
| Bootstrap infinite regress | Kernel projections are fixed, not self-modifying |

## Structural-Proof Agent Findings (Addressed)

The structural-proof agent identified critical gaps. This section addresses each:

### Gap 1: NO_MATCH Must Be Structural

**Problem:** Current `match_mu` returns Python sentinel `NO_MATCH`.

**Solution:** Match projections must return structural result:

```json
// Match success:
{"mode": "match_done", "status": "success", "bindings": {...}}

// Match failure:
{"mode": "match_done", "status": "no_match"}
```

**Required change to match.v1.json:**
- `match.done` returns `{"status": "success", "bindings": ...}`
- Add `match.fail` projection that returns `{"status": "no_match"}`

### Gap 2: Missing State Transitions

**Problem:** Apply phase doesn't connect to match_wrap.

**Solution:** Add explicit transition projections:

**kernel.extract** - Extract pattern/body from applying:
```json
{
  "id": "kernel.extract",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "apply",
    "applying": {"pattern": {"var": "p"}, "body": {"var": "b"}}
  },
  "body": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "matching",
    "pattern": {"var": "p"},
    "body": {"var": "b"}
  }
}
```

**kernel.match_wrap** - Transition to match mode:
```json
{
  "id": "kernel.match_wrap",
  "pattern": {
    "mode": "kernel",
    "input": {"var": "input"},
    "remaining": {"var": "rest"},
    "phase": "matching",
    "pattern": {"var": "p"},
    "body": {"var": "b"}
  },
  "body": {
    "mode": "match",
    "match": {
      "pattern": {"var": "p"},
      "value": {"var": "input"}
    },
    "kernel_context": {
      "remaining": {"var": "rest"},
      "body": {"var": "b"}
    }
  }
}
```

### Gap 3: Bootstrap Iteration

**Problem:** How does `run_mu` loop without Python for-loop?

**Answer:** The outer loop (run until stall) remains Python scaffolding.

**Rationale:**
- `step_mu` (try projections in order) → Phase 7 makes structural
- `run_mu` (repeat step until stall) → Remains Python boundary

This is acceptable because:
1. The iteration primitive (for-loop) is **operational**, not **semantic**
2. Stall detection (`mu_equal(before, after)`) is already structural
3. Max-steps is a **resource limit**, not algorithmic logic

**Phase 7 scope:** Self-host projection selection, not the outer repeat-until-stall loop.

**Future (Phase 8+):** Could make outer loop structural with:
```json
{
  "id": "kernel.iterate",
  "pattern": {
    "mode": "kernel_done",
    "result": {"var": "r"},
    "stall": false
  },
  "body": {
    "step": {"var": "r"},
    "projections": {"var": "original_projs"}
  }
}
```

But this requires preserving `original_projs` through the entire cycle - significant complexity for marginal benefit.

### Complete State Machine Transition Table

| From State | Projection | To State |
|------------|------------|----------|
| `{step, projections}` | kernel.wrap | `{mode: kernel, phase: try, remaining: [...]}` |
| `{mode: kernel, phase: try, remaining: {head, tail}}` | kernel.try | `{phase: apply, applying: head}` |
| `{mode: kernel, phase: try, remaining: null}` | kernel.stall | `{mode: kernel_done, stall: true}` |
| `{phase: apply, applying: {pattern, body}}` | kernel.extract | `{phase: matching, pattern, body}` |
| `{phase: matching, pattern, body}` | kernel.match_wrap | `{mode: match, ...}` |
| `{mode: match, ...}` | match.* | `{mode: match_done, status: success/no_match}` |
| `{mode: match_done, status: success}` | kernel.match_success | `{mode: kernel, phase: substituting}` |
| `{mode: match_done, status: no_match}` | kernel.no_match | `{mode: kernel, phase: no_match}` |
| `{phase: no_match}` | kernel.advance | `{phase: try}` (with remaining = rest) |
| `{phase: substituting, bindings, body}` | kernel.subst_wrap | `{mode: subst, ...}` |
| `{mode: subst, ...}` | subst.* | `{mode: subst_done, result: ...}` |
| `{mode: subst_done, result}` | kernel.subst_success | `{mode: kernel, phase: match, result}` |
| `{phase: match, result}` | kernel.done | `{mode: kernel_done, result, stall: false}` |

### Revised Projection Count

**Kernel projections (10):**
1. `kernel.wrap` - Entry point
2. `kernel.try` - Start applying first projection
3. `kernel.stall` - No projections remaining
4. `kernel.extract` - Extract pattern/body
5. `kernel.match_wrap` - Transition to match
6. `kernel.match_success` - Match succeeded, start subst
7. `kernel.no_match` - Match failed, advance
8. `kernel.advance` - Move to next projection
9. `kernel.subst_wrap` - Transition to subst
10. `kernel.subst_success` - Subst done, return result
11. `kernel.done` - Final result

**Plus existing (32):**
- match.* (13 projections) - needs match.fail added
- subst.* (13 projections)
- classify.* (6 projections)

**Total: 43 projections** for fully self-hosted kernel step.

## Resolved Questions

1. **Projection ordering:** Kernel projections FIRST, with mode guards
2. **NO_MATCH representation:** Structural `{status: "no_match"}` (Gap 1)
3. **Stall vs done:** `{mode: "kernel_done", stall: true/false}`
4. **Bootstrap iteration:** Outer run loop remains Python (acceptable boundary)

## References

- `docs/core/SelfHosting.v0.md` - Phase 5/6 self-hosting spec
- `docs/core/RCXKernel.v0.md` - Original kernel spec
- `rcx_pi/selfhost/step_mu.py` - Current Python implementation
- `seeds/match.v1.json` - Match projections (13)
- `seeds/subst.v1.json` - Subst projections (13)
- `seeds/classify.v1.json` - Classify projections (6)
