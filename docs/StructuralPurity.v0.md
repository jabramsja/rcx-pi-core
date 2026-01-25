# Structural Purity Guardrails v0

Status: VECTOR (design-only)

## Purpose

Ensure we program IN RCX (using structure/Mu) rather than ABOUT RCX (using Python constructs). Without these guardrails, we risk simulating emergence rather than proving it.

## The Problem

It's easy to accidentally write:
```python
# BAD: Python lambda as handler
handlers["step"] = lambda mu: transform(mu)

# BAD: Python string as pattern
pattern = "add_zero"  # Should be structure!

# BAD: Python isinstance for matching
if isinstance(mu, dict) and mu.get("op") == "add":  # Host logic!
```

These are all "programming ABOUT RCX" - using Python to simulate what should be structural.

## The Rule

**Everything that flows through the kernel must be Mu.**

- Seeds are Mu
- Projections are Mu
- Handlers receive Mu, return Mu
- Patterns are Mu (not strings, not regexes)
- The kernel ONLY does: hash, compare hashes, append, dispatch

## What IS Allowed

### In Kernel (Python bootstrap only)

```python
# OK: Computing identity hash
def compute_identity(mu: Mu) -> str:
    assert_mu(mu)  # Guardrail
    return hashlib.sha256(json.dumps(mu, sort_keys=True).encode()).hexdigest()

# OK: Comparing hashes (strings, but just comparison)
def detect_stall(before: str, after: str) -> bool:
    return before == after

# OK: Appending to trace (trace is Mu)
def record_trace(entry: Mu) -> None:
    assert_mu(entry)  # Guardrail
    self._trace.append(entry)

# OK: Dispatching to handler
def gate_dispatch(event: str, context: Mu) -> Mu:
    assert_mu(context)  # Guardrail
    handler = self._handlers.get(event)
    result = handler(context)
    assert_mu(result)  # Guardrail on output too!
    return result
```

### In Seeds (must be pure Mu)

```python
# OK: Seed defined as Mu structure
EVAL_SEED = {
    "seed": {
        "id": "eval.v1",
        "projections": [
            {
                "id": "equal.same",
                "pattern": {"equal?": [{"var": "a"}, {"var": "a"}]},
                "body": True
            },
            {
                "id": "equal.diff",
                "pattern": {"equal?": [{"var": "a"}, {"var": "b"}]},
                "body": False
            }
        ]
    }
}
```

## What is NOT Allowed

### No Python functions in seeds

```python
# BAD: Lambda in seed
seed = {
    "handler": lambda mu: mu  # NOT MU!
}

# BAD: Function reference
seed = {
    "handler": my_python_function  # NOT MU!
}
```

### No Python logic for matching

```python
# BAD: Python isinstance
if isinstance(pattern, dict):  # Host logic!

# BAD: Python == for semantic equality
if pattern == input:  # Only OK for hash comparison

# BAD: Python string operations
if pattern.startswith("add"):  # NOT STRUCTURAL!
```

### No Python control flow in evaluation

```python
# BAD: Python if/else for pattern dispatch
if mu["op"] == "add":
    return handle_add(mu)
elif mu["op"] == "mul":
    return handle_mul(mu)

# This should be: try each projection structurally
```

### No host types leaking

```python
# BAD: Python set
patterns = {pattern1, pattern2}  # Set not Mu!

# BAD: Python tuple
result = (before, after)  # Tuple not Mu!

# BAD: Python None used semantically
if result is None:  # None IS Mu, but using Python's None semantics
```

## Guardrail Functions

### assert_mu (exists in mu_type.py)

```python
def assert_mu(value: Any, context: str = "value") -> None:
    """Fail-loud if value is not valid Mu."""
    if not is_mu(value):
        raise TypeError(f"{context} must be Mu, got {type(value).__name__}")
```

### assert_seed_pure (NEW)

```python
def assert_seed_pure(seed: Any, context: str = "seed") -> None:
    """
    Verify a seed is pure Mu with no host contamination.

    Checks:
    1. Seed is valid Mu
    2. No callable values anywhere in structure
    3. All projections have pattern and body, both Mu
    4. No Python-specific types
    """
    assert_mu(seed, context)
    _check_no_callables(seed, context)
    _check_projections(seed, context)
```

### assert_handler_pure (NEW)

```python
def assert_handler_pure(handler: Callable, name: str) -> Callable:
    """
    Wrap a handler to verify Mu in, Mu out.

    Returns wrapped handler that:
    1. Asserts input is Mu
    2. Calls original handler
    3. Asserts output is Mu
    """
    def wrapped(context: Mu) -> Mu:
        assert_mu(context, f"{name} input")
        result = handler(context)
        assert_mu(result, f"{name} output")
        return result
    return wrapped
```

## Audit Script Extensions

Extend `tools/audit_semantic_purity.sh` with new checks:

### Check 1: No lambdas in seed definitions

```bash
# Look for lambda in seed structures
if grep -n "lambda" rcx_pi/seeds/*.py rcx_pi/kernel.py 2>/dev/null; then
    echo "ERROR: Lambda found in seed/kernel code"
    FAILED=1
fi
```

### Check 2: All handlers wrapped with assert_handler_pure

```bash
# Handlers must be wrapped
if grep -n "handlers\[" rcx_pi/kernel.py | grep -v "assert_handler_pure"; then
    echo "ERROR: Unwrapped handler registration"
    FAILED=1
fi
```

### Check 3: No isinstance in evaluation paths

```bash
# isinstance is only OK in guardrails, not in evaluation
if grep -n "isinstance" rcx_pi/kernel.py rcx_pi/eval_seed.py 2>/dev/null | grep -v "# guardrail"; then
    echo "WARNING: isinstance outside guardrail context"
    WARNINGS=$((WARNINGS + 1))
fi
```

### Check 4: Seeds are loadable as JSON

```bash
# Seeds must be pure JSON (Mu)
for seed in seeds/*.json; do
    if ! python -c "import json; json.load(open('$seed'))"; then
        echo "ERROR: Seed $seed is not valid JSON"
        FAILED=1
    fi
done
```

## Boundary Definition

There is ONE place where Python touches Mu: the kernel primitives.

```
PYTHON WORLD          BOUNDARY              MU WORLD
─────────────────────────────────────────────────────
                         │
hashlib.sha256() ───────►│◄─────── compute_identity()
                         │
str == str ─────────────►│◄─────── detect_stall()
                         │
list.append() ──────────►│◄─────── record_trace()
                         │
dict.get() + call() ────►│◄─────── gate_dispatch()
                         │
─────────────────────────────────────────────────────
```

Python is allowed ONLY for these 4 primitives. Everything else must be Mu.

## Enforcement Levels

### Level 1: Runtime (assert_mu)
- Every kernel primitive validates input/output
- Fail-loud on violation

### Level 2: Static (audit script)
- Scan code for violations
- Run in CI before merge

### Level 3: Structural (seed format)
- Seeds stored as JSON files, not Python
- Forces pure Mu representation

## Test Cases for Guardrails

```python
def test_lambda_rejected():
    """Lambda in seed should fail."""
    bad_seed = {"handler": lambda x: x}
    with pytest.raises(TypeError):
        assert_seed_pure(bad_seed)

def test_function_rejected():
    """Function reference in seed should fail."""
    def my_func(x): return x
    bad_seed = {"handler": my_func}
    with pytest.raises(TypeError):
        assert_seed_pure(bad_seed)

def test_tuple_rejected():
    """Tuple in seed should fail."""
    bad_seed = {"pair": (1, 2)}
    with pytest.raises(TypeError):
        assert_seed_pure(bad_seed)

def test_valid_seed_accepted():
    """Pure Mu seed should pass."""
    good_seed = {
        "seed": {
            "id": "test",
            "projections": [
                {"pattern": {"a": 1}, "body": {"b": 2}}
            ]
        }
    }
    assert_seed_pure(good_seed)  # Should not raise
```

## Implementation Order

1. **Implement `assert_seed_pure()`** in `mu_type.py`
2. **Implement `assert_handler_pure()`** in `mu_type.py`
3. **Add tests** for both functions
4. **Extend audit script** with new checks
5. **Run audit** - should pass on current code
6. **Then** start kernel implementation with guardrails in place

## Open Questions

1. **Handler representation**: In Phase 1, handlers are Python functions (wrapped). In Phase 2+, how do we represent handlers as Mu? Projection IDs?

2. **Bootstrap exception**: The Python kernel is allowed to use Python. How do we clearly mark what's bootstrap vs. what's permanent?

3. **Error handling**: When assert_mu fails, what Mu value represents the error? Or do we just crash?

## Invariants

1. **Mu closure**: If you start with Mu and only use kernel primitives, you always have Mu
2. **No host leakage**: Python types cannot enter the Mu world
3. **Structural only**: All computation is structural transformation, not host interpretation
4. **Audit-enforced**: Static analysis catches violations before runtime

## Success Criteria

The guardrails are working when:
1. `assert_mu` is called on every kernel boundary
2. `assert_seed_pure` validates every seed before loading
3. `audit_semantic_purity.sh` passes with all new checks
4. We cannot accidentally introduce Python logic into evaluation
