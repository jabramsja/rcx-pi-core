# Trace Reading Primer (v0)

**Purpose:** Sanity-check any RCX trace in 60 seconds without guessing.

---

## 1. Trace Format

Every trace is a JSONL file (one JSON object per line). Each line is an **event**.

```
{"v":1,"type":"trace.start","i":0,"t":"seed-name"}
{"v":1,"type":"step","i":1,"mu":{"value":"..."}}
{"v":1,"type":"trace.end","i":2}
```

---

## 2. Required Fields

| Field | Meaning |
|-------|---------|
| `v` | Version: `1` = frozen v1 semantics, `2` = v2 extension |
| `type` | Event verb (see Section 3) |
| `i` | Contiguous index (0, 1, 2, ...). Must be in order, no gaps. |

## 3. Optional Fields

| Field | Meaning |
|-------|---------|
| `t` | Tag/label (rule ID, seed name, etc.) |
| `mu` | Payload (structured data specific to the event type) |
| `meta` | Debug metadata (ignored by replay) |

---

## 4. Event Verbs (What They Mean)

### v1 Events (frozen, always valid)

| Type | Verb | Meaning |
|------|------|---------|
| `trace.start` | START | Trace begins. `t` = seed name. |
| `step` | STEP | Reduction step occurred. `mu` = value snapshot. |
| `trace.end` | END | Trace complete. Value reached normal form. |

### v2 Observability Events (RCX_TRACE_V2=1)

| Type | Verb | Meaning |
|------|------|---------|
| `reduction.stall` | STALL (debug) | Pattern match failed. Debug only, no state change. |
| `reduction.applied` | APPLIED | Rule transformed value. Debug only. |
| `reduction.normal` | NORMAL | No rule matched. Debug only. |

### v2 Execution Events (RCX_EXECUTION_V0=1)

| Type | Verb | Meaning |
|------|------|---------|
| `execution.stall` | STALL | Value blocked. State: ACTIVE → STALLED. |
| `execution.fix` | FIX | Fix to be applied (in replay). |
| `execution.fixed` | FIXED | Fix applied. State: STALLED → ACTIVE. |

**Key distinction:**
- `reduction.*` = observability only (debug, no state change)
- `execution.*` = actual state transitions

---

## 5. Hashes: What They Mean

Hashes appear in `mu` for execution events:

| Hash Field | Meaning |
|------------|---------|
| `value_hash` | SHA-256 prefix (16 hex chars) of the stalled value |
| `before_hash` | Value hash before fix was applied |
| `after_hash` | Value hash after fix was applied |
| `target_hash` | Expected value hash for a fix (must match `value_hash`) |

**What you can ignore:** The actual hex digits. They're for machine verification.

**What matters:** `before_hash` must equal the preceding `value_hash`. If they don't match, the trace is invalid.

---

## 6. Reading a Trace: The 60-Second Method

1. **Check version:** `v=1` or `v=2`?
2. **Check indices:** Are `i` values contiguous (0, 1, 2, ...)?
3. **Find the verbs:** Look for `type` field. Read as: START, STALL, FIXED, END.
4. **Check hash continuity:** Does `before_hash` match preceding `value_hash`?
5. **Check termination:** Does it end with `trace.end` or a final `execution.stall`?

If all five checks pass, the trace is structurally valid.

---

## 7. Annotated Example: stall_fix.v2.jsonl

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"add.succ","value_hash":"787bdc0f2aa4b88b"}}
{"v":2,"type":"execution.fixed","i":1,"t":"add.zero","mu":{"after_hash":"a627cdef47d90beb","before_hash":"787bdc0f2aa4b88b"}}
```

**Reading:**

| Line | Verb | What happened |
|------|------|---------------|
| 0 | STALL | Value blocked on pattern `add.succ`. Hash: `787b...` |
| 1 | FIXED | Rule `add.zero` transformed value. Before: `787b...` → After: `a627...` |

**Validation:**
- Indices: 0, 1 (contiguous)
- Hash continuity: `before_hash` (787b...) = preceding `value_hash` (787b...)
- Result: Valid stall→fix cycle

---

## 8. Annotated Example: record_mode.v2.jsonl

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"projection.pattern_mismatch","value_hash":"6e28e861511cd677"}}
{"v":2,"type":"execution.fixed","i":1,"t":"projection.match","mu":{"after_hash":"d0bebd790075c05f","before_hash":"6e28e861511cd677"}}
```

**Reading:**

| Line | Verb | What happened |
|------|------|---------------|
| 0 | STALL | Projection pattern didn't match. Hash: `6e28...` |
| 1 | FIXED | Different projection matched. Before: `6e28...` → After: `d0be...` |

**Context:** This trace was *generated* by Record Mode (execution → trace), not replayed. It proves the pattern matcher correctly emits STALL on mismatch and FIXED when a later pattern matches the same value.

**Validation:**
- Indices: 0, 1 (contiguous)
- Hash continuity: `before_hash` (6e28...) = preceding `value_hash` (6e28...)
- Result: Valid stall→fix cycle

---

## 9. Common Errors

| Error | Cause |
|-------|-------|
| Non-contiguous `i` | Event missing or out of order |
| `before_hash` mismatch | Fix applied to wrong value |
| `execution.fixed` without `execution.stall` | Fix without preceding stall |
| Double `execution.stall` | Stalled while already stalled |

---

## 10. Quick Reference

```
v1 trace (minimal):
  trace.start → step* → trace.end

v2 execution trace:
  execution.stall → execution.fixed → ...

Valid terminations:
  - trace.end (normal form reached)
  - execution.stall at end (stalled, no fix available = normal form)
```

---

## Version

Document version: v0
Last updated: 2026-01-24
