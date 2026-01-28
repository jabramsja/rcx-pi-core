# Meta-Circular Kernel Specification v0

Status: **VECTOR** (design-only, no implementation until approved)

**Revision History:**
- v0.1: Initial design with 11 projections
- v0.2: Simplified to 7 projections, addressed agent-identified gaps

**Agent Review Summary:**
- structural-proof: Linked-list cursor PROVEN STRUCTURAL
- adversary: Mode namespace collision (HIGH) - addressed with `_kernel_` prefix
- expert: Simplify from 11 to 5-7 projections - addressed
- verifier: Context preservation gap - addressed with `kernel_ctx` field

## Purpose

Define how the kernel loop itself becomes structural. Currently, `step_mu()` uses a Python for-loop to try projections in order. Phase 7 eliminates this by expressing projection selection as Mu projections.

## The Meta-Circular Requirement

**Critical Insight:** Both self-hosting AND meta-circularity are required.

- **Self-hosting**: Algorithms (match, subst) expressed as Mu projections ✓ ACHIEVED
- **Meta-circularity**: The evaluator runs itself - projections select projections

If Python provides the iteration ("try each projection in order"), emergence might be a Python artifact. The kernel loop must be structural for RCX to prove emergence honestly.

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

## Key Design Decisions

### Q1: How do we represent "try projections in order"?

**Answer: Linked-list cursor (not integer)**

The kernel uses the remaining projection list itself as the cursor:
```json
{"_remaining": {"head": <projection>, "tail": <rest>}}  // More to try
{"_remaining": null}                                     // All tried → stall
```

Pattern matching on `head/tail` vs `null` provides iteration without arithmetic.

### Q2: What is the meta-representation of "first match wins"?

**Answer: Mode transitions with context preservation**

The kernel transitions through modes: `kernel` → `match` → `subst` → `done`

Context (`_match_ctx`, `_subst_ctx`) carries state through mode transitions:
- `_input` - original value
- `_body` - projection body to substitute into
- `_remaining` - projections not yet tried

### Q3: How does the kernel loop terminate?

**Three termination conditions:**

1. **Match found**: Produces `{_mode: "done", _stall: false, _result: ...}`
2. **All projections tried**: Produces `{_mode: "done", _stall: true, _result: <input>}`
3. **Max steps exceeded**: External limit (unchanged from current)

### Q4: What is the bootstrap problem?

**The meta-circularity challenge:**

If projections select projections, what selects those projections?

**Answer: Kernel projections are fixed (7 total)**

```
┌─────────────────────────────────────────────────────┐
│  KERNEL PROJECTIONS (fixed, never change)           │
│  - kernel.wrap, kernel.try, kernel.stall            │
│  - kernel.match_success, kernel.match_fail          │
│  - kernel.subst_success, kernel.unwrap              │
└─────────────────────────────────────────────────────┘
                        │
                        ▼ applies
┌─────────────────────────────────────────────────────┐
│  DOMAIN PROJECTIONS (from seeds, configurable)      │
│  - match.*, subst.*, classify.*, user-defined       │
└─────────────────────────────────────────────────────┘
```

Kernel projections are the "hardware" - they implement iteration. Domain projections are the "software" - they define what each step does.

## Design: Context-Preserving State Machine

### Why Linked List Cursor?

The naive approach uses integer cursors and arithmetic (`get`, `inc`, `len`, `gte`). These are **host operations** that violate the "structure is primitive" invariant.

**Solution:** Use the projection list itself as the cursor. The `_remaining` field is a linked list:

```json
{"_remaining": {"head": <projection>, "tail": <rest>}}  // More to try
{"_remaining": null}                                     // All exhausted → stall
```

Pattern matching on `head/tail` vs `null` handles iteration structurally. **No arithmetic needed.**

Structural-proof agent verified: This approach is SOUND and STRUCTURAL.

### Why Context Passthrough?

**Key insight:** The context preservation problem is solved by carrying `kernel_ctx` through all mode transitions.

### Core Principle: No Context Loss

When transitioning from kernel → match → subst → kernel, we must preserve:
- `remaining` - projections not yet tried (linked list)
- `body` - the projection body to substitute into (if match succeeds)
- `input` - the original input value

This is achieved by wrapping the entire kernel context in a `kernel_ctx` field that passes through match/subst untouched.

### State Machine with Context Preservation

```
┌───────────────────────────────────────────────────────────┐
│ ENTRY: {_step: X, _projs: [P1, P2, ...]}                   │
└───────────────────────────────────────────────────────────┘
          │
          ▼ kernel.wrap
┌───────────────────────────────────────────────────────────┐
│ {_mode: "kernel", _phase: "try",                          │
│  _input: X, _remaining: {head: P1, tail: [P2, ...]}}      │
└───────────────────────────────────────────────────────────┘
          │
          ├─── (_remaining: null) ──▶ kernel.stall ──▶ {_mode: "done", _result: X, _stall: true}
          │
          ▼ kernel.try (remaining has head)
┌───────────────────────────────────────────────────────────┐
│ {_mode: "match", _pattern_focus: P1.pattern, ...          │
│  _match_ctx: {_input: X, _body: P1.body,                  │
│               _remaining: [P2, ...]}}                     │
└───────────────────────────────────────────────────────────┘
          │
          ▼ match.* projections run (context passes through)
          │
          ├─── (match.fail) ──▶ {_mode: "kernel", _phase: "no_match", ...}
          │                            │
          │                            ▼ kernel.advance
          │                     (loop back to try with remaining = tail)
          │
          ▼ match.done (success)
┌───────────────────────────────────────────────────────────┐
│ {_mode: "subst", _focus: body, _bindings: {...},          │
│  _subst_ctx: {_input: X, _remaining: [P2, ...]}}          │
└───────────────────────────────────────────────────────────┘
          │
          ▼ subst.* projections run (context passes through)
          │
          ▼ subst.done
┌───────────────────────────────────────────────────────────┐
│ {_mode: "done", _result: <substituted>, _stall: false}    │
└───────────────────────────────────────────────────────────┘
```

### Structural NO_MATCH Representation (Gap 1 Addressed)

**Problem:** Current `match_mu` returns Python sentinel `NO_MATCH`.

**Solution:** Match projections ALREADY return structural results. The issue is the transition back to kernel mode.

When match fails, `match.fail` produces:
```json
{"_mode": "match_done", "_status": "no_match", "_match_ctx": {...}}
```

When match succeeds, `match.done` produces:
```json
{"_mode": "match_done", "_status": "success", "_bindings": {...}, "_match_ctx": {...}}
```

The `_match_ctx` field carries the kernel context through, enabling proper resume.

### Namespace Protection (Adversary Finding Addressed)

**Problem:** Domain projections could forge kernel state (mode namespace collision).

**Solution:** Use `_` prefix for all kernel-internal fields:
- `_mode`, `_phase`, `_input`, `_remaining`, `_match_ctx`, `_subst_ctx`
- Domain data uses non-underscore keys
- Projections with `_mode` in pattern are kernel projections (run first)

Validation: Reject inputs that start with `_mode` at kernel boundary.

### Simplified Projection Set (7 Kernel Projections)

Expert recommended simplifying from 11 to 5-7. Here's the minimal set:

**1. kernel.wrap** - Entry point
```json
{
  "id": "kernel.wrap",
  "pattern": {"_step": {"var": "input"}, "_projs": {"var": "projs"}},
  "body": {
    "_mode": "kernel", "_phase": "try",
    "_input": {"var": "input"},
    "_remaining": {"var": "projs"}
  }
}
```

**2. kernel.stall** - Empty remaining list (null)
```json
{
  "id": "kernel.stall",
  "pattern": {"_mode": "kernel", "_phase": "try", "_input": {"var": "input"}, "_remaining": null},
  "body": {"_mode": "done", "_result": {"var": "input"}, "_stall": true}
}
```

**3. kernel.try** - Start matching first projection
```json
{
  "id": "kernel.try",
  "pattern": {
    "_mode": "kernel", "_phase": "try",
    "_input": {"var": "input"},
    "_remaining": {"head": {"pattern": {"var": "p"}, "body": {"var": "b"}}, "tail": {"var": "rest"}}
  },
  "body": {
    "_mode": "match",
    "_pattern_focus": {"var": "p"},
    "_value_focus": {"var": "input"},
    "_match_ctx": {"_input": {"var": "input"}, "_body": {"var": "b"}, "_remaining": {"var": "rest"}}
  }
}
```

**4. kernel.match_success** - Match succeeded, start substitution
```json
{
  "id": "kernel.match_success",
  "pattern": {
    "_mode": "match_done", "_status": "success",
    "_bindings": {"var": "bindings"},
    "_match_ctx": {"_input": {"var": "input"}, "_body": {"var": "body"}, "_remaining": {"var": "rest"}}
  },
  "body": {
    "_mode": "subst",
    "_focus": {"var": "body"},
    "_bindings": {"var": "bindings"},
    "_subst_ctx": {"_input": {"var": "input"}, "_remaining": {"var": "rest"}}
  }
}
```

**5. kernel.match_fail** - Match failed, advance to next projection
```json
{
  "id": "kernel.match_fail",
  "pattern": {
    "_mode": "match_done", "_status": "no_match",
    "_match_ctx": {"_input": {"var": "input"}, "_remaining": {"var": "rest"}}
  },
  "body": {
    "_mode": "kernel", "_phase": "try",
    "_input": {"var": "input"},
    "_remaining": {"var": "rest"}
  }
}
```

**6. kernel.subst_success** - Substitution complete, return result
```json
{
  "id": "kernel.subst_success",
  "pattern": {
    "_mode": "subst_done",
    "_result": {"var": "result"},
    "_subst_ctx": {"var": "_"}
  },
  "body": {"_mode": "done", "_result": {"var": "result"}, "_stall": false}
}
```

**7. kernel.unwrap** - Extract final result
```json
{
  "id": "kernel.unwrap",
  "pattern": {"_mode": "done", "_result": {"var": "result"}, "_stall": {"var": "stall"}},
  "body": {"var": "result"}
}
```

**Total: 7 kernel projections** (down from 11)

### Required Match/Subst Modifications

The existing match.* and subst.* projections need minor modifications:

1. **match.done** must include `_match_ctx` passthrough:
```json
// Current: {"bindings": {...}}
// New: {"_mode": "match_done", "_status": "success", "_bindings": {...}, "_match_ctx": <passthrough>}
```

2. **match.fail** must include `_match_ctx` passthrough:
```json
// New: {"_mode": "match_done", "_status": "no_match", "_match_ctx": <passthrough>}
```

3. **subst.done** must include `_subst_ctx` passthrough:
```json
// Current: <result>
// New: {"_mode": "subst_done", "_result": <result>, "_subst_ctx": <passthrough>}
```

These are **additive changes** to existing seeds - no breaking changes to current behavior.

### Full Projection Count (Revised)

**Kernel projections (7):** wrap, stall, try, match_success, match_fail, subst_success, unwrap

**Modified existing:**
- match.* (13 projections) + context passthrough
- subst.* (13 projections) + context passthrough
- classify.* (6 projections) - unchanged

**Total: 39 projections** for fully self-hosted kernel step

## Manual Trace: Concrete Example

To verify the design is complete, here's a step-by-step trace of applying a simple projection.

**Input:**
```json
{"_step": {"x": 1}, "_projs": [{"pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}}]}
```

**Goal:** Match `{"x": 1}` against pattern `{"x": {"var": "v"}}`, bind `v=1`, substitute to get `{"result": 1}`.

### Step 1: kernel.wrap
```
Input:  {"_step": {"x": 1}, "_projs": [{...}]}
Output: {"_mode": "kernel", "_phase": "try", "_input": {"x": 1},
         "_remaining": {"head": {...}, "tail": null}}
```

### Step 2: kernel.try
```
Input:  {"_mode": "kernel", "_phase": "try", "_input": {"x": 1},
         "_remaining": {"head": {"pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}},
                        "tail": null}}
Output: {"_mode": "match",
         "_pattern_focus": {"x": {"var": "v"}},
         "_value_focus": {"x": 1},
         "_match_ctx": {"_input": {"x": 1}, "_body": {"result": {"var": "v"}}, "_remaining": null}}
```

### Steps 3-N: match.* projections run
(Existing match projections handle this, eventually producing:)
```
Output: {"_mode": "match_done", "_status": "success",
         "_bindings": {"v": 1},
         "_match_ctx": {"_input": {"x": 1}, "_body": {"result": {"var": "v"}}, "_remaining": null}}
```

### Step N+1: kernel.match_success
```
Input:  {"_mode": "match_done", "_status": "success", "_bindings": {"v": 1},
         "_match_ctx": {"_input": {"x": 1}, "_body": {"result": {"var": "v"}}, "_remaining": null}}
Output: {"_mode": "subst", "_focus": {"result": {"var": "v"}}, "_bindings": {"v": 1},
         "_subst_ctx": {"_input": {"x": 1}, "_remaining": null}}
```

### Steps N+2 to M: subst.* projections run
(Existing subst projections handle this, eventually producing:)
```
Output: {"_mode": "subst_done", "_result": {"result": 1},
         "_subst_ctx": {"_input": {"x": 1}, "_remaining": null}}
```

### Step M+1: kernel.subst_success
```
Input:  {"_mode": "subst_done", "_result": {"result": 1}, "_subst_ctx": {...}}
Output: {"_mode": "done", "_result": {"result": 1}, "_stall": false}
```

### Step M+2: kernel.unwrap
```
Input:  {"_mode": "done", "_result": {"result": 1}, "_stall": false}
Output: {"result": 1}
```

**Final result:** `{"result": 1}` ✓

### Manual Trace: No Match Case

**Input:** `{"_step": {"y": 2}, "_projs": [{"pattern": {"x": {"var": "v"}}, "body": {...}}]}`

After kernel.try → match.* projections run → match fails:
```
{"_mode": "match_done", "_status": "no_match",
 "_match_ctx": {"_input": {"y": 2}, "_remaining": null}}
```

Then kernel.match_fail:
```
{"_mode": "kernel", "_phase": "try", "_input": {"y": 2}, "_remaining": null}
```

Then kernel.stall (remaining is null):
```
{"_mode": "done", "_result": {"y": 2}, "_stall": true}
```

Then kernel.unwrap:
```
{"y": 2}  // Original input returned (stall)
```

## Implementation Plan

### Phase 7a: Kernel projections seed
1. Create `seeds/kernel.v1.json` with 7 projections
2. Test kernel projections in isolation (manual trace tests)
3. Verify linked-list cursor advancement works

### Phase 7b: Match/Subst context passthrough
1. Add `_match_ctx` passthrough to match.done, match.fail projections
2. Add `_subst_ctx` passthrough to subst.done projection
3. Verify existing parity tests still pass (additive change)

### Phase 7c: Integration testing
1. Combine kernel + match + subst + classify projections
2. Test full cycle: kernel → match → subst → kernel
3. Manual trace tests for success and failure cases

### Phase 7d: Replace Python scaffolding
1. `step_mu` calls structural kernel instead of Python loop
2. Verify parity with Python `step_mu` (1000+ fuzzer examples)
3. Remove `@host_iteration` debt markers

## Success Criteria

1. [ ] `seeds/kernel.v1.json` exists with 7 projections
2. [ ] Manual trace tests pass for success and failure cases
3. [ ] Match/subst context passthrough tests pass
4. [ ] Kernel projections pass parity tests with Python `step_mu`
5. [ ] No Python for-loop in step_mu execution path
6. [ ] All 1000+ existing tests still pass
7. [ ] Debt threshold decreases (target: 11 → 9 or lower)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Context passthrough breaks existing tests | Additive-only changes to match/subst |
| Mode transition complexity | Manual trace tests lock behavior |
| Performance degradation | Benchmark before/after |
| Projection explosion | Keep kernel projections minimal (7) |
| Bootstrap infinite regress | Kernel projections are fixed, not self-modifying |
| Namespace collision | `_` prefix + boundary validation |

## Agent-Identified Gaps: Resolution Summary

| Gap | Original Issue | Resolution |
|-----|----------------|------------|
| Context preservation | Kernel state lost during mode transitions | `_match_ctx` / `_subst_ctx` fields carry context through |
| Structural NO_MATCH | Python sentinel | `{"_mode": "match_done", "_status": "no_match", "_match_ctx": ...}` |
| Mode transitions | Outputs don't match inputs | Revised projections with matching field names |
| Too many projections | 11 was over-engineered | Simplified to 7 |
| Namespace collision | Domain could forge kernel state | `_` prefix + boundary validation |

## Bootstrap Iteration (Explicitly Out of Scope)

**Question:** How does `run_mu` loop without Python for-loop?

**Answer:** The outer loop (run until stall) remains Python scaffolding.

**Rationale:**
- `step_mu` (try projections in order) → Phase 7 makes structural
- `run_mu` (repeat step until stall) → Remains Python boundary

This is acceptable because:
1. The iteration primitive (for-loop) is **operational**, not **semantic**
2. Stall detection (`mu_equal(before, after)`) is already structural
3. Max-steps is a **resource limit**, not algorithmic logic

**Phase 7 scope:** Self-host projection selection, not the outer repeat-until-stall loop.

**Future (Phase 8+):** Could make outer loop structural by preserving `_original_projs` through the cycle, but this adds significant complexity for marginal benefit. Defer to later phase.

## Complete State Machine Transition Table (v0.2)

| From State | Projection | To State |
|------------|------------|----------|
| `{_step, _projs}` | kernel.wrap | `{_mode: kernel, _phase: try, _remaining: ...}` |
| `{_mode: kernel, _phase: try, _remaining: null}` | kernel.stall | `{_mode: done, _stall: true}` |
| `{_mode: kernel, _phase: try, _remaining: {head, tail}}` | kernel.try | `{_mode: match, _match_ctx: ...}` |
| `{_mode: match_done, _status: success, _match_ctx: ...}` | kernel.match_success | `{_mode: subst, _subst_ctx: ...}` |
| `{_mode: match_done, _status: no_match, _match_ctx: ...}` | kernel.match_fail | `{_mode: kernel, _phase: try}` |
| `{_mode: subst_done, _result: ..., _subst_ctx: ...}` | kernel.subst_success | `{_mode: done, _stall: false}` |
| `{_mode: done, _result: ..., _stall: ...}` | kernel.unwrap | result value |

## Resolved Questions

1. **Projection ordering:** Kernel projections FIRST (match on `_mode`)
2. **NO_MATCH representation:** Structural `{_status: "no_match"}` with context
3. **Stall vs done:** `{_mode: "done", _stall: true/false}`
4. **Context preservation:** `_match_ctx` / `_subst_ctx` passthrough
5. **Bootstrap iteration:** Outer run loop remains Python (acceptable boundary)

## References

- `docs/core/SelfHosting.v0.md` - Phase 5/6 self-hosting spec
- `docs/core/RCXKernel.v0.md` - Original kernel spec
- `rcx_pi/selfhost/step_mu.py` - Current Python implementation
- `seeds/match.v1.json` - Match projections (13)
- `seeds/subst.v1.json` - Subst projections (13)
- `seeds/classify.v1.json` - Classify projections (6)
