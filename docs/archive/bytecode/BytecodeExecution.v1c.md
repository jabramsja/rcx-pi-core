# Bytecode Execution v1c: Value Storage (R0)

Status: VECTOR (design-only, no implementation until promoted to NEXT)

## Context

v1a/v1b implemented the stall/fix state machine with registers RS, RP, RH, RF. But these only track *hashes* and *status* - there's no actual value storage.

v1c-alpha adds R0: the register that holds the current value being reduced.

## Scope

**v1c-alpha (this doc):** R0 register and value loading
**v1c-beta (future):** OP_MATCH opcode
**v1c-gamma (future):** OP_REDUCE opcode

## Goals

1. Add R0 register to hold the current value (mu object)
2. Add `load_value()` method that sets R0 and computes RH
3. Validate that value storage integrates with existing state machine

## Non-goals

1. OP_MATCH (v1c-beta)
2. OP_REDUCE (v1c-gamma)
3. Pattern matching logic
4. Rule application logic
5. Execution loop

## Register Addition

| Register | Type | Purpose |
|----------|------|---------|
| R0 | Mu | Current value (JSON-compatible, see `docs/MuType.v0.md`) |

Existing: RS (status), RP (pattern_id), RH (value_hash), RF (fix target)

**Mu Type Constraint**: R0 holds only Mu values (JSON-compatible). This ensures:
1. Self-hosting readiness (no Python-specific types)
2. Portability (can be implemented in any language with JSON support)
3. Determinism (same value → same hash via `value_hash()`)

## API

```python
from rcx_pi.mu_type import Mu, assert_mu

@property
def value(self) -> Mu:
    """R0 register: Current value being reduced."""
    return self._r0

def load_value(self, value: Mu) -> str:
    """
    Load a value into R0 and compute its hash.

    Sets R0 = value and RH = hash(value).
    Returns the computed hash.

    This is the entry point for getting a value into the VM.
    Validates that value is a Mu (JSON-compatible) to ensure
    self-hosting readiness.
    """
    assert_mu(value, context="R0 register")  # Guardrail
    self._r0 = value
    self._rh = self._compute_hash(value)
    return self._rh

def _compute_hash(self, value: Mu) -> str:
    """Compute canonical hash of a value."""
    # Use existing value_hash from trace_canon
    # or implement here with same algorithm
    ...
```

## Integration with Existing Opcodes

| Opcode | R0 behavior |
|--------|-------------|
| OP_STALL | R0 unchanged (stall doesn't modify value) |
| OP_FIX | R0 unchanged (fix is declaration, not modification) |
| OP_FIXED | R0 updated to new value (caller provides after_value) |

Note: OP_FIXED already takes `after_value` as parameter. With R0, we can store it:

```python
def op_fixed(self, after_value: Any, after_hash: str) -> None:
    # ... existing validation ...
    self._r0 = after_value  # NEW: Store in R0
    self._rh = after_hash
    # ... rest unchanged ...
```

## Tests

1. `test_initial_value_is_none`: R0 starts as None
2. `test_load_value_sets_r0`: load_value stores the value
3. `test_load_value_computes_hash`: load_value sets RH correctly
4. `test_load_value_returns_hash`: load_value returns computed hash
5. `test_value_property_returns_r0`: value property works
6. `test_stall_preserves_value`: OP_STALL doesn't change R0
7. `test_fixed_updates_value`: OP_FIXED updates R0
8. `test_reset_clears_value`: reset() clears R0
9. `test_hash_determinism`: Same value → same hash
10. `test_hash_uses_canonical_form`: {a:1, b:2} == {b:2, a:1}

## Promotion Checklist (VECTOR → NEXT)

- [x] Decided: R0 type is `Any`
- [x] Decided: Use `value_hash` from trace_canon
- [ ] Resolve: Should load_value clear stall_memory?
- [ ] Scope: ~30 lines of code, ~10 tests

## Design Decisions

1. **Type of R0**: `Mu` (JSON-compatible value). Defined in `docs/MuType.v0.md` and validated by `rcx_pi/mu_type.py`. This ensures no Python-specific types leak into the VM, preserving self-hosting readiness.

2. **Hash function**: Reuse `value_hash` from `trace_canon.py`. Determinism requires the same hash function everywhere.

3. **Mu validation**: `load_value()` should call `assert_mu()` to fail-loud on invalid values. This is a guardrail, not a constraint on the execution model.

## Open Questions

1. **Stall memory**: Does load_value clear stall_memory? Initialization probably shouldn't, but mid-execution reload might. Needs clarification during implementation.

## What This Enables

Once R0 exists:
- v1c-beta can add OP_MATCH that examines R0
- v1c-gamma can add OP_REDUCE that transforms R0
- The VM has actual values, not just hashes
