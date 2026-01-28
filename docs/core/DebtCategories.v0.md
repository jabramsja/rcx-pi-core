# Debt Categories v0

> **Current debt counts:** See `STATUS.md` for current debt threshold and counts. This doc explains the categories.

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
| `@host_recursion` | 4 | Semantic | eval_seed.py (match, substitute), match_mu.py (check_empty_var) |
| `@host_builtin` | 5 | Semantic | eval_seed.py, deep_eval.py, match_mu.py (convert) |
| `@host_mutation` | 2 | Scaffolding | eval_seed.py, deep_eval.py |
| `@bootstrap_only` | 0 | Semantic | (deprecated marker) |

**Total tracked:** 11 markers (ceiling: 15)

**Phase 6 debt reduction:**
- Phase 6a: Removed 2 `@host_builtin` (lookup as structural)
- Phase 6b: Removed 2 `@host_builtin` (classification as structural)
- Phase 6c: Removed 2 `@host_recursion` (iterative normalization)

### AST_OK Bypasses (ast_police.py)

| Category | Count | Reason |
|----------|-------|--------|
| `# AST_OK: infra` | 24 | Infrastructure (CLI, coverage, tracing) |
| `# AST_OK: bootstrap` | 3 | Semantic debt in selfhost modules |
| `# AST_OK: key comparison` | 5 | Type tag key set comparisons (Phase 6c) |
| `# AST_OK: constant whitelist` | 1 | VALID_TYPE_TAGS frozenset (Phase 6c) |

**Total bypasses:** 33 instances across 12 files

The 3 `bootstrap` bypasses are semantic debt (line numbers may drift):
- `eval_seed.py` - 2 instances (substitute comprehensions)
- `match_mu.py` - 1 instance (remaining comprehension)

The 6 Phase 6c `AST_OK` markers are scaffolding (key comparison for type tags).

### Remaining Semantic Debt

Functions still marked with `@host_recursion` or `@host_builtin` decorators:

| Function | Marker | File | Path to Structural |
|----------|--------|------|-------------------|
| `_check_empty_var_names()` | @host_recursion | match_mu.py | Validation projection |
| `bindings_to_dict()` | @host_builtin | match_mu.py | Conversion projection |
| `dict_to_bindings()` | @host_builtin | match_mu.py | Conversion projection |
| `match()` | @host_recursion | eval_seed.py | (already structural in match_mu) |
| `substitute()` | @host_recursion | eval_seed.py | (already structural in subst_mu) |

### Eliminated Semantic Debt (Phase 6)

| Function | Was | Now | Phase |
|----------|-----|-----|-------|
| `normalize_for_match()` | @host_recursion | Iterative | 6c |
| `denormalize_from_match()` | @host_recursion | Iterative | 6c |
| `resolve_lookups()` | @host_builtin | Mu projection | 6a |
| `lookup_binding()` | @host_builtin | Mu projection | 6a |
| `is_dict_linked_list()` | @host_builtin | `classify_linked_list()` | 6b |
| `is_kv_pair_linked()` | @host_builtin | Mu projection | 6b |

**Note:** Cycle detection remains in normalize/denormalize (~28 lines) but is now inline in iterative code, not recursive.

---

## Debt Ceiling Policy

### Current State
- **Tracked markers:** 11/14 (at ceiling)
- **AST_OK bootstrap:** 3 (semantic debt, counted separately)
- **AST_OK infra/key comparison:** 30 (scaffolding, acceptable)
- **Total semantic debt:** 14 (11 tracked + 3 AST_OK)

### Policy

1. **Marker ceiling is 14** - reduced from 23 after Phase 6a/6b/6c and PR #163 cleanup
2. **Track AST_OK: bootstrap separately** - these are semantic debt
3. **Use existing markers** - no new marker systems needed
4. **Ratchet only tightens** - threshold can only decrease, never increase

To mark new semantic debt, use existing `@host_*` decorators or `# AST_OK: bootstrap` for statements.

### Enforcement Status

**Implemented (PR #155, updated PR #156):**
- `debt_dashboard.sh` now counts AST_OK: bootstrap bypasses separately from scaffolding
- `audit_semantic_purity.sh` includes AST_OK: bootstrap in the debt threshold (DEBT_THRESHOLD=23)
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

**Completed (Phase 6):**

1. ✅ **Lookup** (~66 lines) - Phase 6a: `subst.lookup.found`, `subst.lookup.next` projections
2. ✅ **Classification** (~52 lines) - Phase 6b: `seeds/classify.v1.json` (6 projections)
3. ✅ **Normalization** (~140 lines) - Phase 6c: Iterative with explicit stack + type tags

**Remaining:**

4. **Kernel loop** - Phase 7 (meta-circular), requires structural-proof before promotion
5. **Conversion helpers** (~40 lines) - `bindings_to_dict()`, `dict_to_bindings()`

**Open problem:** Phase 7 (kernel loop as projection) requires projections that interpret projections. This is meta-circular and needs concrete structural proof before promotion to NEXT.

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
| Semantic (tracked) | ~200 | 11/14 ceiling | L2 |
| Semantic (AST_OK) | 3 instances | Counted separately | L2 |
| Semantic (unmarked) | 0 | All marked | L2 |

**Total semantic debt blocking L2:** ~150 lines (reduced from ~340 after Phase 6)

**Phase 6 debt reduction:**
- Phase 6a: Lookup as Mu projections (~66 lines eliminated)
- Phase 6b: Classification as Mu projections (~52 lines eliminated)
- Phase 6c: Iterative normalization (~28 lines eliminated)
- PR #163: Dead code removal (`resolve_lookups()` deleted, ~47 lines)

This debt is finite, bounded, and has a clear elimination path. The remaining semantic debt is primarily in `eval_seed.py` (match/substitute core) and `match_mu.py` (conversion helpers). Kernel loop (Phase 7) requires L3 design.

**LOC estimates are approximate** - actual counts may vary with code formatting. Use `grep` commands in grounding tests for verification.

---

## Known Design Decisions

### Empty Collection Normalization

Both `{}` (empty dict) and `[]` (empty list) normalize to `null` (empty linked list). This is intentional:

1. **Why identical normalization:** Structurally, an empty sequence is an empty sequence regardless of whether it was a Python list or dict. The head/tail encoding cannot distinguish them.

2. **Denormalization behavior:** An empty linked list (`null`) denormalizes to `[]`, not `{}`. This means:
   - `normalize({})` → `null`
   - `denormalize(null)` → `[]`
   - Round-trip changes empty dicts to empty lists

3. **Implication for matching:** `{}` and `[]` match the same patterns. A pattern matching `[]` will also match `{}`.

4. **Why this is acceptable:** In RCX, empty collections are semantically equivalent empty sequences. If your logic depends on distinguishing empty dict from empty list, you need a different encoding (e.g., a wrapper like `{"type": "dict", "items": []}`).

### Head/Tail Key Collision

A dict with keys `head` and `tail` like `{"head": "x", "tail": "y"}` is NOT misclassified as a linked list node because:

1. The `is_dict_linked_list()` function checks ALL elements of the linked list to verify each is a valid kv-pair
2. A valid kv-pair has the exact structure: `{"head": key_string, "tail": {"head": value, "tail": null}}`
3. A dict where `tail` is not another head/tail node (or null) fails this check

This means user data containing `head`/`tail` keys is safe - it will be normalized as a regular dict with those keys as kv-pairs, not confused with linked list structure.

### Type Tags (Phase 6c)

Type tags resolve the list/dict ambiguity where `[["a", 1]]` and `{"a": 1}` would otherwise normalize to identical head/tail structures.

1. **How it works:** `normalize_for_match()` adds `_type: "list"` or `_type: "dict"` to root nodes:
   - `{"a": 1}` → `{"_type": "dict", "head": ..., "tail": ...}`
   - `[["a", 1]]` → `{"_type": "list", "head": ..., "tail": ...}`

2. **Security:** Type tags use a whitelist (`VALID_TYPE_TAGS = {"list", "dict"}`) and `validate_type_tag()` rejects unknown values.

3. **Projections:** New projections handle type-tagged structures:
   - `match.typed.descend` - descend into typed linked list
   - `subst.typed.{descend,sibling,ascend}` - substitution with type preservation

4. **Classification fast-path:** `classify_linked_list()` checks `_type` directly for type-tagged structures, avoiding full structural scan.

5. **Legacy support:** Structures without `_type` still work via projection-based classification.
