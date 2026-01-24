# Stall/Fix Execution Semantics (v0)

**Status: DESIGN DOCUMENT — Requires approval before implementation.**

This document defines execution semantics for the Stall → Fix loop. It is the promotion path for VECTOR #6.

---

## 1. Scope

**Goal**: Define minimal execution semantics for stall/fix that are:
- Deterministic (same input → same output)
- Traceable (all state transitions recorded)
- Testable (golden fixtures validate behavior)

**In Scope (v0)**:
- STALL opcode: value fails pattern match, enters waiting state
- FIX opcode: apply transformation, value exits waiting state
- Trace events for execution (v2 schema extension)
- Deterministic replay of recorded fix sequences

**Explicitly Out of Scope (v0)**:
- ROUTE opcode (bucket routing)
- CLOSE opcode (closure completion)
- External/interactive fix sources
- Multiple concurrent stalled values
- Bucket state persistence across traces

---

## 2. Design Principles

### 2.1 Replay-First

All execution must be replayable from trace. This means:
- Every fix must be recorded as a trace event
- Fix sources are trace events, not external input
- Execution order is deterministic and recorded

### 2.2 Single-Value Focus (v0)

v0 tracks ONE value through the stall/fix cycle:
- Value starts in "active" state
- Value may stall (enter "waiting" state)
- Fix resolves stall (value returns to "active")
- Simplifies reasoning; multi-value deferred to v1

### 2.3 Closed System

Fixes come from:
- Recorded trace events (deterministic replay)
- Rule application (structural transformation)

Fixes do NOT come from:
- External input during execution
- Network/filesystem
- User interaction

---

## 3. Execution State Model

### 3.1 Value State

```
value_state: {
  mu: JsonValue,           // Current structural value
  status: Enum(ACTIVE, STALLED),
  stall_reason: Option<String>,  // Why stalled (pattern id, etc.)
  history: List<StateTransition>,  // For debugging/audit
}
```

### 3.2 State Transitions

```
ACTIVE  --[pattern_mismatch]--> STALLED
STALLED --[fix_applied]-------> ACTIVE
ACTIVE  --[normal_form]-------> TERMINAL (v0: trace.end)
```

### 3.3 Relationship to Buckets

The bucket model from `BytecodeMapping.v0.md` maps to v0 execution as:

| Bucket | v0 Execution State | Notes |
|--------|-------------------|-------|
| `r_a` (active) | `status = ACTIVE` | Value is being reduced |
| `r_null` | `status = STALLED` | Pattern match failed, awaiting fix |
| `r_inf` | Not used in v0 | Divergence detection deferred |
| `lobes` | Not used in v0 | Multi-lobe deferred |
| `sink` | TERMINAL | Value reached normal form |

---

## 4. Opcode Semantics

### 4.1 STALL

**Trigger**: Pattern match fails during reduction.

**Preconditions**:
- `value_state.status == ACTIVE`
- Pattern match returned false

**Effects**:
1. Set `value_state.status = STALLED`
2. Set `value_state.stall_reason = <pattern_id>`
3. Emit `execution.stall` trace event
4. Halt reduction (do not continue to next rule)

**Postconditions**:
- `value_state.status == STALLED`
- Trace contains `execution.stall` event

### 4.2 FIX

**Trigger**: Fix event in trace stream.

**Preconditions**:
- `value_state.status == STALLED`
- Next trace event is `execution.fix`

**Effects**:
1. Apply transformation specified in fix event
2. Set `value_state.status = ACTIVE`
3. Clear `value_state.stall_reason`
4. Emit `execution.fixed` trace event (confirmation)
5. Resume reduction from transformed value

**Postconditions**:
- `value_state.status == ACTIVE`
- `value_state.mu` is transformed value

### 4.3 Interaction with Existing Opcodes

| Existing Opcode | Interaction with STALL/FIX |
|-----------------|---------------------------|
| `LOAD_EVENT` | May load `execution.fix` event |
| `CANON_EVENT` | Canonicalizes fix events same as v1 |
| `EMIT_CANON` | Emits execution events to output |
| `HALT_ERR` | If stalled with no fix available |

---

## 5. Trace Event Schema (v2 Extension)

### 5.1 `execution.stall`

Emitted when execution stalls due to pattern mismatch.

```json
{
  "v": 2,
  "type": "execution.stall",
  "i": <contiguous_index>,
  "mu": {
    "pattern_id": "<which pattern failed>",
    "value_hash": "<deterministic hash of stalled value>"
  }
}
```

**Distinction from `reduction.stall`**:
- `reduction.stall` = observability only (debug, no state change)
- `execution.stall` = actual execution state change (value is now STALLED)

### 5.2 `execution.fix`

Recorded fix to be applied (input to execution).

```json
{
  "v": 2,
  "type": "execution.fix",
  "i": <contiguous_index>,
  "t": "<rule_id>",
  "mu": {
    "transform": "<transformation spec>",
    "target_hash": "<hash of value to fix>"
  }
}
```

### 5.3 `execution.fixed`

Confirmation that fix was applied (output from execution).

```json
{
  "v": 2,
  "type": "execution.fixed",
  "i": <contiguous_index>,
  "t": "<rule_id>",
  "mu": {
    "before_hash": "<hash before>",
    "after_hash": "<hash after>"
  }
}
```

---

## 6. Execution Modes

### 6.1 Replay Mode (Primary)

Trace contains both stalls and fixes. Execution replays:

```
Input Trace:
  trace.start
  step (reduce...)
  execution.stall    <- value stalled here
  execution.fix      <- fix recorded in trace
  execution.fixed    <- confirmation
  step (continue...)
  trace.end

Execution: Reads fix from trace, applies it, continues.
```

This is deterministic: same trace → same execution.

### 6.2 Record Mode (Future)

Execution runs, stalls occur, fixes are provided externally and recorded:

```
Execution runs...
  Value stalls (pattern mismatch)
  External fix provided → recorded as execution.fix
  Execution continues...
Output: Complete trace with stalls + fixes
```

**v0 scope**: Replay mode only. Record mode deferred.

---

## 7. Determinism Contract

All execution must satisfy `EntropyBudget.md`:

| Requirement | Enforcement |
|-------------|-------------|
| Fix sources are trace events | No external input in v0 |
| Stall conditions are structural | Pattern match only, no RNG |
| Value hashes are deterministic | Canonical JSON hash |
| Event ordering is deterministic | Contiguous indices |

### 7.1 Value Hashing

To reference values in trace without embedding full structure:

```python
def value_hash(mu: JsonValue) -> str:
    canonical = canon_event_json({"v": 1, "type": "_", "i": 0, "mu": mu})
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

This is deterministic because canonicalization is deterministic.

---

## 8. Error Conditions

### 8.1 Stall Without Fix

If execution stalls and no `execution.fix` event follows:

```
HALT_ERR("stalled at index {i} with no fix: {stall_reason}")
```

### 8.2 Fix Without Stall

If `execution.fix` event appears when not stalled:

```
HALT_ERR("fix at index {i} but value not stalled")
```

### 8.3 Fix Hash Mismatch

If `execution.fix.mu.target_hash` doesn't match current value:

```
HALT_ERR("fix target mismatch at index {i}: expected {target_hash}, got {actual_hash}")
```

---

## 9. Implementation Plan

### Phase 1: Schema + Validation
1. Add `execution.stall`, `execution.fix`, `execution.fixed` to v2 schema
2. Update `trace_canon.py` to validate new event types
3. No execution changes yet

### Phase 2: Minimal Execution
1. Add `value_state` to VM state model
2. Implement STALL opcode (sets status, emits event)
3. Implement FIX opcode (reads event, transforms, emits confirmation)
4. Create golden fixture: `tests/fixtures/traces_v2/stall_fix.v2.jsonl`

### Phase 3: Integration
1. Wire execution into reduction engine
2. Pattern match failure → STALL (when execution mode enabled)
3. Fix event → FIX transformation
4. Gate: execution replay produces identical output

---

## 10. Fixture Strategy

### 10.1 Minimal Fixture

```jsonl
{"v":2,"type":"trace.start","i":0,"mu":{"seed":"test"}}
{"v":2,"type":"step","i":1,"mu":{"value":{"op":"add","a":0,"b":1}}}
{"v":2,"type":"execution.stall","i":2,"mu":{"pattern_id":"add.succ","value_hash":"abc123"}}
{"v":2,"type":"execution.fix","i":3,"t":"add.zero","mu":{"transform":"identity","target_hash":"abc123"}}
{"v":2,"type":"execution.fixed","i":4,"t":"add.zero","mu":{"before_hash":"abc123","after_hash":"def456"}}
{"v":2,"type":"step","i":5,"mu":{"value":1}}
{"v":2,"type":"trace.end","i":6,"mu":{"result":1}}
```

### 10.2 Validation

Golden fixture must:
- Replay identically (diff-empty)
- Stall at expected point
- Fix with expected transformation
- Produce expected final value

---

## 11. Relationship to Other Docs

| Document | Relationship |
|----------|--------------|
| `BytecodeMapping.v0.md` | Extends with STALL/FIX opcodes |
| `StallFixObservability.v0.md` | Observability is debug-only; this is execution |
| `EntropyBudget.md` | All execution must comply |
| `MetaCircularReadiness.v1.md` | This unblocks Gate 5 |

---

## 12. Open Questions

These require decision before implementation:

### Q1: Transform Specification

How is the transformation in `execution.fix` specified?
- **Option A**: Rule ID only (look up rule, apply it)
- **Option B**: Explicit before/after values
- **Option C**: Transformation DSL

**Recommendation**: Option A (rule ID) for v0. Keeps traces small, rules are already defined.

### Q2: Multiple Stalls

What if reduction would stall multiple times before reaching fix?
- **Option A**: One stall at a time (serialize)
- **Option B**: Batch stalls, batch fixes
- **Option C**: Defer to v1

**Recommendation**: Option A for v0. Single-value focus.

### Q3: Partial Reduction

If a compound value has one part that stalls, what happens to other parts?
- **Option A**: Whole value stalls
- **Option B**: Partial reduction continues
- **Option C**: Defer to v1

**Recommendation**: Option A for v0. Simplest semantics.

---

## 13. Success Criteria

VECTOR #6 is considered complete when:

1. `execution.stall`, `execution.fix`, `execution.fixed` events defined in v2 schema
2. STALL and FIX opcodes implemented in VM
3. Golden fixture passes replay gate (diff-empty)
4. Execution mode flag (`RCX_EXECUTION_V0=1`) gates the feature
5. v1 replay gates remain green (no regression)
6. `MetaCircularReadiness.v1.md` Gate 5 can be marked PASS

---

## Version

Document version: v0 (draft)
Last updated: 2026-01-24
Status: AWAITING APPROVAL
Dependencies:
- `docs/BytecodeMapping.v0.md`
- `docs/StallFixObservability.v0.md`
- `docs/schemas/rcx-trace-event.v2.json`
- `EntropyBudget.md`
