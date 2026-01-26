# Stall/Fix Trace Observability (v0)

**Status: APPROVED FOR IMPLEMENTATION**

This document defines trace event types to make existing stall/fix-like behavior OBSERVABLE without changing execution semantics.

---

## 1. Scope

**Goal**: Observe what already happens in the reduction engine. No new semantics.

**Non-goals**:
- New execution models
- New closures/gates
- VM/bytecode work
- Changes to replay semantics v1

---

## 2. Proposed Trace Event Types

### 2.1 `reduction.stall`

Emitted when pattern matching fails and a value is returned unchanged.

**Emission point**: `rcx_pi/reduction/pattern_matching.py:62-64`
```python
if not self._match(pattern, value, bindings):
    # << EMIT reduction.stall HERE >>
    return value
```

**Required fields**:
| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Schema version |
| `type` | string | `"reduction.stall"` |
| `i` | int | Contiguous event index |

**Optional fields**:
| Field | Type | Description |
|-------|------|-------------|
| `mu` | object | `{"reason": "pattern_mismatch"}` |
| `meta` | object | `{"file": "pattern_matching.py", "line": 64}` |

**Canonicalization**: Same as v1 (key order, deep-sort mu/meta).

---

### 2.2 `reduction.normal`

Emitted when reduce() returns a value unchanged (no rule matched).

**Emission point**: `rcx_pi/reduction/rules_pure.py:109`
```python
# Nothing matched → normal form
# << EMIT reduction.normal HERE >>
return m
```

**Required fields**:
| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Schema version |
| `type` | string | `"reduction.normal"` |
| `i` | int | Contiguous event index |

**Optional fields**:
| Field | Type | Description |
|-------|------|-------------|
| `mu` | object | `{"reason": "no_rule_matched"}` |
| `meta` | object | `{"file": "rules_pure.py", "line": 109}` |

---

### 2.3 `reduction.applied`

Emitted when a reduction rule successfully applies and transforms a value.

**Emission points** (multiple):
- `rules_pure.py:58` — ADD with zero: `0 + b -> b`
- `rules_pure.py:62` — ADD with succ: `succ(n) + b -> succ(n + b)`
- `rules_pure.py:70` — MULT with zero: `0 * b -> 0`
- `rules_pure.py:74` — MULT with succ
- `rules_pure.py:82` — PRED with zero: `pred(0) -> 0`
- `rules_pure.py:85` — PRED with succ: `pred(succ(n)) -> n`
- `rules_pure.py:100` — ACTIVATION: closure application
- `rules_pure.py:106` — CLASSIFY: meta-classification

**Required fields**:
| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Schema version |
| `type` | string | `"reduction.applied"` |
| `i` | int | Contiguous event index |

**Optional fields**:
| Field | Type | Description |
|-------|------|-------------|
| `t` | string | Rule ID (e.g. `"add.zero"`, `"activation"`, `"classify"`) |
| `mu` | object | `{"rule_id": "...", "before_depth": N, "after_depth": M}` |
| `meta` | object | `{"file": "...", "line": N}` |

---

## 3. Determinism Contract

All new event types must satisfy `EntropyBudget.md`:

| Requirement | Enforcement |
|-------------|-------------|
| No RNG | Events are emitted deterministically based on structural matching |
| No timestamps | `meta.generated_at` forbidden in observer events |
| Sorted keys | Deep-sort all mu/meta objects |
| Contiguous indices | Observer stream maintains its own contiguous `i` |
| PYTHONHASHSEED=0 | CI enforces |

**Ordering**: Events emitted in reduction order (depth-first, left-to-right as traversal occurs).

---

## 4. Schema Approach

**Decision: (A) Schema v2 draft living alongside v1**

1. **v1 replay gates remain untouched** — existing fixtures and CI gates do not see v2 events
2. **Single schema evolution path** — v2 extends v1 with new event types, same structure
3. **Clear versioning** — `"v": 2` distinguishes observer events from v1 replay events
4. **Future-compatible** — when stall/fix kernel semantics are provided, v2 is already in place
5. **Minimal tooling change** — same canonicalization, same JSONL format, just new event types

---

## 5. Interleaving Strategy

**Decision**: v2 events interleaved in main trace with contiguous `i`.

- v1 and v2 events share the same index sequence
- Existing v1-only fixtures remain unchanged
- New traces with observability have interleaved v1+v2 events
- v1 replay gates continue to run on v1-only fixtures (untouched)

---

## 6. Payload Strategy

**Decision**: Include `rule_id` + before/after depth references (not full payloads).

| Field | Description |
|-------|-------------|
| `rule_id` | String identifier for the rule (e.g. `"add.zero"`, `"activation"`) |
| `before_depth` | Integer depth of input motif structure |
| `after_depth` | Integer depth of output motif structure |

This keeps overhead minimal while providing auditability.

---

## 7. Implementation Plan

1. Extend `trace_canon.py` to accept `v=1` or `v=2` (same canonicalization rules)
2. Add `TraceObserver` class for optional instrumentation
3. Modify `rules_pure.py` and `pattern_matching.py` to accept optional observer
4. Create ONE fixture: `tests/fixtures/traces/observer.v2.jsonl`
5. v1 replay gate remains untouched

---

## Version

Document version: v0
Last updated: 2026-01-24
Status: APPROVED FOR IMPLEMENTATION
