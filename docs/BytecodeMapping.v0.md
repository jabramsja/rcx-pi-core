# RCX Bytecode Mapping (v0)

**Status: DESIGN DOCUMENT — No code changes.**

This document defines the mapping from frozen trace event schema (v1) to a minimal bytecode VM sufficient for deterministic replay. It does NOT extend the trace schema or add new execution semantics.

---

## 1. Goals

1. **Replay-only VM**: Execute `trace JSONL → VM ops → canonical outputs`.
2. **Bit-for-bit determinism**: Same trace input produces identical outputs (diff-empty).
3. **Minimal instruction set**: Only opcodes required to replay v1 trace events.
4. **Fail-loud on unmappable**: Any trace event that cannot be mapped must halt with explicit error.
5. **No semantic expansion**: VM must match frozen replay semantics exactly.

## 2. Non-Goals

1. **Stall/Fix/Closure semantics**: These are NOT traced in v1 schema. Reserved for future trace schema extension.
2. **Optimization**: Performance is not a v0 concern; correctness and determinism first.
3. **Meta-circular bootstrap**: Self-hosting requires bytecode → bytecode compilation (out of scope).
4. **Code generation**: v0 is replay-only; no synthesis of new traces.
5. **Interactive execution**: No REPL, debugger, or step-through (v0 is batch replay).

---

## 3. Minimal VM State Model

The VM maintains four state components:

### 3.1 Mu Store

```
mu_store: Map<Index, JsonValue>
```

A map from event index `i` to the mu payload. Deep-sorted at insertion time per EntropyBudget.md.

### 3.2 Buckets (Routing State)

```
buckets: {
  r_null: List<Ref>,   // Unresolved / null routing
  r_inf:  List<Ref>,   // Divergent / infinite
  r_a:    List<Ref>,   // Active / in-flight
  lobes:  List<Ref>,   // Lobe-local accumulation
  sink:   List<Ref>,   // Terminal / closed
}
```

**Note (v0)**: Buckets are declared but not modified by trace.start/step/trace.end events. Bucket operations are blocked pending stall/fix trace events (VECTOR #5 prerequisite).

### 3.3 Cursor

```
cursor: {
  i: Integer,          // Current event index (0-based, contiguous)
  phase: Enum(START, RUNNING, END, HALTED),
}
```

### 3.4 Artifacts

```
artifacts: {
  canon_out: String,   // Accumulated canonical JSONL output
  error: Option<String>,  // Error message if halted abnormally
}
```

---

## 4. Minimal Instruction Set (v0)

| Opcode | Args | Description |
|--------|------|-------------|
| `INIT` | — | Initialize VM state; set cursor.i = 0, cursor.phase = START |
| `LOAD_EVENT` | `ev: JsonValue` | Parse and validate event against v1 schema |
| `CANON_EVENT` | — | Canonicalize loaded event (key order, deep-sort mu/meta) |
| `STORE_MU` | — | Store mu payload at current cursor.i in mu_store |
| `EMIT_CANON` | — | Append canonical JSON line to artifacts.canon_out |
| `ADVANCE` | — | Increment cursor.i |
| `SET_PHASE` | `phase: Enum` | Set cursor.phase |
| `ASSERT_CONTIGUOUS` | `expected: Integer` | Fail if cursor.i != expected |
| `HALT_OK` | — | Set cursor.phase = END; return success |
| `HALT_ERR` | `msg: String` | Set cursor.phase = HALTED; record error; return failure |

### Reserved Opcodes (Not Implemented in v0)

These opcodes are reserved for future trace schema extension. They MUST NOT be implemented or emitted until the corresponding trace events are defined:

| Reserved Opcode | Blocked By |
|-----------------|------------|
| `STALL` | No stall trace events in v1 schema |
| `FIX` | No fix trace events in v1 schema |
| `ROUTE` | No bucket-routing trace events in v1 schema |
| `CLOSE` | No closure trace events in v1 schema |

---

## 5. Mapping Table: Trace Event Type → Op Sequence

### 5.1 `trace.start`

**Preconditions**: cursor.phase = START, cursor.i = 0

**Op Sequence**:
```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(0)
CANON_EVENT
STORE_MU
EMIT_CANON
SET_PHASE(RUNNING)
ADVANCE
```

### 5.2 `step`

**Preconditions**: cursor.phase = RUNNING, cursor.i > 0

**Op Sequence**:
```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(cursor.i)
CANON_EVENT
STORE_MU
EMIT_CANON
ADVANCE
```

### 5.3 `trace.end`

**Preconditions**: cursor.phase = RUNNING

**Op Sequence**:
```
LOAD_EVENT(ev)
ASSERT_CONTIGUOUS(cursor.i)
CANON_EVENT
STORE_MU
EMIT_CANON
HALT_OK
```

### 5.4 Unknown Event Type

**Op Sequence**:
```
HALT_ERR("unmappable event type: {type}")
```

---

## 6. Determinism Contract References

This VM MUST comply with `EntropyBudget.md`:

| Requirement | Enforcement |
|-------------|-------------|
| PYTHONHASHSEED=0 | CI environment |
| Dict key ordering | Deep-sort at CANON_EVENT |
| No RNG | No randomness in any opcode |
| No floats in trace | Schema validation at LOAD_EVENT |
| Contiguous indices | ASSERT_CONTIGUOUS |
| Canonical JSON output | EMIT_CANON uses frozen key order v→type→i→t→mu→meta |

### Fail-Loud Policy

The VM MUST halt with explicit error on:

1. **Schema violation**: event.v != 1, missing required fields, invalid types
2. **Contiguity violation**: event.i != expected
3. **Unmappable event type**: Any type not in {trace.start, step, trace.end}
4. **Entropy leak**: Any non-deterministic operation detected

Error messages MUST identify the failing event index and reason.

---

## 7. Untraced Semantics (Explicitly Deferred)

The following RCX semantics are NOT represented in v1 trace schema and are blocked from v0 VM implementation:

| Semantic | Status | Unblock Condition |
|----------|--------|-------------------|
| **Stall** (no-match) | UNTRACED | Add stall trace event type to schema |
| **Fix** (null/inf register) | UNTRACED | Add fix trace event type to schema |
| **Closure** (gate completion) | UNTRACED | Add closure trace event type to schema |
| **Bucket routing** | UNTRACED | Add routing trace event type to schema |

These are documented in TASKS.md VECTOR #5 as prerequisites.

---

## 8. Validation Criteria

A conforming v0 VM implementation MUST:

1. Accept all golden fixtures in `tests/fixtures/traces/*.v1.jsonl`
2. Produce output identical to Python `trace_canon.py` (diff-empty)
3. Reject traces with non-contiguous indices
4. Reject traces with unknown event types
5. Pass all replay gate tests

---

## Version

Document version: v0
Last updated: 2026-01-24
Trace schema reference: docs/schemas/rcx-trace-event.v1.json
Entropy contract reference: EntropyBudget.md
