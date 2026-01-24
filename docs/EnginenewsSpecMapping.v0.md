# Enginenews Spec Mapping v0

Status: VECTOR (design-first, no code changes to engine)

This document defines a minimal "enginenews" motif set and describes intended behavior purely in terms of TRACE EVIDENCE. It serves as a stress-test specification for the RCX v2 replay pipeline.

**This spec does not introduce ROUTE/CLOSE or termination policy. It constrains observable evidence only.**

---

## 1. Purpose

The enginenews spec exercises the public CLI replay path (`--check-canon`, `--print-exec-summary`) using adversarial but valid v2 execution traces. It validates that:

- Replay accepts valid sequences and rejects invalid ones
- Execution summaries are deterministic
- Metrics can be derived purely from trace events without engine access

---

## 2. Motif Set (Semantic Labels)

These labels categorize fixture behavior. They are test annotations, not engine semantics.

| Motif | Description | Trace Pattern |
|-------|-------------|---------------|
| `news.pending` | Unresolved item awaiting reduction | `execution.stall` with no subsequent `fixed` |
| `news.refined` | Item successfully reduced | `execution.stall` → `execution.fixed` |
| `news.cycling` | Oscillating between stall states | Multiple stalls at different patterns |
| `news.terminal` | Closure evidence detected | Same `(value_hash, pattern_id)` stalls twice |

---

## 3. Metrics (Derived from Events Only)

All metrics are computed from the trace event stream. No engine internals are accessed.

### 3.1 Event Counts

```
stall_count   = count of execution.stall events
fix_count     = count of execution.fix events
fixed_count   = count of execution.fixed events
```

### 3.2 Stall Density

```
stall_density = stall_count / total_execution_events
```

Where `total_execution_events = stall_count + fix_count + fixed_count`.

High stall density indicates pressure; low density indicates smooth refinement.

### 3.3 Closure Evidence Count

Computed per `docs/IndependentEncounter.v0.md`:

- Maintain `stall_memory[pattern_id] = value_hash` for each `execution.stall`
- On `execution.stall(value_hash=v, pattern_id=p)`:
  - If `stall_memory[p] == v`: closure evidence for `(v, p)`
  - Else: `stall_memory[p] = v`
- On `execution.fixed(before_hash=b, ...)`:
  - Clear any `stall_memory` entries where value == b (conservative reset)

```
closure_evidence_count = number of (value_hash, pattern_id) pairs with closure evidence
```

### 3.4 Fix Efficacy

```
effective_fixes = count of execution.fixed where after_hash != before_hash
fix_efficacy    = effective_fixes / fixed_count  (0.0 if fixed_count == 0)
```

A fix is "effective" if it actually changes the value. Idempotent fixes (same hash) count as ineffective.

---

## 4. Expected Behaviors (Trace Evidence)

### 4.1 Progressive Refinement

- Pattern: `stall` → `fix` (optional) → `fixed` → ends ACTIVE
- Metrics: `stall_density < 0.5`, `fix_efficacy > 0`, `closure_evidence_count == 0`
- Interpretation: Value was reduced successfully; no stall pressure.

### 4.2 Oscillation / Stall Pressure

- Pattern: `stall` → (no fixed before end)
- Metrics: `stall_density == 1.0`, `fixed_count == 0`, `closure_evidence_count == 0`
- Interpretation: Value could not be reduced; normal form by exhaustion.

### 4.3 Closure Evidence

- Pattern: `stall(v, p)` → ... → `stall(v, p)` with no intervening `fixed(before=v, ...)`
- Metrics: `closure_evidence_count > 0`
- Interpretation: Second independent encounter detected; closure is observable.

---

## 5. Fixture Requirements

Each fixture must:

1. Contain only v2 execution events (`execution.stall`, `execution.fix`, `execution.fixed`)
2. Form a valid execution sequence per `validate_v2_execution_sequence()`
3. Be minimal (2-6 events)
4. Have a clear expected `final_status` (ACTIVE or STALLED)
5. Have deterministic metric values

---

## 6. CLI Contract

The stress-test harness invokes:

```bash
python3 -m rcx_pi.rcx_cli replay --trace <fixture> --check-canon --print-exec-summary
```

Expected:
- Exit code 0 for valid fixtures
- JSON summary on stdout (last `{...}` line)
- Deterministic output across repeated runs

---

## 7. Non-Goals

- Defining engine termination policy
- Introducing ROUTE/CLOSE opcodes
- Modifying trace schema
- Adding new event types
- Performance optimization

---

## Version

Document version: v0
Last updated: 2026-01-24
Dependencies:
- `docs/IndependentEncounter.v0.md` (closure evidence semantics)
- `docs/BytecodeMapping.v1.md` (execution event definitions)
- `rcx_pi.replay_cli` (public CLI interface)
