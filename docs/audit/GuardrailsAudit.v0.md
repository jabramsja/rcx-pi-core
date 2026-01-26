# Guardrails Audit v0

Status: REFERENCE (pre-implementation audit)

## Purpose

This document identifies ALL ways we could accidentally simulate RCX in Python rather than implement it as a structural substrate. Each gap must be closed before Phase 1 implementation.

---

## Current Guardrails (What We Have)

### Runtime Guardrails (mu_type.py)

| Function | Purpose | Status |
|----------|---------|--------|
| `is_mu()` | Check if value is JSON-compatible | ✅ |
| `validate_mu()` | Stricter JSON round-trip check | ✅ |
| `assert_mu()` | Fail-loud on non-Mu | ✅ |
| `has_callable()` | Detect functions/lambdas | ✅ |
| `assert_no_callables()` | Reject host functions | ✅ |
| `assert_seed_pure()` | Validate seed structure | ✅ |
| `assert_handler_pure()` | Wrap handlers for Mu in/out | ✅ |
| `validate_kernel_boundary()` | Validate primitive boundaries | ✅ |

### Static Guardrails (audit_semantic_purity.sh)

| Check | What It Catches | Status |
|-------|-----------------|--------|
| 1. Python types in traces | `<class 'X'>` leakage | ✅ |
| 2. Host closures in rules | Lambda in rule motifs | ✅ |
| 3. Non-portable builtins | eval/exec/compile | ✅ |
| 4. Non-JSON serialization | datetime/bytes/set | ✅ |
| 5. Opcode portability | Language-agnostic enum | ✅ |
| 6. Value hash portability | Uses hashlib.sha256 | ✅ |
| 7. Reserved opcode discipline | ROUTE/CLOSE blocked | ✅ |
| 8. Mu type guardrails | is_mu/assert_mu exist | ✅ |
| 9. Structural purity | has_callable/assert_seed_pure | ✅ |
| 10. Kernel purity | No lambdas in kernel | ✅ |
| 11. Seed purity | Seeds are JSON files | ✅ |

---

## Identified Gaps (Attack Vectors)

### GAP 1: Python Equality for Structural Matching

**Risk:** Using Python `==` to compare structures hides Python's type coercion.

```python
# DANGEROUS: Python coerces types
True == 1  # True in Python, but semantically different in Mu
[] == False  # False, but what if some edge case exists?
```

**Mitigation:** Compare via canonical JSON serialization, not Python `==`.

```python
def mu_equal(a: Mu, b: Mu) -> bool:
    """Structural equality via canonical serialization."""
    return (
        json.dumps(a, sort_keys=True, ensure_ascii=False) ==
        json.dumps(b, sort_keys=True, ensure_ascii=False)
    )
```

**Test:** `test_mu_equal_rejects_python_coercion`
**Audit:** Search for `==` on Mu values in kernel code

---

### GAP 2: isinstance Chains for Dispatch

**Risk:** Using Python isinstance/type() for pattern dispatch smuggles host semantics.

```python
# DANGEROUS: This is Python dispatch, not structural
if isinstance(mu, dict) and "add" in mu:
    return handle_add(mu)
elif isinstance(mu, dict) and "mul" in mu:
    return handle_mul(mu)
```

**Mitigation:** All dispatch must be via structural projection matching (seed responsibility).

**Test:** `test_kernel_has_no_isinstance_dispatch`
**Audit:** Grep for `isinstance` in kernel.py (only allowed in guardrails with `# guardrail` comment)

---

### GAP 3: Private Methods Bypassing Guardrails

**Risk:** Internal methods that don't validate Mu boundaries.

```python
# DANGEROUS: _internal doesn't validate
def _internal_transform(self, value):  # No assert_mu!
    return self._apply(value)

def public_api(self, value):
    assert_mu(value)  # Only public validates
    return self._internal_transform(value)
```

**Mitigation:**
1. No private methods in kernel (all paths validate)
2. Or: wrap ALL internal paths with validation

**Test:** `test_all_kernel_paths_validate_mu`
**Audit:** Grep for `def _` in kernel.py; each must document why it's safe

---

### GAP 4: Tests That Mock Guardrails

**Risk:** Tests that mock away validation create false positives.

```python
# DANGEROUS: Test passes but hides bugs
@patch('rcx_pi.mu_type.assert_mu')
def test_something(mock_assert):
    mock_assert.return_value = None  # Disabled!
    kernel.process(lambda x: x)  # Should fail, but doesn't
```

**Mitigation:** Ban mocking of guardrail functions.

**Test:** `test_no_guardrail_mocking` (meta-test)
**Audit:** Grep for `@patch.*mu_type` or `@patch.*assert_mu` in test files

---

### GAP 5: Python Control Flow for Projection Selection

**Risk:** Using Python if/elif/else to select which projection to apply.

```python
# DANGEROUS: Python choosing projection
def apply_projections(self, mu, projections):
    for proj in projections:
        if self._python_match(proj["pattern"], mu):  # Python doing matching!
            return proj["body"]
```

**Mitigation:**
- In Phase 1 (Python bootstrap): Document this as TEMPORARY
- In Phase 2+: EVAL_SEED does matching structurally
- Clear marker: `# BOOTSTRAP: Python matching (will be replaced by EVAL_SEED)`

**Test:** `test_phase1_matching_is_marked_bootstrap`
**Audit:** All pattern matching code must have BOOTSTRAP comment or be in seeds/

---

### GAP 6: Trace Theater (Pre-computed Traces)

**Risk:** Generating traces that look correct but don't reflect actual execution.

```python
# DANGEROUS: Pre-computed trace
def execute(self, mu):
    # Doesn't actually execute, just returns expected output
    return {"result": mu, "trace": HARDCODED_TRACE}
```

**Mitigation:**
1. Traces must be generated step-by-step during execution
2. Record mode generates from actual stall/fix events
3. Replay validates trace matches execution

**Test:** `test_trace_reflects_actual_execution` (inject deliberate error, see trace change)
**Audit:** No trace construction outside of record_trace() kernel primitive

---

### GAP 7: Error Handling Hiding Violations

**Risk:** try/except swallowing Mu validation errors.

```python
# DANGEROUS: Violation hidden
try:
    assert_mu(value)
except TypeError:
    pass  # Swallowed!
```

**Mitigation:**
1. Never catch TypeError/ValueError around Mu validation
2. If catching is necessary, must re-raise or log prominently

**Test:** `test_no_swallowed_mu_errors`
**Audit:** Grep for `except.*TypeError` and `except:` in kernel code

---

### GAP 8: Implicit Python Dict Ordering

**Risk:** Relying on Python 3.7+ dict insertion order for semantics.

```python
# POTENTIALLY DANGEROUS: Order-dependent
for key in mu.keys():  # Relies on insertion order
    process(key)
```

**Mitigation:** Always sort keys when order matters.

```python
for key in sorted(mu.keys()):  # Explicit order
    process(key)
```

**Test:** `test_processing_order_is_deterministic`
**Audit:** Check all dict iteration uses `sorted()` or documents why order doesn't matter

---

### GAP 9: String Operations for Pattern Semantics

**Risk:** Using Python string operations for pattern matching.

```python
# DANGEROUS: String-based matching
if pattern.startswith("add"):  # Not structural!
    return handle_addition(mu)
```

**Mitigation:** Patterns must be Mu structures, not strings with semantic meaning.

**Test:** `test_patterns_are_structural_not_string`
**Audit:** Search for `.startswith`, `.endswith`, `.split`, `in ` on pattern values

---

### GAP 10: Closures Capturing Mutable State

**Risk:** Python closures capturing variables that affect behavior non-deterministically.

```python
# DANGEROUS: Captured mutable state
counter = [0]
def my_handler(mu):
    counter[0] += 1  # Side effect!
    return {"count": counter[0], **mu}
```

**Mitigation:**
1. Handlers must be stateless (or state must be Mu passed explicitly)
2. assert_handler_pure validates Mu in/out but not statelessness

**NEW GUARDRAIL NEEDED:** `assert_handler_stateless()` or document that state is caller's responsibility

**Test:** `test_handler_purity_includes_no_captured_state`
**Audit:** Handlers defined in kernel must not reference outer scope variables

---

### GAP 11: Meta-Circular Illusion

**Risk:** Claiming self-hosting when Python is doing the actual pattern matching.

```
Claim: "RCX runs RCX"
Reality: Python runs EVAL_SEED which is just data, Python does all matching
```

**Mitigation:** Clear distinction between:
- **Phase 1**: Python kernel + Python matching (bootstrap)
- **Phase 2**: Python kernel + EVAL_SEED matching (intermediate)
- **Phase 3**: EVAL_SEED runs EVAL_SEED (true self-hosting)

**Proof:** Compare traces:
1. Python-EVAL trace
2. EVAL-EVAL trace
3. Must be identical to claim self-hosting

**Test:** `test_python_eval_matches_eval_eval` (Phase 3 gate)
**Audit:** Do not claim self-hosting until Phase 3 test passes

---

### GAP 12: Float Precision

**Risk:** Python float precision causing non-determinism.

```python
0.1 + 0.2 == 0.3  # False in Python!
```

**Mitigation:**
1. Document that floats may have precision issues
2. Consider: avoid floats in core semantics (use integers + rationals if needed)
3. Or: define canonical float handling (round to N decimals)

**Test:** `test_float_precision_is_documented_or_banned`
**Audit:** Search for float operations in kernel, document each

---

### GAP 13: Large Integer Overflow

**Risk:** Python arbitrary precision vs JSON number limits.

```python
big = 10**1000  # Valid in Python
json.dumps(big)  # May work in Python, may fail in other JSON parsers
```

**Mitigation:** Document integer bounds or validate.

**Test:** `test_large_integers_are_portable`
**Audit:** Consider adding integer bounds check to is_mu()

---

### GAP 14: None vs Missing Key Ambiguity

**Risk:** Python `None` vs missing dict key have different meanings.

```python
{"a": None}  # Key exists, value is null
{}  # Key doesn't exist
```

**Mitigation:** Document that these are semantically different in Mu.

**Test:** `test_none_value_differs_from_missing_key`
**Audit:** Document None handling in MuType.v0.md

---

### GAP 15: Unicode Normalization

**Risk:** Different Unicode representations of "same" string.

```python
"\u00e9" == "\u0065\u0301"  # é vs e+combining accent
# False in Python, but visually identical
```

**Mitigation:**
1. Document that strings are byte-identical, not visually normalized
2. Or: normalize all strings (NFC) on Mu boundary

**Test:** `test_unicode_strings_are_byte_identical`
**Audit:** Consider adding Unicode normalization to validate_mu()

---

## New Guardrails Needed

### 1. `mu_equal()` - Structural Equality

```python
def mu_equal(a: Mu, b: Mu) -> bool:
    """Compare Mu values via canonical JSON, not Python ==."""
    assert_mu(a, "mu_equal.a")
    assert_mu(b, "mu_equal.b")
    return (
        json.dumps(a, sort_keys=True) ==
        json.dumps(b, sort_keys=True)
    )
```

### 2. `assert_no_isinstance_dispatch()` - Static Check

Add to audit script: verify kernel doesn't use isinstance for dispatch.

### 3. Bootstrap Markers

All Python code that will be replaced by seeds must be marked:

```python
# BOOTSTRAP: Python matching (temporary, replaced by EVAL_SEED in Phase 2)
def _python_match(pattern, value):
    ...
```

### 4. Test for No Guardrail Mocking

Add meta-test that fails if any test mocks guardrail functions.

---

## Test Categories (Prevent False Positives)

### Category A: Positive Tests (Valid Mu)
- Test that valid Mu passes all checks
- Must NOT mock guardrails

### Category B: Negative Tests (Invalid Mu)
- Test that invalid Mu is rejected
- Must verify SPECIFIC error message (not just "raises")

### Category C: Boundary Tests
- Test exact boundary of what's Mu vs not
- `True` is Mu, but `1 == True` should still be distinguishable

### Category D: Round-Trip Tests
- Test that Mu survives JSON serialization
- Verify no information loss

### Category E: Integration Tests
- Test full kernel path with real Mu
- No mocking of any kind

### Category F: Audit Tests (Meta-Tests)
- Test that audit scripts exist and run
- Test that no guardrails are mocked in other tests

---

## Audit Checklist (Run Before Each Phase)

### Pre-Phase 1 Audit
- [ ] All guardrail functions have tests
- [ ] No isinstance dispatch in kernel code
- [ ] No bare except around Mu validation
- [ ] All dict iteration uses sorted() where order matters
- [ ] BOOTSTRAP markers on Python-only matching code
- [ ] No tests mock guardrail functions
- [ ] audit_semantic_purity.sh passes

### Pre-Phase 2 Audit
- [ ] All Phase 1 items
- [ ] EVAL_SEED is pure Mu (assert_seed_pure passes)
- [ ] Python matching code still has BOOTSTRAP markers
- [ ] Traces from Python-EVAL match EVAL-SEED execution

### Pre-Phase 3 Audit
- [ ] All Phase 2 items
- [ ] EVAL_SEED runs EVAL_SEED successfully
- [ ] Traces from Python-EVAL match EVAL-EVAL exactly
- [ ] Can remove BOOTSTRAP-marked code without breaking seeds

---

## Summary: What Could Go Wrong

| Risk | Current Protection | Gap? | Mitigation |
|------|-------------------|------|------------|
| Lambda in seed | `assert_seed_pure` | No | ✅ |
| Non-Mu type | `is_mu/assert_mu` | No | ✅ |
| Python == for matching | None | **YES** | Add `mu_equal()` |
| isinstance dispatch | Audit script | Partial | Strengthen audit |
| Private methods bypass | None | **YES** | No private methods in kernel |
| Test mocking guardrails | None | **YES** | Add meta-test |
| Python if/else dispatch | None | **YES** | BOOTSTRAP markers + doc |
| Pre-computed traces | None | **YES** | Generate from execution |
| Swallowed exceptions | None | **YES** | Audit for bare except |
| Dict order dependence | PYTHONHASHSEED | Partial | Use sorted() |
| String-based patterns | None | **YES** | Audit for string ops |
| Captured mutable state | None | **YES** | Document/audit |
| False self-hosting claim | None | **YES** | Phase 3 gate test |
| Float precision | None | **YES** | Document/restrict |
| Large integers | None | **YES** | Document bounds |
| None vs missing key | None | Partial | Document |
| Unicode normalization | None | **YES** | Document/normalize |

---

## Implementation Order

1. **Add `mu_equal()` to mu_type.py** - Structural equality
2. **Add meta-test for no guardrail mocking** - Prevent false positives
3. **Update audit script** - Check for isinstance dispatch, string patterns, bare except
4. **Add BOOTSTRAP markers** - Document temporary Python code
5. **Document float/integer/unicode handling** - Update MuType.v0.md
6. **Create Phase 1 audit checklist test** - Automated pre-implementation check

---

## Version

Document version: v0
Last updated: 2026-01-25
