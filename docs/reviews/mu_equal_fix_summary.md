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

# mu_equal Binding Conflict Fix - Summary for Review

**Date:** 2026-01-31
**Branch:** feat/step5-enginenews-closure-detection

---

## What Was Requested

Eliminate inline `json.dumps` equality checks in `eval_seed.py` binding conflict detection, replacing with calls to the `mu_equal` bootstrap primitive.

The original proposal suggested a 9-file refactor with memoization and structural recursion.

---

## What Was Actually Done

**2-line fix + parity fuzzer.**

The 9-file refactor was over-engineered. After 9-agent review, the Expert agent identified that:
- `mu_equal` already exists as a bootstrap primitive
- It already uses `json.dumps(..., sort_keys=True)` internally
- The fix is simply: call the existing function instead of inlining its implementation

### Changes Made

**1. `rcx_pi/selfhost/eval_seed.py`** (3 edits)

```python
# Import (line 20)
- from .mu_type import Mu, assert_mu, is_mu, mark_bootstrap
+ from .mu_type import Mu, assert_mu, is_mu, mark_bootstrap, mu_equal

# List binding conflict (line 339)
- if json.dumps(bindings[k], sort_keys=True) != json.dumps(v, sort_keys=True):
+ if not mu_equal(bindings[k], v):

# Dict binding conflict (line 358)
- if json.dumps(bindings[k], sort_keys=True) != json.dumps(v, sort_keys=True):
+ if not mu_equal(bindings[k], v):
```

**2. `tests/test_mu_equal_parity_fuzzer.py`** (new file)

13 tests with 500+ Hypothesis-generated inputs proving:
- `mu_equal(a, b)` produces identical results to `json.dumps` comparison
- Non-linear pattern matching works correctly
- EngineNews closure detection (Rule 2.2) unaffected
- Edge cases covered (unicode, floats, empty structures, type sensitivity)

---

## Why This Approach

| Proposed (9-file) | Actual (2-line) |
|-------------------|-----------------|
| New structural recursion in mu_equal | Use existing json.dumps-based mu_equal |
| Memoization with id() | No memoization needed |
| 7+ new dependencies | Zero new dependencies |
| Risk of bool/int coercion bugs | Proven correct via fuzzer |
| Breaks L3 parity (JS has no id()) | Maintains L3 parity |

The key insight: **centralizing the call site is the win**, not reimplementing the function. When/if `mu_equal` implementation changes later, binding conflict detection automatically gets the update.

---

## L3 Parity Confirmed

JavaScript (`mu/host/js/eval_step.js`) already uses `muEqual` for binding conflicts:

```javascript
// Line 541 (list matching)
if (k in bindings && !muEqual(bindings[k], v)) {
  return NO_MATCH;
}

// Line 568 (dict matching)
if (bk in bindings && !muEqual(bindings[bk], bv)) {
  return NO_MATCH;
}
```

Python is now in parity with JavaScript.

---

## Test Results

```
Fast audit:     1405 passed
Parity fuzzer:    13 passed (500+ random inputs)
JS L3 tests:      All passed
```

All tests deterministic with `PYTHONHASHSEED=0`.

---

## Files to Review

| File | What to Look For |
|------|------------------|
| `rcx_pi/selfhost/eval_seed.py` | Lines 20, 339, 358 - the actual fix |
| `rcx_pi/selfhost/mu_type.py` | Lines 417-420 - mu_equal implementation |
| `tests/test_mu_equal_parity_fuzzer.py` | The proof of correctness |
| `mu/host/js/eval_step.js` | Lines 541, 568 - JS parity |
| `docs/core/Boot0Architecture.v0.md` | v0.4 spec updates |

---

## Phase 2 Proposal: Structural Recursion (DEFERRED)

An external reviewer proposed Phase 2: replace mu_equal's `json.dumps` with explicit structural recursion.

### 9-Agent Dialectic (2026-01-31)

| Agent | Verdict | Key Finding |
|-------|---------|-------------|
| **Verifier** | APPROVE | "Spec compliant with North Star. JS already uses structural recursion." |
| **Adversary** | NEEDS HARDENING | "Depth exceeded should raise ValueError, not return False." |
| **Expert** | DEFER | "4 lines → 40-60 lines with identical semantics. Not worth it." |
| **Structural-proof** | UNPROVEN | "Cannot find ONE example where json.dumps gives wrong answer." |
| **Grounding** | PARTIAL (10/12) | "3 missing tests, but existing coverage is strong." |
| **Fuzzer** | DESIGN COMPLETE | "40+ test methods ready for future implementation." |
| **Translator** | SCOPE CREEP | "Trading one set of Python dependencies for a different set." |
| **Visualizer** | Diagrams ready | "5 Mermaid diagrams showing type dispatch, depth guard, bool/int pitfall." |
| **Advisor** | DEFER | "Quick win not worth fighting for. json.dumps IS structural for JSON." |

### Why Phase 2 Was Rejected

**The core question:** Does replacing json.dumps with structural recursion help with self-hosting/meta-circular goals?

**Answer: NO.**

| Current (json.dumps) | Proposed (recursion) |
|---------------------|---------------------|
| Uses Python's json library | Uses Python's type(), isinstance(), == |
| 4 lines of code | 40-60 lines of code |
| Battle-tested, proven correct | New code, new bugs |
| Already has L3 parity | Requires JS changes for parity |
| **Both are bootstrap primitives using host mechanisms** |

**Structural-proof agent summary:**
> "json.dumps IS structural recursion over JSON data. Mu IS JSON by definition. Both approaches use host mechanisms. The change is cosmetic, not semantic. This is cargo cult structuralism."

### What Would Actually Help Self-Hosting

The L4 research question: **Can mu_equal become Mu projections?**

This would require comparison via pattern matching, e.g.:
```
projection: {"eq": [x, x]} → {"result": true}
projection: {"eq": [_, _]} → {"result": false}
```

Neither json.dumps NOR explicit recursion gets there. That's L4 research territory.

---

## Conclusion

**Phase 1 (DONE):** Centralize call site - inline json.dumps → call mu_equal. This was the real win.

**Phase 2 (DEFERRED):** Replace mu_equal internals with structural recursion. Not worth it:
- No semantic change (both produce identical results)
- No self-hosting benefit (still a bootstrap primitive)
- Adds complexity without adding correctness
- 9-agent consensus: "json.dumps IS structural for JSON data"

**L4 remains open:** Can mu_equal become projections? This is the real self-hosting question.
