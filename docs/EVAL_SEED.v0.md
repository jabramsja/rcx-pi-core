# EVAL_SEED Specification v0

Status: NEXT (Phase 2 - Python implementation)

## Purpose

Define EVAL_SEED - the foundational seed that knows how to:
1. Match patterns against Mu values
2. Apply projections (pattern → body transformation)
3. Select which projection to apply from a list

This is THE hard part. If EVAL_SEED is tractable, self-hosting follows.

## Semantic Question

**"What is the minimal set of operations needed to evaluate projections structurally?"**

We're NOT building a Lisp interpreter. We're building something simpler:
- Pattern = Mu
- Input = Mu
- If pattern matches input, produce body (with substitutions)

## Core Operations

### 1. Structural Match

```
match(pattern, input) → bindings | NO_MATCH
```

Match a pattern against input. Returns variable bindings if match, NO_MATCH otherwise.

#### Match Rules

| Pattern | Input | Result |
|---------|-------|--------|
| `null` | `null` | `{}` (empty bindings) |
| `true` | `true` | `{}` |
| `42` | `42` | `{}` |
| `"hello"` | `"hello"` | `{}` |
| `[a, b]` | `[1, 2]` | `match(a,1) ∪ match(b,2)` |
| `{"k": v}` | `{"k": 1}` | `match(v, 1)` |
| `{"var": "x"}` | anything | `{"x": anything}` |
| anything else | anything else | NO_MATCH |

Key insight: `{"var": "x"}` is the ONLY special form. Everything else is literal matching.

### 2. Substitute

```
substitute(body, bindings) → Mu
```

Replace variable sites in body with bound values.

```
substitute({"var": "x"}, {"x": 42}) → 42
substitute([1, {"var": "x"}], {"x": 2}) → [1, 2]
substitute({"a": {"var": "x"}}, {"x": [1,2]}) → {"a": [1,2]}
```

### 3. Apply Projection

```
apply(projection, input) → Mu | NO_MATCH

where projection = {"pattern": P, "body": B}
```

Implementation:
```
bindings = match(P, input)
if bindings == NO_MATCH:
    return NO_MATCH
return substitute(B, bindings)
```

### 4. Select & Apply

```
step(projections, input) → Mu

where projections = [proj1, proj2, ...]
```

Try each projection in order. Return first successful application.
If none match, return input unchanged (stall).

```
for proj in projections:
    result = apply(proj, input)
    if result != NO_MATCH:
        return result
return input  # stall
```

## EVAL_SEED as Handlers

EVAL_SEED provides handlers for kernel events:

### step handler

```python
def step_handler(context):
    mu = context["mu"]
    projections = get_projections()  # from seed config
    return step(projections, mu)
```

### stall handler

```python
def stall_handler(context):
    # For now: just return the stalled value
    # Later: could signal closure, retry, etc.
    return context["mu"]
```

### init handler

```python
def init_handler(context):
    # Load projections from seed config
    return context["mu"]
```

## Complexity Analysis

### Operations Count

| Operation | Complexity |
|-----------|------------|
| `match` | O(size of pattern) |
| `substitute` | O(size of body) |
| `apply` | O(pattern + body) |
| `step` | O(n * (pattern + body)) where n = # projections |

### Code Size Estimate (Python)

| Function | Lines |
|----------|-------|
| `match` | ~30 |
| `substitute` | ~15 |
| `apply` | ~10 |
| `step` | ~10 |
| Handlers | ~20 |
| **Total** | ~85 |

This is tractable.

## Test Plan

### match tests
- `test_match_null` - null matches null
- `test_match_bool` - true matches true, false matches false
- `test_match_int` - 42 matches 42
- `test_match_string` - "x" matches "x"
- `test_match_list` - [1,2] matches [1,2]
- `test_match_dict` - {"a":1} matches {"a":1}
- `test_match_var` - {"var":"x"} matches anything
- `test_match_nested_var` - [{"var":"x"}, {"var":"y"}] matches [1, 2]
- `test_match_fail_type` - 1 doesn't match "1"
- `test_match_fail_length` - [1] doesn't match [1,2]

### substitute tests
- `test_sub_no_vars` - {a:1} unchanged
- `test_sub_single_var` - {"var":"x"} with {"x":1} → 1
- `test_sub_nested_var` - [1, {"var":"x"}] with {"x":2} → [1, 2]
- `test_sub_multiple_vars` - [{"var":"x"}, {"var":"y"}] with {"x":1, "y":2} → [1, 2]

### apply tests
- `test_apply_match` - pattern matches, body returned
- `test_apply_no_match` - pattern doesn't match
- `test_apply_with_substitution` - variables substituted in body

### step tests
- `test_step_first_match` - first matching projection applied
- `test_step_second_match` - first doesn't match, second does
- `test_step_no_match` - none match, input returned (stall)

### Integration tests
- `test_kernel_with_eval_seed` - full loop with EVAL_SEED handlers
- `test_countdown_with_projections` - countdown to zero
- `test_add_with_projections` - simple addition via projections

## Non-Goals (Phase 2)

- No unification (bidirectional matching)
- No higher-order patterns (pattern matching on patterns)
- No recursive patterns
- No special forms beyond `{"var": ...}`

These can be added in later versions if needed.

## Example: Countdown

```python
projections = [
    # Zero case: stall
    {
        "pattern": {"n": 0},
        "body": {"n": 0}
    },
    # Positive case: decrement
    {
        "pattern": {"n": {"var": "x"}},
        "body": {"n": {"sub": [{"var": "x"}, 1]}}  # need arithmetic...
    }
]
```

**Problem**: This requires arithmetic (`sub`). Pure structural matching can't compute.

**Solution options**:
1. **Peano numerals**: 3 = {"succ": {"succ": {"succ": "zero"}}}
2. **Pre-computed tables**: explicit projection for each number
3. **Kernel primitive for arithmetic** (violates "everything is structure")

Let's use Peano numerals for Phase 2 (pure structural).

## Example: Countdown with Peano

```python
# Representation: 0 = "zero", 1 = {"succ": "zero"}, 2 = {"succ": {"succ": "zero"}}

projections = [
    # Base case: zero stalls
    {
        "pattern": "zero",
        "body": "zero"
    },
    # Recursive case: unwrap succ
    {
        "pattern": {"succ": {"var": "n"}},
        "body": {"var": "n"}
    }
]

# Input: {"succ": {"succ": "zero"}} (= 2)
# Step 1: matches succ, returns {"succ": "zero"} (= 1)
# Step 2: matches succ, returns "zero" (= 0)
# Step 3: matches zero, returns "zero" (stall)
```

This works. Pure structural, no arithmetic.

## Phase 2 Deliverables

1. `rcx_pi/eval_seed.py` - EVAL_SEED implementation (~100 lines)
2. `tests/test_eval_seed_v0.py` - Tests (~40 tests)
3. Update `tools/audit_semantic_purity.sh` if needed

## Promotion Checklist (Phase 2 → Phase 3)

- [ ] All tests pass
- [ ] Countdown example works
- [ ] At least one non-trivial example works (e.g., list append)
- [ ] Complexity is tractable (< 200 lines)
- [ ] No host language leakage (pure Mu in/out)
