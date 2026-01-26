# Debt Categories v0

This document formalizes the distinction between **scaffolding debt** (acceptable infrastructure) and **semantic debt** (must become structural).

## Status: DESIGN (v0)

---

## Why This Matters

Self-hosting has three levels:
- **L1 (Algorithmic)**: Projections encode the algorithm (match/substitute as Mu) ✓ COMPLETE
- **L2 (Operational)**: RCX executes projections structurally - NEXT
- **L3 (Meta-circular)**: Kernel itself is projections - FUTURE

At L1, Python still runs the kernel loop. This creates ambiguity: which Python code is "acceptable scaffolding" and which is "semantic debt that smuggles emergence"?

This document answers that question.

---

## Two Categories

### 1. Scaffolding Debt (Acceptable)

Code that provides **execution infrastructure** but does not determine **what operations mean**.

**Criteria:**
- Dispatches to projections but doesn't interpret projection content
- Provides I/O (file read, JSON parse) but doesn't interpret data
- Thread/resource isolation infrastructure

**Examples:**
| Code | Why Scaffolding |
|------|-----------------|
| `step(projections, state)` | Dispatches to seed, seed defines behavior |
| `json.load(f)` | I/O boundary, doesn't interpret seed content |
| `threading.local()` | Thread isolation infrastructure |
| `budget.consume(n)` | Resource tracking (count only, not behavior) |

**Key insight:** Scaffolding debt can be measured in LOC but doesn't affect emergence attribution. If we replaced Python's dispatch with Rust's, semantics would be identical.

### 2. Semantic Debt (Must Become Structural)

Code that **interprets Mu** or **determines what operations mean**.

**Criteria:**
- Traverses Mu and makes decisions based on content
- Implements operations that should be projections
- Uses Python conditionals to choose behavior based on Mu shape
- Creates new Mu based on interpreting existing Mu
- Determines termination/stall behavior

**Examples:**
| Code | Why Semantic | Path to Structural |
|------|-------------|-------------------|
| `normalize_for_match()` | Traverses Mu, converts based on type | Normalization projection |
| `denormalize_from_match()` | Traverses Mu, reconstructs based on shape | Denormalization projection |
| `resolve_lookups()` | Interprets `{"lookup": x, "in": y}` marker | Lookup projection |
| `lookup_binding()` | Traverses linked list to find name | Part of lookup projection |
| `is_dict_linked_list()` | Examines structure to classify | Classification projection |
| `max_steps` parameter | Determines when stall occurs | Structural termination |
| `mu_equal()` | Defines equality semantics for stall detection | Structural equality |

**Key insight:** Semantic debt directly affects emergence. If Python's `isinstance(value, list)` check behaves differently, match semantics change.

---

## Current Inventory

### Tracked Markers (debt_dashboard.sh)

| Marker | Count | Category | Location |
|--------|-------|----------|----------|
| `@host_recursion` | 3 | Semantic | eval_seed.py (match, substitute) |
| `@host_builtin` | 2 | Semantic | eval_seed.py, deep_eval.py |
| `@host_mutation` | 2 | Scaffolding | deep_eval.py, eval_seed.py |
| `@bootstrap_only` | 0 | Semantic | (deprecated marker) |

**Total tracked:** 7 markers (ceiling: 9)

### AST_OK Bypasses (ast_police.py)

| Category | Count | Reason |
|----------|-------|--------|
| `# AST_OK: infra` | 24 | Infrastructure (CLI, coverage, tracing) |
| `# AST_OK: bootstrap` | 5 | Semantic debt in selfhost modules |

**Total bypasses:** 29 instances across 11 files

The 5 `bootstrap` bypasses are semantic debt:
- `match_mu.py:237` - denormalize list comprehension
- `match_mu.py:280` - denormalize dict comprehension
- `match_mu.py:431` - denormalize bindings dict comprehension
- `eval_seed.py:355` - substitute list comprehension
- `eval_seed.py:359` - substitute dict comprehension

### Unmarked Semantic Debt

| Function | Lines | File | Issue |
|----------|-------|------|-------|
| `normalize_for_match()` | ~65 | match_mu.py | Python traversal + cycle detection |
| `denormalize_from_match()` | ~75 | match_mu.py | Python traversal + cycle detection |
| `resolve_lookups()` | ~42 | subst_mu.py | Mu interpretation |
| `lookup_binding()` | ~24 | subst_mu.py | Linked list traversal |
| `is_dict_linked_list()` | ~31 | match_mu.py | Classification logic |
| `is_kv_pair_linked()` | ~21 | match_mu.py | Classification logic |
| `bindings_to_dict()` | ~18 | match_mu.py | Conversion |
| `dict_to_bindings()` | ~13 | match_mu.py | Conversion |

**Total unmarked:** ~289 lines of semantic debt

**Note:** Cycle detection in normalize/denormalize adds ~20 lines each. Making this structural requires encoding visited set as Mu state.

---

## Debt Ceiling Policy

### Current State
- **Tracked markers:** 7/9 (2 headroom)
- **AST_OK bootstrap:** 5 (semantic debt, should count toward ceiling)
- **AST_OK infra:** 24 (scaffolding, acceptable)
- **Unmarked semantic debt:** ~289 lines (blocking L2)

### Policy

1. **Marker ceiling stays at 9** - existing `@host_*` markers
2. **Track AST_OK: bootstrap separately** - these are semantic debt
3. **Use existing markers** - no new marker systems needed
4. **Enhance debt_dashboard.sh** - add scaffolding vs semantic breakdown

To mark new semantic debt, use existing `@host_*` decorators or `# AST_OK: bootstrap` for statements.

---

## Path to L2

To reach L2, all semantic debt must become projections. See `docs/core/SelfHosting.v0.md` for phasing.

**Priority order (structural-proof verified):**

1. **Lookup** (~66 lines) - Most straightforward, linked list traversal is native to RCX
2. **Classification** (~52 lines) - Feasible with boolean→Mu encoding
3. **Normalization** (~140 lines) - Main logic works, cycle detection adds complexity
4. **Kernel loop** - L3 (meta-circular), requires structural-proof before promotion

**Open problem:** Phase 6d (kernel loop as projection) requires projections that interpret projections. This is meta-circular and needs concrete structural proof before promotion to NEXT.

---

## Decision Criteria

When adding new code, ask:

1. **Does it traverse Mu and make decisions?**
   - Yes → Semantic debt
   - No → Possibly scaffolding

2. **Would replacing Python with Rust change semantics?**
   - Yes → Semantic debt (Python behavior is leaking)
   - No → Scaffolding (implementation detail)

The second criterion is the ultimate test. `isinstance(value, list)`, `sorted()`, `mu_equal()` all have Python-specific behavior that would differ in another host language.

---

## Summary

| Category | LOC | Status | Blocking |
|----------|-----|--------|----------|
| Scaffolding | ~150 | Acceptable | No |
| Semantic (tracked) | ~50 | 7/9 ceiling | L2 |
| Semantic (AST_OK) | 5 instances | Should track | L2 |
| Semantic (unmarked) | ~289 | Needs @host_* | L2 |

**Total semantic debt blocking L2:** ~340 lines

This debt is finite, bounded, and has a clear elimination path. Lookup and classification are structurally feasible now; normalization requires cycle detection strategy; kernel loop requires L3 design.
