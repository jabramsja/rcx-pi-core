# Debt Categories v0

This document formalizes the distinction between **scaffolding debt** (acceptable infrastructure) and **semantic debt** (must become structural).

## Status: DESIGN (v0)

---

## Why This Matters

Self-hosting has three levels:
- **L1 (Algorithmic)**: Projections encode the algorithm (match/substitute as Mu) ✓ COMPLETE
- **L2 (Operational)**: RCX executes projections (kernel loop as Mu) - NEXT
- **L3 (Meta-circular)**: Kernel itself is projections - FUTURE

At L1, Python still runs the kernel loop. This creates ambiguity: which Python code is "acceptable scaffolding" and which is "semantic debt that smuggles emergence"?

This document answers that question.

---

## Two Categories

### 1. Scaffolding Debt (Acceptable)

Code that provides **execution infrastructure** but does not determine **what operations mean**.

**Criteria:**
- Runs fixed iterations (for-loop) but doesn't decide iteration count
- Dispatches to projections but doesn't interpret projection content
- Tracks resources (budget, depth) but doesn't affect semantics
- Provides I/O (file read, JSON parse) but doesn't interpret data

**Examples:**
| Code | Why Scaffolding |
|------|-----------------|
| `for i in range(max_steps)` | Fixed loop, doesn't decide projection order |
| `step(projections, state)` | Dispatches to seed, seed defines behavior |
| `budget.consume(n)` | Resource tracking, not semantic |
| `json.load(f)` | I/O boundary, doesn't interpret seed content |
| `threading.local()` | Thread isolation infrastructure |

**Key insight:** Scaffolding debt can be measured in LOC but doesn't affect emergence attribution. If we replaced Python's for-loop with Rust's, semantics would be identical.

### 2. Semantic Debt (Must Become Structural)

Code that **interprets Mu** or **determines what operations mean**.

**Criteria:**
- Traverses Mu and makes decisions based on content
- Implements operations that should be projections
- Uses Python conditionals to choose behavior based on Mu shape
- Creates new Mu based on interpreting existing Mu

**Examples:**
| Code | Why Semantic | Path to Structural |
|------|-------------|-------------------|
| `normalize_for_match()` | Traverses Mu, converts based on type | Normalization projection |
| `denormalize_from_match()` | Traverses Mu, reconstructs based on shape | Denormalization projection |
| `resolve_lookups()` | Interprets `{"lookup": x, "in": y}` marker | Lookup projection |
| `lookup_binding()` | Traverses linked list to find name | Part of lookup projection |
| `is_dict_linked_list()` | Examines structure to classify | Classification projection |

**Key insight:** Semantic debt directly affects emergence. If Python's `isinstance(value, list)` check behaves differently, match semantics change.

---

## Current Inventory

### Tracked Markers (debt_dashboard.sh)

| Marker | Count | Category | Location |
|--------|-------|----------|----------|
| `@host_recursion` | 3 | Semantic | eval_seed.py (match, substitute) |
| `@host_builtin` | 2 | Mixed | eval_seed.py, deep_eval.py |
| `@host_mutation` | 2 | Scaffolding | deep_eval.py, eval_seed.py |
| `@bootstrap_only` | 0 | Semantic | (deprecated marker) |

**Total tracked:** 7 markers

### AST_OK Bypasses (ast_police.py)

| Category | Count | Reason |
|----------|-------|--------|
| `# AST_OK: infra` | 23 | Infrastructure (CLI, coverage, tracing) |
| `# AST_OK: bootstrap` | 3 | Semantic debt in selfhost modules |

**Total bypasses:** 26 instances

The 3 `bootstrap` bypasses are semantic debt:
- `match_mu.py:237` - denormalize list comprehension
- `match_mu.py:280` - denormalize dict comprehension
- `match_mu.py:431` - denormalize bindings dict comprehension
- `eval_seed.py:355` - substitute list comprehension
- `eval_seed.py:359` - substitute dict comprehension

### Unmarked Semantic Debt

| Function | Lines | File | Issue |
|----------|-------|------|-------|
| `normalize_for_match()` | ~65 | match_mu.py | Unmarked Python traversal |
| `denormalize_from_match()` | ~75 | match_mu.py | Unmarked Python traversal |
| `resolve_lookups()` | ~40 | subst_mu.py | Unmarked Mu interpretation |
| `lookup_binding()` | ~20 | subst_mu.py | Unmarked linked list traversal |
| `is_dict_linked_list()` | ~20 | match_mu.py | Unmarked classification |
| `is_kv_pair_linked()` | ~20 | match_mu.py | Unmarked classification |
| `bindings_to_dict()` | ~15 | match_mu.py | Unmarked conversion |
| `dict_to_bindings()` | ~10 | match_mu.py | Unmarked conversion |

**Total unmarked:** ~265 lines of semantic debt

---

## Debt Ceiling Policy

### Current State
- **Tracked markers:** 7 (at ceiling)
- **AST_OK bypasses:** 26 (not tracked in ceiling)
- **Unmarked semantic debt:** ~265 lines (not tracked)

### Proposed Policy

1. **Marker ceiling stays at 9** (current RATCHET value)
2. **Add AST_OK tracking** - count `# AST_OK: bootstrap` separately
3. **Mark unmarked debt** - add `# SEMANTIC_DEBT:` marker to ~265 lines
4. **Separate dashboards:**
   - Scaffolding debt (LOC, informational only)
   - Semantic debt (blocking for L2 self-hosting)

### New Marker: `# SEMANTIC_DEBT:`

For code that interprets Mu but isn't yet a projection:

```python
# SEMANTIC_DEBT: normalize - should be projection
def normalize_for_match(value: Mu, _seen: set[int] | None = None) -> Mu:
    ...
```

This makes semantic debt visible without requiring the full `@host_*` decorator infrastructure.

---

## Path to L2 (Operational Self-Hosting)

To reach L2, all semantic debt must become projections:

### Phase 6a: Normalization as Projection
- `normalize_for_match()` → `seeds/normalize.v1.json`
- `denormalize_from_match()` → `seeds/denormalize.v1.json`
- Eliminates ~140 lines of semantic debt

### Phase 6b: Lookup as Projection
- `resolve_lookups()` → part of `seeds/subst.v1.json`
- `lookup_binding()` → part of lookup projection
- Eliminates ~60 lines of semantic debt

### Phase 6c: Classification as Projection
- `is_dict_linked_list()` → classification projection
- `is_kv_pair_linked()` → classification projection
- Eliminates ~40 lines of semantic debt

### Phase 6d: Kernel Loop as Projection
- `run_match_projections()` for-loop → iteration projection
- `run_subst_projections()` for-loop → iteration projection
- Completes L2 self-hosting

---

## Decision Criteria

When adding new code, ask:

1. **Does it traverse Mu and make decisions?**
   - Yes → Semantic debt, must become projection
   - No → Possibly scaffolding

2. **Would changing it change what operations mean?**
   - Yes → Semantic debt
   - No → Scaffolding

3. **Does it use Python's type system on Mu?**
   - `isinstance(value, list)` → Semantic debt
   - `isinstance(budget, int)` → Scaffolding (budget is infrastructure)

4. **Would replacing Python with Rust change semantics?**
   - Yes → Semantic debt (Python behavior is leaking)
   - No → Scaffolding (implementation detail)

---

## Summary

| Category | LOC | Status | Blocking |
|----------|-----|--------|----------|
| Scaffolding | ~200 | Acceptable | No |
| Semantic (tracked) | ~50 | At ceiling | L2 |
| Semantic (unmarked) | ~265 | Needs marking | L2 |

**Total semantic debt blocking L2:** ~315 lines

This debt is finite, bounded, and has a clear elimination path through Phases 6a-6d.
