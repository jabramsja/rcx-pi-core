# Stall/Fix Trace Observability (v0)

**Status: DESIGN NOTE — Not approved for implementation**

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
| `t` | string | Rule tag (e.g. `"add.zero"`, `"activation"`, `"classify"`) |
| `mu` | object | Before/after summary (if cheap to compute) |
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

**Recommendation: (A) Schema v2 draft living alongside v1**

**Justification**:

1. **v1 replay gates remain untouched** — existing fixtures and CI gates do not see v2 events
2. **Single schema evolution path** — v2 extends v1 with new event types, same structure
3. **Clear versioning** — `"v": 2` distinguishes observer events from v1 replay events
4. **Future-compatible** — when stall/fix kernel semantics are provided, v2 is already in place
5. **Minimal tooling change** — same canonicalization, same JSONL format, just new event types

**Alternative rejected**: (B) "observer trace stream" would require parallel infrastructure and create file sprawl.

---

## 5. Implementation Plan (pending approval)

If approved, implementation would:

1. Add `v2` constant to `trace_canon.py` (alongside existing `v1`)
2. Add optional `observer` parameter to reduction functions
3. Emit events to observer callback (if provided)
4. Create ONE fixture: `tests/fixtures/traces/observer.v2.jsonl`
5. Add ONE test that validates observer events (separate from v1 replay gate)

**Estimated diff**: ~50-80 lines across 2-3 files.

---

## 6. Open Questions

1. Should `reduction.applied` include the transformed value in `mu`, or is that too expensive?
2. Should observer events be emitted to a separate stream, or interleaved with v1 events?
3. What is the maximum acceptable overhead for observer instrumentation?

---

## Version

Document version: v0
Last updated: 2026-01-24
Status: Awaiting review. Not approved for implementation.
