# RCX Bytecode Mapping (v0)

**Status: IMPLEMENTED**

**Implementation status:**
- ✅ Design doc complete (`docs/BytecodeMapping.v0.md`)
- ✅ BytecodeVM class: `rcx_pi/bytecode_vm.py`
- ✅ Tests: `tests/test_bytecode_vm_v0.py` (47 tests)
- ✅ Audit script: `tools/audit_bytecode.sh`
- ✅ All 10 v0 opcodes implemented with full test coverage
- ✅ Golden round-trip tests pass (4 v1 fixtures)
- ✅ Reserved opcode guard in place (STALL/FIX/ROUTE/CLOSE blocked)

This document defines the mapping from frozen trace event schema (v1) to a minimal bytecode VM sufficient for deterministic replay. It does NOT extend the trace schema or add new execution semantics.

---

## 1. Goals

1. **Replay-only VM**: Execute `trace JSONL → VM ops → canonical outputs`.
2. **Bit-for-bit determinism**: Same trace input produces identical outputs (diff-empty).
3. **Minimal instruction set**: Only opcodes required to replay v1 trace events.
4. **Fail-loud on unmappable**: Any trace event that cannot be mapped must halt with explicit error.
5. **No semantic expansion**: VM must match frozen replay semantics exactly.

## 2. Non-Goals

1. **Stall/Fix/Closure execution semantics**: Core engine loop is NOT implemented in v0. v2 observability events are debug-only.
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

These opcodes are reserved for future execution semantics. They MUST NOT be implemented until explicitly promoted from VECTOR:

| Reserved Opcode | Status | Notes |
|-----------------|--------|-------|
| `STALL` | Reserved | v2 observability available (`reduction.stall`) but execution semantics blocked |
| `FIX` | Reserved | v2 observability available (`reduction.applied`) but execution semantics blocked |
| `ROUTE` | Reserved | No bucket-routing execution in v0 |
| `CLOSE` | Reserved | No closure execution in v0 |

### Debug-Only Opcodes (v2 Observability)

These opcodes are for **debug/observability only** and do NOT affect v1 replay semantics. They are gated by `RCX_TRACE_V2=1` environment variable:

| Debug Opcode | v2 Event Type | Description |
|--------------|---------------|-------------|
| `DBG_STALL` | `reduction.stall` | Log pattern match failure (no state change) |
| `DBG_APPLIED` | `reduction.applied` | Log rule application with rule_id, before/after depth |
| `DBG_NORMAL` | `reduction.normal` | Log normal form reached (no rule matched) |

These debug opcodes:
- Do NOT modify VM state
- Do NOT affect canonical output
- Are stripped when `RCX_TRACE_V2=0` (default)
- Reference: `docs/StallFixObservability.v0.md`, `docs/schemas/rcx-trace-event.v2.json`

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

1. **Schema violation**: event.v not in {1, 2}, missing required fields, invalid types
2. **Contiguity violation**: event.i != expected
3. **Unmappable v1 event type**: Any v1 type not in {trace.start, step, trace.end}
4. **Entropy leak**: Any non-deterministic operation detected

Note: v2 events (reduction.stall, reduction.applied, reduction.normal) are debug-only and do not cause halt.

Error messages MUST identify the failing event index and reason.

---

## 7. Observability vs Execution Semantics

### v2 Observability (Debug-Only, Implemented)

The following are now OBSERVABLE via v2 trace events but do NOT have execution semantics in v0:

| Semantic | v2 Event | Status | Notes |
|----------|----------|--------|-------|
| **Stall** (no-match) | `reduction.stall` | Observable | Pattern match failure logged, no state change |
| **Applied** (rule fired) | `reduction.applied` | Observable | Rule ID + depth refs logged, no state change |
| **Normal** (no rule) | `reduction.normal` | Observable | Normal form logged, no state change |

Reference: `docs/StallFixObservability.v0.md`, `docs/schemas/rcx-trace-event.v2.json`

### Execution Semantics (Blocked, VECTOR)

The following execution semantics are NOT implemented in v0 and require explicit VECTOR promotion:

| Semantic | Status | Unblock Condition |
|----------|--------|-------------------|
| **Stall → Fix loop** | BLOCKED | VECTOR #6 promotion |
| **Bucket routing** | BLOCKED | VECTOR #6 promotion |
| **Closure completion** | BLOCKED | VECTOR #6 promotion |

These are documented in TASKS.md VECTOR #6.

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

Document version: v0.1 (aligned with v2 observability)
Last updated: 2026-01-24
Trace schema references:
- v1 (replay): `docs/schemas/rcx-trace-event.v1.json`
- v2 (observability): `docs/schemas/rcx-trace-event.v2.json`
Observability reference: `docs/StallFixObservability.v0.md`
Entropy contract reference: `EntropyBudget.md`
