# Debt Categories v0

> **Current debt counts:** See `STATUS.md` for current debt threshold and counts. This doc explains the categories.

---

## Why This Matters

Self-hosting has three levels:
- **L1 (Algorithmic)**: Projections encode the algorithm (match/substitute as Mu) ✓ DONE
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

> **For current counts, see `STATUS.md`.** This section describes the categories, not the numbers.
>
> Run `./tools/debt_dashboard.sh` for live counts. Grounding tests in `tests/structural/` verify counts match STATUS.md.

### Tracked Markers

| Marker | Category | Meaning |
|--------|----------|---------|
| `@host_recursion` | Semantic | Python recursion doing Mu work |
| `@host_builtin` | Semantic | Python builtins interpreting Mu |
| `@host_mutation` | Scaffolding | Python mutation (dict assignment) |

### AST_OK Bypasses

| Category | Meaning |
|----------|---------|
| `# AST_OK: infra` | Infrastructure (CLI, tracing) - acceptable |
| `# AST_OK: bootstrap` | Semantic debt - must become structural |
| `# AST_OK: key comparison` | Type tag checks - scaffolding |

### Remaining Semantic Debt

Functions still using host operations (see `debt_dashboard.sh` for current list):
- `match()` / `substitute()` in eval_seed.py (reference implementations)
- Conversion helpers in match_mu.py (`bindings_to_dict`, `dict_to_bindings`)
- Empty var validation in match_mu.py

---

## Debt Ceiling Policy

> **Current threshold/count: See `STATUS.md`**

### Policy

1. **Threshold can only decrease** (ratchet policy)
2. **Track AST_OK: bootstrap separately** - these are semantic debt
3. **Use existing markers** - no new marker systems needed
4. **Ratchet only tightens** - threshold can only decrease, never increase

To mark new semantic debt, use existing `@host_*` decorators or `# AST_OK: bootstrap` for statements.

### Enforcement Status

**Current threshold and counts:** See `STATUS.md` (single source of truth).

**Implemented:**
- `debt_dashboard.sh` counts all @host_* markers and AST_OK: bootstrap bypasses
- Dashboard shows: Tracked markers + AST_OK bootstrap = Total Semantic Debt
- Run `./tools/debt_dashboard.sh --json` for machine-readable counts

**Tracking mechanisms:**
- @host_* decorators for function-level debt
- `# @host_*` comments for nested function debt (can't decorate)
- `# AST_OK: bootstrap` for statement-level semantic debt
- `# AST_OK: infra` for infrastructure scaffolding (not counted as debt)

**To fully close gaps:**
- Mark any new semantic debt with `@host_*` decorators or `# AST_OK: bootstrap`
- All debt markers must have clear elimination path documented

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

> **For current counts, see `STATUS.md`.** Run `./tools/debt_dashboard.sh` for live counts.

| Category | Status | Blocking |
|----------|--------|----------|
| Scaffolding | Acceptable | No |
| Semantic (tracked markers) | See STATUS.md | L2 |
| Semantic (AST_OK bootstrap) | See STATUS.md | L2 |

**Debt is finite, bounded, and has a clear elimination path.** Remaining semantic debt is in:
- `eval_seed.py` (match/substitute reference implementations)
- `match_mu.py` (conversion helpers)

Kernel loop self-hosting (Phase 7) is tracked in TASKS.md.

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

### String Key Assumption (classify_mu.py)

The `classify_linked_list()` function in `rcx_pi/selfhost/classify_mu.py` determines whether a head/tail structure encodes a dict or list.

**The Limitation:**

Mu projections can only check structural patterns (head/tail shape), not Python types. The string key check at line 179 is a **security boundary** that projections cannot enforce:

```python
if not isinstance(key, str):
    # Key is not a string - not a valid dict encoding
    return "list"
```

**Why This Matters:**

1. **Ambiguity after normalization:** A list like `[["key", "value"]]` and a dict like `{"key": "value"}` both normalize to the same head/tail structure. Without the string key check, an attacker could create structures with non-string keys that bypass validation.

2. **Host semantics leakage:** Python's `isinstance(key, str)` determines whether a structure is valid dict encoding. This is a pre-condition the projections assume but cannot verify.

3. **Design decision:** When ambiguous, we favor dict interpretation because dicts with None values are more common than lists of 2-element sublists.

**Documentation in Code:**

This is documented in classify_mu.py lines 167-173:
```python
# KNOWN LIMITATION: A list like [[s, x]] normalizes identically to {s: x}
# We cannot distinguish them after normalization. We favor dict interpretation
# because dicts with None values are more common than lists of 2-element sublists.
```

And in the seed file `seeds/classify.v1.json` meta/invariants:
```json
"Pre-condition: dict keys are strings (JSON constraint)"
```

**Resolution Path:**

Phase 6c type tags resolve this for new code - tagged structures (`_type: "dict"` or `_type: "list"`) bypass projection-based classification entirely. The string key check only applies to legacy untagged structures.
