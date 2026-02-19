<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-03
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Mu Type Definition v0

Status: IMPLEMENTED (rcx_pi/selfhost/mu_type.py, 58+ tests)

## Purpose

Define what a "mu" (value/motif) IS structurally, to ensure:
1. Self-hosting readiness (no Python-specific types)
2. Portability (can be implemented in any language)
3. Determinism (same value → same hash)

## Definition

A **Mu** is a value composed only of JSON-compatible primitive types, recursively:

```
Mu = None | bool | int | float | str | List[Mu] | Dict[str, Mu]
```

Equivalently, a Mu is any value that:
1. Can be serialized to JSON via `json.dumps()`
2. Can be deserialized from JSON via `json.loads()`
3. Round-trips identically: `json.loads(json.dumps(x)) == x`

## What IS a Mu

| Type | Example | Valid |
|------|---------|-------|
| None | `None` | ✅ |
| bool | `True`, `False` | ✅ |
| int | `42`, `-1`, `0` | ✅ |
| float | `3.14`, `-0.5` | ✅ |
| str | `"hello"`, `""` | ✅ |
| list | `[1, 2, 3]`, `[]` | ✅ |
| dict | `{"a": 1}`, `{}` | ✅ |
| nested | `{"x": [1, {"y": 2}]}` | ✅ |

## What is NOT a Mu

| Type | Example | Why Invalid |
|------|---------|-------------|
| function | `lambda x: x` | Not JSON-serializable |
| class | `class Foo: pass` | Not JSON-serializable |
| object | `MyClass()` | Not JSON-serializable |
| bytes | `b"hello"` | JSON uses strings, not bytes |
| set | `{1, 2, 3}` | JSON has no set type |
| tuple | `(1, 2)` | JSON has arrays, not tuples |
| complex | `3+4j` | JSON has no complex type |
| date | `datetime.now()` | Not a JSON primitive |

## Variable Sites (per RuleAsMotif.v0.md)

A special Mu structure for pattern matching:

```json
{"var": "<name>"}
```

This is still a valid Mu (a dict with a string value), but has semantic meaning in patterns.

## Relationship to Existing Code

| Component | How it uses Mu |
|-----------|----------------|
| `value_hash()` | Serializes Mu to canonical JSON, hashes it |
| Trace `mu` field | Contains Mu payloads |
| Rule motifs | Pattern and body are Mu structures |
| R0 register | Will hold Mu values |

## Validation Function

```python
def is_mu(value: Any) -> bool:
    """Check if a value is a valid Mu (JSON-compatible)."""
    if value is None:
        return True
    if isinstance(value, bool):  # Must check before int (bool is subclass of int)
        return True
    if isinstance(value, (int, float, str)):
        return True
    if isinstance(value, list):
        return all(is_mu(item) for item in value)
    if isinstance(value, dict):
        return (
            all(isinstance(k, str) for k in value.keys()) and
            all(is_mu(v) for v in value.values())
        )
    return False
```

## Guardrail: JSON Round-Trip Test

A stricter validation that catches edge cases:

```python
def validate_mu(value: Any) -> bool:
    """Validate that a value is a portable Mu."""
    try:
        serialized = json.dumps(value, sort_keys=True)
        deserialized = json.loads(serialized)
        # Must round-trip correctly
        return json.dumps(deserialized, sort_keys=True) == serialized
    except (TypeError, ValueError):
        return False
```

## Invariants

1. **Closure under operations**: Operations on Mu values produce Mu values
2. **Determinism**: `value_hash(mu)` is deterministic for any Mu
3. **Portability**: Any language with JSON support can represent Mu
4. **No host leakage**: Python-specific types cannot enter the Mu space

## Application to Kernel

All values flowing through the RCX kernel must be valid Mu:
1. Seeds load as Mu (JSON files in `mu/` directory)
2. Projections transform Mu to Mu
3. `assert_mu()` guardrails enforce boundaries

This ensures the system cannot accidentally become dependent on Python-specific features.

## Open Questions

None. The type is fully defined by JSON compatibility.

## Implementation

The Mu type validation is implemented in `rcx_pi/selfhost/mu_type.py`:
- `is_mu(value)` - Check if value is a valid Mu
- `validate_mu(value)` - Stricter JSON round-trip validation
- `assert_mu(value, context)` - Fail-loud guardrail for VM use
- `mu_type_name(value)` - Return Mu type name for debugging

The semantic purity audit (`tools/audit_semantic_purity.sh`) verifies these guardrails exist.

## Historical Implementation Notes

1. ~~Implement `is_mu()` and `validate_mu()` in `rcx_pi/selfhost/mu_type.py`~~ ✅
2. ~~Extend `audit_semantic_purity.sh` to check Mu type guardrails~~ ✅

All core Mu type functionality is implemented. See `rcx_pi/selfhost/mu_type.py`.
