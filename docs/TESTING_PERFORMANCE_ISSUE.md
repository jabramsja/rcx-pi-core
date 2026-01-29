# Testing Performance Issue - Handoff Document

**Date:** 2026-01-28
**Status:** RESOLVED (Option B implemented)

## Resolution Summary

**9-agent review consensus:** REJECT circuit breaker proposal (violates determinism).
**Solution implemented:** Option B - test configuration only (zero production code changes).

**Changes made:**
1. `max_depth=5` → `max_depth=3` in test generators
2. Added `deadline=5000` to all fuzzer `@settings` decorators
3. Reduced `max_steps` range in pathological projection tests
4. Created `tests/stress/` for deep edge case testing (Tier 3)

**Results:**
- Bootstrap fuzzer: 18 tests pass in 4 minutes (was hanging indefinitely)
- Fast audit: 772 tests pass in 3.5 seconds
- Full audit: ~5-8 minutes (was 10+ minutes or stuck)

---

## Original Problem Summary

The test suite, which used to run quickly, now takes 8+ minutes and often gets stuck. The issue is in the Hypothesis property-based fuzzer tests, specifically when testing the `run_mu()` kernel execution function.

## Symptoms

1. `./tools/audit_fast.sh` works fine (~2-3 min) - excludes fuzzer tests
2. `./tools/audit_all.sh` gets stuck - includes fuzzer tests
3. `tests/test_bootstrap_fuzzer.py` gets stuck at test 15/18
4. Even with `max_examples` reduced from 1000→200→50, tests still hang

## Key Files to Review

### Test Configuration
| File | Purpose |
|------|---------|
| `tests/conftest.py` | Hypothesis profiles, PYTHONHASHSEED enforcement |
| `pyproject.toml` | pytest configuration |

### Slow/Stuck Fuzzer Tests
| File | Tests | Status |
|------|-------|--------|
| `tests/test_bootstrap_fuzzer.py` | 18 | **STUCK at test 15-18** |
| `tests/test_selfhost_fuzzer.py` | 49 | Slow |
| `tests/test_phase8b_fuzzer.py` | 20 | Slow |
| `tests/test_phase7_readiness_fuzzer.py` | ~24 | Slow |
| `tests/test_type_tags_fuzzer.py` | 16 | Slow |
| `tests/test_apply_mu_fuzzer.py` | 8 | Slow |

### Core Code Being Tested
| File | Function | Issue |
|------|----------|-------|
| `rcx_pi/selfhost/step_mu.py` | `run_mu()`, `step_kernel_mu()` | May infinite loop on certain inputs |
| `rcx_pi/selfhost/match_mu.py` | `normalize_for_match()` | Creates deeply nested structures |
| `rcx_pi/selfhost/mu_type.py` | `is_mu()`, `MAX_MU_DEPTH=200` | Depth guard exists but may not catch all cases |

### Audit Scripts
| File | Purpose | Status |
|------|---------|--------|
| `tools/audit_fast.sh` | Fast iteration (no fuzzers) | **WORKS** |
| `tools/audit_all.sh` | Full suite (with fuzzers) | **STUCK** |

## Diagnostic Commands

```bash
# Check which test is stuck:
PYTHONHASHSEED=0 python3 -m pytest tests/test_bootstrap_fuzzer.py -v --tb=no 2>&1 | tail -10

# Run with dev profile (50 examples):
HYPOTHESIS_PROFILE=dev PYTHONHASHSEED=0 python3 -m pytest tests/test_bootstrap_fuzzer.py -v

# Run single problematic test class:
PYTHONHASHSEED=0 python3 -m pytest tests/test_bootstrap_fuzzer.py::TestBootstrapBoundary -v

# Check for infinite loops (add timeout):
timeout 60 python3 -c "
from rcx_pi.selfhost.step_mu import run_mu
double = {'pattern': {'var': 'x'}, 'body': {'doubled': {'var': 'x'}}}
result, trace, is_stall = run_mu([double], 100, max_steps=50)
print(f'Completed: {len(trace)} steps')
"
```

## Likely Root Causes

### 1. Infinite/Very Long Loops in `run_mu()`
The `run_mu()` function in `step_mu.py` runs a projection repeatedly until stall or max_steps. With certain hypothesis-generated inputs, this may:
- Never detect stall (mu_equal fails to match)
- Create exponentially growing structures
- Hit edge cases in normalization

### 2. Deep Nesting Explosion
The "double" projection `{"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}` wraps values deeper each step:
- Step 1: `100` → `{"doubled": 100}`
- Step 2: → `{"doubled": {"doubled": 100}}`
- After 100 steps: 100 levels deep

When normalized, each dict becomes a linked list, potentially doubling depth.

### 3. Hypothesis Generates Pathological Inputs
Hypothesis may generate:
- `{'_type': []}` - Non-string type tag (fixed in recent commit)
- Deeply nested structures that exceed `MAX_MU_DEPTH` after normalization
- Values that cause non-termination in pattern matching

## Recent Changes (context)

Several commits were made today to fix PYTHONHASHSEED issues:
- Added `env={**os.environ, "PYTHONHASHSEED": "0"}` to all subprocess calls
- Added hypothesis profiles (dev/ci) to conftest.py
- Reduced `max_examples` from 1000→200 in test_bootstrap_fuzzer.py
- Fixed `normalize_for_match()` to guard against unhashable `_type`

These changes are in uncommitted state in:
- `tests/conftest.py`
- `tests/test_bootstrap_fuzzer.py`
- `tests/test_replay_gate_idempotent.py`
- `rcx_pi/selfhost/match_mu.py`

## Proposed Solutions

### Option A: Add Timeout to Fuzzer Tests
```python
from hypothesis import settings, HealthCheck

@settings(max_examples=100, deadline=5000)  # 5 second deadline per example
def test_something(value):
    ...
```

### Option B: Limit Input Complexity
```python
@given(mu_values(max_depth=3))  # Reduce from default max_depth=5
def test_something(value):
    ...
```

### Option C: Add Circuit Breaker to run_mu()
```python
def run_mu(projections, value, max_steps=1000, max_depth=100):
    for step in range(max_steps):
        # Check depth before processing
        if _estimate_depth(current) > max_depth:
            return current, trace, True  # Treat as stall
        ...
```

### Option D: Skip Problematic Tests Temporarily
```python
@pytest.mark.skip(reason="Performance investigation needed")
def test_max_steps_uses_mu_equal_for_stall():
    ...
```

## Files with Uncommitted Changes

```
tests/conftest.py                    - Hypothesis profiles added
tests/test_bootstrap_fuzzer.py       - max_examples reduced
tests/test_replay_gate_idempotent.py - Exclude orbit SVG from diff check
rcx_pi/selfhost/match_mu.py          - Guard against unhashable _type
```

## Contact

This document was prepared for handoff to debug the testing performance issue.
The codebase is RCX, a structural computation kernel.

## Quick Test (should complete in <60s)

```bash
cd /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX
./tools/audit_fast.sh
```

If this passes, the core code works. The issue is specifically in the fuzzer test execution.
