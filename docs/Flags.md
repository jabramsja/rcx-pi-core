# RCX Feature Flags

**Purpose:** Document flag semantics so no test suite run depends on flags implicitly.

---

## Flag Inventory

| Flag | Default | Purpose |
|------|---------|---------|
| `RCX_TRACE_V2` | `0` (OFF) | Enable v2 observability events |
| `RCX_EXECUTION_V0` | `0` (OFF) | Enable v0 execution/record mode |
| `PYTHONHASHSEED` | (unset) | Python hash randomization seed |

---

## Flag Semantics

### RCX_TRACE_V2=1

**Purpose:** Observability only.

**When ON:**
- `TraceObserver` emits `reduction.stall`, `reduction.applied`, `reduction.normal` events
- These are v2 events (`v=2` in JSON)
- No state changes; debug information only

**When OFF (default):**
- `TraceObserver` is a no-op
- No v2 observability events emitted
- v1 traces unchanged

**Test behavior:**
- Tests that require v2 observability must set this flag explicitly
- Default test runs do not depend on this flag

---

### RCX_EXECUTION_V0=1

**Purpose:** Execution/record mode.

**When ON:**
- `ExecutionEngine` tracks ACTIVE/STALLED state
- Emits `execution.stall`, `execution.fix`, `execution.fixed` events
- PatternMatcher calls `engine.stall()` on pattern mismatch
- PatternMatcher calls `engine.fixed()` when pattern matches a stalled value

**When OFF (default):**
- `ExecutionEngine` is a no-op (all methods return immediately)
- No execution events emitted
- PatternMatcher behavior unchanged from v1

**Test behavior:**
- Tests that require execution tracking must set this flag explicitly
- Default test runs do not depend on this flag

---

### PYTHONHASHSEED=0

**Purpose:** Deterministic Python hash ordering.

**When set to `0`:**
- Dictionary iteration order is deterministic
- Hash-based data structures are reproducible
- Required for trace determinism

**When unset:**
- Python randomizes hash seed on each run
- Traces may vary between runs (non-deterministic)

**Test behavior:**
- All fixture-based tests run with `PYTHONHASHSEED=0`
- CI enforces `PYTHONHASHSEED=0` for replay gates

---

## Default OFF Invariant

**Critical:** When all flags are OFF (default), behavior is unchanged from v1.

This means:
1. No v2 events are emitted
2. No execution state is tracked
3. v1 fixtures remain bit-for-bit identical
4. All v1 tests pass without modification

To verify:

```bash
# Default (no flags) - must pass
pytest tests/

# Explicit v1 only - must pass
RCX_TRACE_V2=0 RCX_EXECUTION_V0=0 pytest tests/
```

---

## Flag Combinations

| RCX_TRACE_V2 | RCX_EXECUTION_V0 | Behavior |
|--------------|------------------|----------|
| 0 | 0 | v1 only (default) |
| 1 | 0 | v1 + v2 observability (debug) |
| 0 | 1 | v1 + v2 execution (record mode) |
| 1 | 1 | v1 + v2 observability + v2 execution |

---

## Test Suite Flag Discipline

1. **v1 gate tests** (`test_replay_gate_idempotent.py`):
   - Run with default flags (no v2 behavior)
   - Verify v1 fixtures unchanged

2. **v2 gate tests** (`test_replay_gate_v2.py`):
   - Tests that need v2 behavior create engines/observers with `enabled=True`
   - Do not rely on environment variables being set
   - CI runs with `PYTHONHASHSEED=0` for determinism

3. **Fixture tests**:
   - v1 fixtures: `tests/fixtures/traces/*.v1.jsonl`
   - v2 fixtures: `tests/fixtures/traces_v2/*.v2.jsonl`
   - Naming convention enforces separation

---

## Version

Document version: v0
Last updated: 2026-01-24
