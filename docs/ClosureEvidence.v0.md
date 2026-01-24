# Closure Evidence Events v0

Status: VECTOR (design-only, no implementation allowed)

This document defines the trace-level vocabulary for "closure evidence" events: observable signals that closure has become unavoidable, without implying any termination directive.

---

## Motivation / Problem Statement

IndependentEncounter.v0.md establishes when closure becomes unavoidable (second independent stall at same value_hash + pattern_id). However, it explicitly defers event emission:

> "Closure detection may only emit trace evidence. Any termination decision must be external and explicit."

We need a design-level spec for:
1. What observable evidence should exist when closure becomes unavoidable?
2. What vocabulary (event names, fields) should this evidence use?
3. How does this integrate with existing v2 trace semantics?

This document answers these questions without introducing engine opcodes or termination mechanics.

---

## Definitions

### Closure Evidence

A trace event asserting that closure has become unavoidable for a specific (value_hash, pattern_id) pair. This is an **observation**, not a **directive**.

### Unavoidable Closure

The state where no further reduction can change the outcome for a given value at a given pattern site. Detected via the "second independent encounter" rule (see IndependentEncounter.v0.md).

### Evidence Event

A v2 trace event produced by tooling, validators, or replay infrastructure to record an observation. Evidence events are:
- Derived from execution events (not primary)
- Produced externally to the engine execution loop
- Informational, not prescriptive

### Relationship to Independent Encounter

This document defines the **event vocabulary** for emitting closure evidence.
IndependentEncounter.v0.md defines the **detection rule** for when closure becomes unavoidable.

The detection rule is upstream; this vocabulary is downstream.

---

## Proposed Evidence Event (v2 vocabulary)

### Event: `evidence.closure`

A trace event signaling that closure has become unavoidable.

**Required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `v` | integer | Schema version (must be 2) |
| `type` | string | `"evidence.closure"` |
| `i` | integer | Trace index (position in event stream) |
| `mu.value_hash` | string | The value_hash at which closure was detected |
| `mu.pattern_id` | string | The pattern_id at which closure was detected |
| `mu.reason` | string | Detection reason (enum, see below) |

**Reason enum (v0):**

| Value | Meaning |
|-------|---------|
| `"second_independent_stall"` | Two stalls at same (value_hash, pattern_id) with no intervening value change |

**Optional fields:**

| Field | Type | Description |
|-------|------|-------------|
| `mu.first_seen_at` | integer | Trace index of the first stall that established the encounter |
| `mu.trigger_at` | integer | Trace index of the second stall that triggered evidence |

### Naming rationale

- Prefix `evidence.*` (not `execution.*`) to signal this is observational, not operational.
- Suffix `.closure` is specific and unambiguous.
- This avoids collision with any future `execution.close` or `route.*` opcodes.

### What about ROUTE/CLOSE?

The original SINK item mentioned "ROUTE/CLOSE opcodes." This document reframes that as:
- **ROUTE**: Not addressed here. Routing is a separate concern (multi-value, bucket selection).
- **CLOSE**: Renamed to `evidence.closure` to emphasize it is evidence, not an engine directive.

If/when ROUTE or CLOSE become engine opcodes, they will live in a separate spec (VECTOR → NEXT promotion). This document only covers **evidence vocabulary**.

---

## Invariants (Normative)

1. **Determinism**: Given the same execution event stream, the same `evidence.closure` events must be derivable.

2. **Derivability**: `evidence.closure` must be computable from the execution event stream alone. No private engine state required.

3. **Non-prescriptive**: Emitting `evidence.closure` does NOT imply the engine should stop. Termination policy is external.

4. **Idempotence**: If closure evidence is emitted for (v, p), re-running detection on the same stream must produce the same evidence at the same trace index.

5. **Alignment with IndependentEncounter.v0.md**: Detection rule must match the "second independent encounter" semantics exactly.

---

## Non-Goals (Explicit)

1. **Engine termination**: This document does NOT define what the engine should do after closure. No "stop" directive.

2. **Engine opcodes**: `evidence.closure` is NOT an opcode. It is a trace annotation.

3. **Routing semantics**: No ROUTE opcode or bucket-selection logic.

4. **Implementation**: No code changes. This is design-only.

5. **Validator enforcement**: Whether validators require or reject `evidence.closure` is out of scope for v0.

6. **Multi-value closure**: This spec assumes single-value execution. Multi-value is in SINK.

---

## Normative Examples

These examples show when `evidence.closure` SHOULD or SHOULD NOT appear. They use pseudo-JSONL for illustration; these are not fixtures.

### Example 1: SHOULD emit (second independent stall)

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"execution.stall","i":1,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"evidence.closure","i":2,"mu":{"pattern_id":"pA","value_hash":"v1","reason":"second_independent_stall","first_seen_at":0,"trigger_at":1}}
```

**Rationale**: Same (value_hash, pattern_id) stalled twice with no intervening reduction. Closure evidence emitted.

### Example 2: SHOULD NOT emit (intervening reduction)

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"execution.fixed","i":1,"mu":{"before_hash":"v1","after_hash":"v2","rule_id":"r1"}}
{"v":2,"type":"execution.stall","i":2,"mu":{"pattern_id":"pA","value_hash":"v1"}}
```

**Rationale**: The `execution.fixed` at i=1 cleared stall memory (before_hash == v1). The stall at i=2 is a fresh first encounter. No closure evidence.

### Example 3: SHOULD NOT emit (single stall)

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"pA","value_hash":"v1"}}
```

**Rationale**: Only one stall. Closure requires two independent encounters. No evidence.

### Example 4: SHOULD emit (different pattern does not reset)

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"execution.stall","i":1,"mu":{"pattern_id":"pB","value_hash":"v1"}}
{"v":2,"type":"execution.stall","i":2,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"evidence.closure","i":3,"mu":{"pattern_id":"pA","value_hash":"v1","reason":"second_independent_stall","first_seen_at":0,"trigger_at":2}}
```

**Rationale**: Stall at pB does not affect stall memory for pA. The third event matches the first at (v1, pA). Closure evidence emitted.

### Example 5: SHOULD NOT emit (value changed between stalls)

```jsonl
{"v":2,"type":"execution.stall","i":0,"mu":{"pattern_id":"pA","value_hash":"v1"}}
{"v":2,"type":"execution.stall","i":1,"mu":{"pattern_id":"pA","value_hash":"v2"}}
{"v":2,"type":"execution.stall","i":2,"mu":{"pattern_id":"pA","value_hash":"v1"}}
```

**Rationale**: The stall at i=1 overwrote stall_memory[pA] = v2. The stall at i=2 sees v1 != v2, so it is a fresh encounter. No closure evidence (even though v1 appeared before).

---

## Interaction with Replay Validation

This section is purely documentary (v0 does not mandate implementation).

**Potential integration points:**

1. **Post-replay annotation**: After replay completes, a validator could scan the execution stream and emit `evidence.closure` events as annotations.

2. **Inline during replay**: A replay engine could emit `evidence.closure` events inline as it detects them. This requires no engine changes, only replay tooling.

3. **Separate analysis pass**: A standalone tool could read a trace file and produce an augmented trace with evidence events appended.

**Validation modes (future):**

| Mode | Description |
|------|-------------|
| `--emit-evidence` | Produce `evidence.closure` events in output |
| `--require-evidence` | Fail if expected evidence is missing |
| `--ignore-evidence` | Skip evidence events during comparison |

These are suggestions for future CLI flags, not current implementation.

---

## Future Promotion (VECTOR → NEXT)

To promote this spec from VECTOR to NEXT, the following must be satisfied:

1. **Semantics locked**: The `evidence.closure` event shape and detection rule are finalized and reviewed.

2. **Bounded implementation scope**: Implementation is limited to:
   - A pure function `detect_closure_evidence(events) -> List[evidence.closure]`
   - Optional CLI flag `--emit-evidence`
   - No engine changes

3. **Tests focus on observability**: Tests verify that given input traces produce expected evidence events. No termination behavior tested.

4. **No termination policy implied**: Implementation must NOT add any "stop" behavior. Evidence is informational only.

5. **Alignment verified**: Tests confirm parity with IndependentEncounter.v0.md pathological scenarios.

---

## Appendix: Event Naming Alternatives Considered

| Name | Reason rejected |
|------|-----------------|
| `execution.closure` | Implies engine action, not observation |
| `execution.close` | Sounds like a directive |
| `closure.detected` | Acceptable but less compositional |
| `trace.closure` | Confuses trace metadata with evidence |
| `evidence.closure` | **Selected**: clear separation of concerns |
