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
- Dispatches to projections without examining projection structure, content, or state
- Provides I/O (file read, JSON parse) without transforming data based on content
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

**Definition of "interprets":** Code that examines Mu structure (type, keys, values, length) and makes decisions that affect output. This includes:
- Type dispatch (`isinstance(value, list)`)
- Key inspection (`"head" in value`)
- Value comparison (`value == expected`)
- Structure traversal (`for elem in value`)

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
| `@host_recursion` | 2 | Semantic | eval_seed.py:213,321 (match, substitute) |
| `@host_builtin` | 3 | Semantic | eval_seed.py:218, deep_eval.py:262,343 |
| `@host_mutation` | 2 | Scaffolding | eval_seed.py:222, deep_eval.py:344 |
| `@bootstrap_only` | 0 | Semantic | (deprecated marker) |

**Total tracked:** 7 markers (ceiling: 9)

### AST_OK Bypasses (ast_police.py)

| Category | Count | Reason |
|----------|-------|--------|
| `# AST_OK: infra` | 24 | Infrastructure (CLI, coverage, tracing) |
| `# AST_OK: bootstrap` | 5 | Semantic debt in selfhost modules |

**Total bypasses:** 29 instances across 11 files

The 5 `bootstrap` bypasses are semantic debt (line numbers may drift):
- `match_mu.py` - 3 instances (denormalize comprehensions)
- `eval_seed.py` - 2 instances (substitute comprehensions)

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

**Total unmarked:** ~289 lines of semantic debt (LOC estimates, may vary with formatting)

**Note:** Cycle detection in normalize/denormalize totals ~28 lines across both functions. Making this structural requires encoding visited set as Mu state.

---

## Debt Ceiling Policy

### Current State
- **Tracked markers:** 7/9 (2 headroom)
- **AST_OK bootstrap:** 5 (semantic debt, counted separately)
- **AST_OK infra:** 24 (scaffolding, acceptable)
- **Unmarked semantic debt:** ~289 lines (blocking L2)

### Policy

1. **Marker ceiling stays at 9** - existing `@host_*` markers
2. **Track AST_OK: bootstrap separately** - these are semantic debt
3. **Use existing markers** - no new marker systems needed
4. **Enhance debt_dashboard.sh** - add scaffolding vs semantic breakdown

To mark new semantic debt, use existing `@host_*` decorators or `# AST_OK: bootstrap` for statements.

### Enforcement Status

**Implemented (PR #155, updated PR #156):**
- `debt_dashboard.sh` now counts AST_OK: bootstrap bypasses separately from scaffolding
- `audit_semantic_purity.sh` includes AST_OK: bootstrap in the debt threshold (DEBT_THRESHOLD=14)
- Dashboard shows: Tracked markers + AST_OK bootstrap = Total Semantic Debt
- AST_OK patterns use `[[:space:]]*` to catch spacing variations (e.g., `AST_OK:bootstrap`)

**Known grep behavior:**
- Grep counts docstring examples as decorators (e.g., line 51 of eval_seed.py)
- Actual decorators: 7 (2 recursion + 3 builtin + 2 mutation)
- Grep reports: 8 (includes 1 docstring example)
- Threshold set to 14 to account for: 8 grep-counted + 5 AST_OK + 1 PHASE REVIEW

**Remaining gaps:**
- ~289 lines of unmarked semantic debt (normalize, denormalize, classify functions)
- No CI check that fails if unmarked semantic functions are added

**To fully close the gap:**
- Mark remaining semantic debt with `@host_*` decorators or `# AST_OK: bootstrap`
- Consider unified tracking (all semantic debt uses @host_* decorators)

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

1. **Does it examine Mu structure and make decisions?**
   - Examines type (`isinstance`), keys (`in`), values (`==`), or traverses (`for`) → Semantic debt
   - Only passes Mu through without inspection → Possibly scaffolding

2. **Could this be expressed as a Mu-to-Mu projection?**
   - Yes but isn't yet → Semantic debt (mark with @host_*)
   - No (requires I/O, threading, etc.) → Scaffolding

The key distinction: scaffolding is **mechanism** (how to run), semantic is **interpretation** (what Mu means).

---

## Summary

| Category | LOC | Status | Blocking |
|----------|-----|--------|----------|
| Scaffolding | ~150 | Acceptable | No |
| Semantic (tracked) | ~50 | 7/9 ceiling | L2 |
| Semantic (AST_OK) | 5 instances | Counted separately | L2 |
| Semantic (unmarked) | ~289 | Needs @host_* | L2 |

**Total semantic debt blocking L2:** ~340 lines

This debt is finite, bounded, and has a clear elimination path. Lookup and classification are structurally feasible now; normalization requires cycle detection strategy; kernel loop requires L3 design.

**LOC estimates are approximate** - actual counts may vary with code formatting. Use `grep` commands in grounding tests for verification.
