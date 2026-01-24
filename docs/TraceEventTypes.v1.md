# RCX Trace Event Types (v1)

**Status: DESIGN DOCUMENT**

This document defines the canonical trace event types for RCX v1. The trace event schema (`docs/schemas/rcx-trace-event.v1.json`) is generic and accepts any `type` string. This document specifies the semantic meaning of each event type.

---

## 1. Core Event Types (Frozen)

These event types are part of the frozen replay semantics (v1).

### 1.1 `trace.start`

Marks the beginning of a trace sequence.

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"trace.start"` |
| `i` | Yes | Must be 0 |
| `t` | Optional | Trace identifier/tag |
| `mu` | Optional | Initial state/seed |
| `meta` | Optional | Trace metadata |

### 1.2 `step`

Marks an intermediate step in execution.

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"step"` |
| `i` | Yes | Contiguous index > 0 |
| `t` | Optional | Step tag |
| `mu` | Optional | State after step |
| `meta` | Optional | Step metadata |

### 1.3 `trace.end`

Marks the end of a trace sequence.

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"trace.end"` |
| `i` | Yes | Final contiguous index |
| `t` | Optional | Trace identifier/tag |
| `mu` | Optional | Final state |
| `meta` | Optional | Trace metadata |

---

## 2. Engine Loop Event Types (Extension)

These event types extend v1 to trace the native engine loop: **Stall → Fix → Trace → Closure**.

### 2.1 `stall`

Emitted when pattern matching fails and a value cannot proceed.

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"stall"` |
| `i` | Yes | Contiguous index |
| `t` | Optional | Stall tag |
| `mu` | Optional | Stalled value |
| `meta` | Optional | Stall reason |

**`meta` conventions:**
```json
{
  "reason": "pattern_mismatch",
  "pattern": "<pattern_description>",
  "value": "<value_summary>"
}
```

### 2.2 `fix`

Emitted when a stalled value is fixed by routing to a bucket.

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"fix"` |
| `i` | Yes | Contiguous index |
| `t` | Optional | Fix tag |
| `mu` | Optional | Fixed value |
| `meta` | Optional | Fix details |

**`meta` conventions:**
```json
{
  "bucket": "r_null | r_inf | r_a | lobes | sink",
  "before": "<stalled_state>",
  "after": "<fixed_state>"
}
```

### 2.3 `closure`

Emitted when a closure completes (gate closes).

| Field | Required | Description |
|-------|----------|-------------|
| `v` | Yes | Schema version (1) |
| `type` | Yes | `"closure"` |
| `i` | Yes | Contiguous index |
| `t` | Optional | Closure tag |
| `mu` | Optional | Closure result |
| `meta` | Optional | Closure details |

**`meta` conventions:**
```json
{
  "gate": "<gate_identifier>",
  "inputs": <input_count>,
  "outputs": <output_count>
}
```

---

## 3. Trace Sequence Constraints

All traces must satisfy:

1. **Contiguity**: Event indices must be 0, 1, 2, ... n-1 in order
2. **Bookends**: First event should be `trace.start`, last should be `trace.end`
3. **Schema compliance**: All events must validate against `rcx-trace-event.v1.json`
4. **Determinism**: Same input must produce same trace (EntropyBudget.md)

---

## 4. Event Type Hierarchy

```
trace.start          (once, i=0)
  ├── step           (zero or more)
  ├── stall          (zero or more, engine loop)
  ├── fix            (zero or more, engine loop)
  ├── closure        (zero or more, engine loop)
  └── ...
trace.end            (once, i=n-1)
```

---

## 5. Replay Semantics

All event types are processed identically by replay:
1. Parse event JSON
2. Validate against schema
3. Canonicalize (key order, deep-sort)
4. Emit canonical JSON

Replay does NOT interpret event type semantics - it only validates structure and ensures determinism.

---

## 6. Implementation Status

| Event Type | Status | Emitted By |
|------------|--------|------------|
| `trace.start` | Implemented | Trace CLI |
| `step` | Implemented | Trace CLI |
| `trace.end` | Implemented | Trace CLI |
| `stall` | Defined | Not yet emitted |
| `fix` | Defined | Not yet emitted |
| `closure` | Defined | Not yet emitted |

---

## Version

Document version: v1
Last updated: 2026-01-24
Schema reference: `docs/schemas/rcx-trace-event.v1.json`
