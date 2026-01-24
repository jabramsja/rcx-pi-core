# Minimal Native Execution Primitive (v0)

**Status: COMPLETE**

This document answers the Boundary Question from TASKS.md.

---

## The Question

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

---

## The Answer

The minimal native execution primitive is the **Structural Reduction Loop**:

```
LOOP:
  1. MATCH: Apply pattern to value
  2. If match succeeds:
       REDUCE: Transform value via substitution
       TRACE: Emit execution.fixed (state transition)
       GOTO LOOP
  3. If match fails:
       STALL: Mark value as blocked
       TRACE: Emit execution.stall (state transition)
       AWAIT FIX (from trace stream)
       TRACE: Emit execution.fixed (state transition)
       GOTO LOOP
  4. If no patterns remain and value unchanged:
       NORMAL FORM detected
       TRACE: Emit trace.end (v1 event)
       HALT
```

This loop requires exactly three operations:
- **MATCH**: Structural equality test (pattern vs value)
- **REDUCE**: Substitution (bindings → body)
- **STALL**: Transition to blocked state (status = STALLED)

Normal form is **detected**, not commanded. There is no CLOSE opcode.
Everything else is trace emission (observation) or control flow.

**Terminology (v2 events):**
- `reduction.*` events = observability only (debug, no state change)
- `execution.*` events = actual state transitions (ACTIVE ↔ STALLED)

---

## Invariants

1. **Stall is the only blocking primitive.**
   No other operation may pause execution. If a value cannot reduce, it stalls.

2. **Fix must come from trace.**
   In replay mode, fixes are read from the trace stream. No external input.
   This ensures determinism.

3. **Closure is forced by repeated stall.**
   A value that stalls twice on the same pattern with no intervening reduction
   is in normal form. Closure is not optional—it is the structural consequence
   of exhausted reduction.

4. **Trace is append-only and total.**
   Every state transition emits an event. The trace is the complete execution history.

5. **No host semantics leak.**
   The loop operates on structure (μ) only. No strings, no numbers, no host types
   except as opaque leaves. Equality is structural. Substitution is structural.

---

## What This Uses (Existing Primitives)

| Primitive | Source | Status |
|-----------|--------|--------|
| `Motif` (μ) | `rcx_pi/core/motif.py` | Frozen |
| `PatternMatcher` | `rcx_pi/reduction/pattern_matching.py` | Frozen |
| `ExecutionEngine` | `rcx_pi/trace_canon.py` | v0 complete |
| `value_hash()` | `rcx_pi/trace_canon.py` | v0 complete |
| v2 trace events | `docs/schemas/rcx-trace-event.v2.json` | v0 complete |

No new primitives are required. The loop is a composition of existing parts.

---

## Non-Goals (Explicit)

1. **No new opcodes beyond STALL/FIX.**
   There is no CLOSE opcode—normal form is detected, not commanded.
   ROUTE, FORK, JOIN, and other multi-value operations are Sink-level.

2. **Single-value only (v0).**
   One value tracked through ACTIVE → STALLED → ACTIVE cycle.
   Multi-value / concurrent stalls are Sink-level.

3. **Replay-only (v0).**
   Fixes come from trace stream. No external input, no record mode.
   Record mode (external input → trace) is Sink-level.

4. **No bucket routing in v0.**
   The bucket model (r_null, r_inf, r_a, lobes, sink) is documentation.
   Actual routing is Sink-level.

5. **No partial reduction.**
   Compound values stall as a whole. Sub-structure reduction is Sink-level.

6. **No divergence detection.**
   r_inf bucket semantics (detecting infinite loops) are Sink-level.

7. **No meta-circular execution.**
   The loop runs in Python. Host-free execution is Sink-level.

---

## Normal Form Detection (Closure)

Normal form is **not** an explicit opcode. It is the observable consequence of:

```
value V stalls on pattern P
  → no fix available (or fix is identity)
  → V is in normal form with respect to P
  → if V stalls on ALL patterns, V is fully closed
```

The trace records this as:
- `execution.stall` (V stalled on P) — v2 event, state transition
- `trace.end` (V reached normal form) — v1 event, terminates trace

Normal form (closure) is structural inevitability, not a command.

---

## Relationship to Boundary Question

This document asserts:

> The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM) is the
> minimal host-independent execution primitive. All structural emergence flows
> through this loop. No other execution path is permitted.

Anything beyond this loop—routing, multi-value, external input, divergence
detection, meta-circularity—requires explicit promotion from Sink.

---

## Version

Document version: v0
Last updated: 2026-01-24
Status: DRAFT
Dependencies:
- `docs/StallFixExecution.v0.md`
- `docs/BytecodeMapping.v0.md`
- `TASKS.md` (Boundary Question)
