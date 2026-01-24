# RCX Bytecode Mapping (v1)

Status: VECTOR (design-first, no code changes)

This document promotes STALL and FIX from reserved (v0) to executable operations, and maps the MATCH/REDUCE/STALL/FIX primitives to bytecode-level ops.

---

## 1. Changes from v0

| Aspect | v0 | v1 |
|--------|----|----|
| STALL opcode | Reserved | Implemented |
| FIX opcode | Reserved | Implemented |
| MATCH opcode | Implicit | Explicit |
| Closure detection | External | Inline via independent encounter |
| State components | 4 (mu_store, buckets, cursor, artifacts) | 5 (adds stall_memory) |

v0 reference: `docs/BytecodeMapping.v0.md`

---

## 2. VM State Model (v1)

The VM maintains five state components:

### 2.1 Mu Store

```
mu_store: Map<Index, JsonValue>
```

Same as v0. Deep-sorted at insertion per EntropyBudget.md.

### 2.2 Value State

```
value_state: {
  current_hash: String,     // Hash of current value
  current_value: JsonValue, // Current value (for reduction)
}
```

New in v1. Tracks the live value being reduced.

### 2.3 Stall Memory

```
stall_memory: Map<PatternId, ValueHash>
```

New in v1. Tracks most recent stall at each pattern site. Used for independent encounter detection per `IndependentEncounter.v0.md`.

### 2.4 Cursor

```
cursor: {
  i: Integer,
  phase: Enum(START, RUNNING, STALLED, FIXING, END, HALTED),
}
```

Extended from v0. Adds STALLED and FIXING phases.

### 2.5 Artifacts

```
artifacts: {
  canon_out: String,
  error: Option<String>,
}
```

Same as v0.

---

## 3. Instruction Set (v1)

### 3.1 Replay Ops (from v0)

| Opcode | Args | Description |
|--------|------|-------------|
| `INIT` | — | Initialize VM state |
| `LOAD_EVENT` | `ev: JsonValue` | Parse and validate event |
| `CANON_EVENT` | — | Canonicalize loaded event |
| `STORE_MU` | — | Store mu payload |
| `EMIT_CANON` | — | Append canonical JSON line |
| `ADVANCE` | — | Increment cursor.i |
| `SET_PHASE` | `phase: Enum` | Set cursor.phase |
| `ASSERT_CONTIGUOUS` | `expected: Integer` | Fail if cursor.i != expected |
| `HALT_OK` | — | Return success |
| `HALT_ERR` | `msg: String` | Return failure |

### 3.2 Execution Ops (new in v1)

| Opcode | Args | Description |
|--------|------|-------------|
| `MATCH` | `pattern_id: String` | Attempt pattern match at current value |
| `STALL` | `pattern_id: String` | Record stall, check independent encounter |
| `FIX` | `fix_expr: JsonValue` | Apply fix expression to current value |
| `FIXED` | `before: Hash, after: Hash` | Confirm value transition, clear stall memory |
| `CHECK_CLOSURE` | `pattern_id: String` | Return true if closure detected at pattern |

### 3.3 Opcode Semantics

#### MATCH(pattern_id)

```
Preconditions: cursor.phase in {RUNNING, STALLED}
Side effects:
  - If pattern matches current_value: proceed to reduction
  - If pattern fails: emit STALL(pattern_id)
```

#### STALL(pattern_id)

```
Preconditions: MATCH just failed
Side effects:
  - v := value_state.current_hash
  - p := pattern_id
  - If stall_memory[p] == v:
      - Closure detected (second independent encounter)
      - SET_PHASE(END)
      - Return closure_detected = true
  - Else:
      - stall_memory[p] = v
      - SET_PHASE(STALLED)
      - Emit execution.stall event
```

#### FIX(fix_expr)

```
Preconditions: cursor.phase == STALLED
Side effects:
  - Apply fix_expr to value_state.current_value
  - Compute new hash
  - Emit execution.fix event
  - SET_PHASE(FIXING)
```

#### FIXED(before_hash, after_hash)

```
Preconditions: cursor.phase == FIXING
Validation:
  - Assert before_hash == value_state.current_hash (pre-fix)
  - Assert after_hash == hash(new_value)
Side effects:
  - value_state.current_hash = after_hash
  - value_state.current_value = new_value
  - Clear stall_memory (conservative reset per IndependentEncounter.v0.md)
  - Emit execution.fixed event
  - SET_PHASE(RUNNING)
```

#### CHECK_CLOSURE(pattern_id)

```
Preconditions: any
Side effects: none
Returns: true if stall_memory[pattern_id] == value_state.current_hash
```

---

## 4. State: Registers vs Trace

| State Component | Register | Trace |
|-----------------|----------|-------|
| `cursor.i` | Yes | No |
| `cursor.phase` | Yes | Derived from event sequence |
| `value_state.current_hash` | Yes | Emitted in execution.stall, execution.fixed |
| `value_state.current_value` | Yes | Not emitted (hash is sufficient) |
| `stall_memory` | Yes | Not emitted (derived from stall events) |
| `mu_store` | Yes | Derived from step events |
| `artifacts.canon_out` | Yes | Is the trace |

### 4.1 Derivability

All register state can be reconstructed from the trace:
- `cursor.i`: Count of events processed
- `cursor.phase`: Inferred from last event type
- `value_state.current_hash`: Tracked through execution.stall and execution.fixed events
- `stall_memory`: Rebuilt by replaying stall events and clearing on fixed events

This means: trace is authoritative, registers are cache.

---

## 5. Mapping: Trace Event → Op Sequence

### 5.1 execution.stall

```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(cursor.i)
STALL(ev.mu.pattern_id)
CANON_EVENT
EMIT_CANON
ADVANCE
```

### 5.2 execution.fix

```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(cursor.i)
FIX(ev.mu.fix_expr)
CANON_EVENT
EMIT_CANON
ADVANCE
```

### 5.3 execution.fixed

```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(cursor.i)
FIXED(ev.mu.before_hash, ev.mu.after_hash)
CANON_EVENT
EMIT_CANON
ADVANCE
```

### 5.4 v1 Events (trace.start, step, trace.end)

Same as v0. No execution ops involved.

---

## 6. Closure Detection Protocol

Per `IndependentEncounter.v0.md`, closure is detected when:

1. STALL(pattern_id) is invoked
2. stall_memory[pattern_id] == value_state.current_hash
3. No FIXED event occurred between the two stalls

The VM signals closure by:
- Setting cursor.phase = END
- Emitting trace.end (or closure-specific event if schema evolves)

### 6.1 Stall Memory Invariants

- On STALL: record (pattern_id → current_hash)
- On FIXED: clear all stall_memory (conservative reset)
- On trace.end: stall_memory is discarded

---

## 7. Determinism Constraints (carried from v0)

All v0 determinism constraints apply:

| Requirement | Enforcement |
|-------------|-------------|
| PYTHONHASHSEED=0 | CI environment |
| Dict key ordering | Deep-sort at CANON_EVENT |
| No RNG | No randomness in any opcode |
| No floats in trace | Schema validation at LOAD_EVENT |
| Contiguous indices | ASSERT_CONTIGUOUS |
| Canonical JSON output | EMIT_CANON uses frozen key order |

### 7.1 New in v1

| Requirement | Enforcement |
|-------------|-------------|
| Value hash determinism | value_hash() function per trace_canon.py |
| Stall memory reset | Clear on any FIXED (not partial invalidation) |
| Pattern ID stability | Must be stable across replay |

---

## 8. Fail-Loud Policy (extended from v0)

The VM MUST halt with explicit error on:

1. **Schema violation**: (same as v0)
2. **Contiguity violation**: (same as v0)
3. **Unmappable event type**: (same as v0)
4. **Entropy leak**: (same as v0)
5. **Hash mismatch**: execution.fixed before_hash != tracked current_hash
6. **Invalid phase transition**: e.g., FIX when not STALLED
7. **Stall without prior match**: STALL invoked without MATCH context

---

## 9. Still Reserved (not in v1)

| Opcode | Status | Notes |
|--------|--------|-------|
| `ROUTE` | Reserved | Bucket routing not in v1 scope |
| `CLOSE` | Reserved | Explicit closure event not required (implicit via stall memory) |

These remain deferred to SINK.

---

## 10. Validation Criteria

A conforming v1 VM implementation MUST:

1. Pass all v0 validation criteria
2. Accept execution.stall/fix/fixed events and update state correctly
3. Detect second independent encounter and signal closure
4. Produce output identical to Python reference (diff-empty)
5. Clear stall memory on any value transition

---

## Version

Document version: v1.0
Last updated: 2026-01-24
Dependencies:
- `docs/BytecodeMapping.v0.md` (base)
- `docs/IndependentEncounter.v0.md` (closure detection)
- `docs/schemas/rcx-trace-event.v2.json` (execution events)
- `EntropyBudget.md` (determinism)
