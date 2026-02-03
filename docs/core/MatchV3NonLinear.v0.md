# Match v3: Non-Linear Pattern Support

**Status:** VECTOR (design-only)
**Created:** 2026-02-02
**Origin:** Architectural gap found in 9-agent review of Step 6
**Depends on:** match.v2.json (context passthrough)
**Enables:** enginenews.v1, exhaust.v1 to become META-CIRCULAR

---

## Executive Summary

match.v2.json explicitly states "Linear patterns only (no conflict detection)." However, recurrence.v1.json and exhaustion.v1.json rely on non-linear patterns (same variable appears twice in pattern) to detect equality structurally.

Currently, these seeds work because they run via `eval_seed.step()` which implements binding conflict detection in Python (lines 331-336, 351-355). But they **cannot** run through the meta-circular kernel (kernel.v1 + match.v2 + subst.v2).

match.v3 adds binding conflict detection as structural projections, enabling all seeds to be truly meta-circular.

---

## Problem Statement

### The Incompatibility

```
match.v2.json line 12: "Linear patterns only (no conflict detection)"

recurrence.v1.json projection "found_in_seen":
  pattern: { "_state": {"var": "state"}, "_check_list": {"head": {"var": "state"}, ...} }
  ^^^^ Same variable "state" appears TWICE - requires binding conflict detection

exhaustion.v1.json projection "scan_same":
  pattern: { "_trace": {"head": {"projection": {"var": "proj"}}}, "_tau_operator": {"var": "proj"} }
  ^^^^ Same variable "proj" appears TWICE - requires binding conflict detection
```

### Why This Matters

1. **North Star #14 violation**: Seeds can't declare META_CIRCULAR if they require non-linear patterns
2. **L4 blocker**: True self-hosting requires all logic in projections, not bootstrap
3. **Test theater risk**: Tests pass via bootstrap, hiding meta-circular incompatibility

### Current Workaround

enginenews and exhaust declare `"execution_layer": "BOOTSTRAP"` and document their dependency on eval_seed's Python binding conflict detection. This is honest but not a solution.

---

## What Non-Linear Patterns Do

A non-linear pattern uses the same variable twice to assert equality:

```json
{
  "pattern": {"a": {"var": "x"}, "b": {"var": "x"}},
  "body": {"matched": true}
}
```

**Linear semantics (match.v2):** Binds `x` to `value.a`, then binds `x` to `value.b` (overwrites).
- Input `{"a": 1, "b": 2}` → matches, `x = 2`
- Input `{"a": 1, "b": 1}` → matches, `x = 1`
- **No equality check!**

**Non-linear semantics (match.v3):** Binds `x` to `value.a`, then checks if `value.b` equals existing binding.
- Input `{"a": 1, "b": 2}` → **NO MATCH** (conflict: 1 ≠ 2)
- Input `{"a": 1, "b": 1}` → matches, `x = 1`
- **Equality is structural!**

---

## Design: Binding Conflict Detection as Projections

### Current match.v2 State Machine

```
match_state = {
  "mode": "match",
  "pattern_focus": <current pattern position>,
  "value_focus": <current value position>,
  "bindings": <linked list of {name, value, rest}>,
  "stack": <continuation stack>,
  "_match_ctx": <context passthrough>
}
```

### Required Changes for match.v3

When encountering `{"var": "name"}` in pattern:

**match.v2 (current):**
1. Add `{name, value, rest: bindings}` to bindings
2. Clear focus, continue

**match.v3 (proposed):**
1. Check if `name` already exists in bindings (new lookup phase)
2. If NOT found: add binding as before
3. If found: compare existing value to current value
   - If equal: continue (binding is consistent)
   - If not equal: transition to NO_MATCH

### New Projections Required

```json
[
  {
    "id": "match.var.check_existing",
    "description": "Variable site - check if name already bound",
    "pattern": {
      "mode": "match",
      "pattern_focus": {"var": {"var": "name"}},
      "value_focus": {"var": "value"},
      "bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    },
    "body": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": {"var": "bindings"},
      "_original_bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    }
  },
  {
    "id": "match.lookup.found_same",
    "description": "Found existing binding with SAME value (non-linear OK)",
    "pattern": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": {
        "name": {"var": "name"},
        "value": {"var": "value"},
        "rest": {"var": "_"}
      },
      "_original_bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    },
    "body": {
      "mode": "match",
      "pattern_focus": null,
      "value_focus": null,
      "bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    }
  },
  {
    "id": "match.lookup.found_different",
    "description": "Found existing binding with DIFFERENT value (conflict!)",
    "pattern": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": {
        "name": {"var": "name"},
        "value": {"var": "other_value"},
        "rest": {"var": "_"}
      },
      "_original_bindings": {"var": "_"},
      "stack": {"var": "_"},
      "_match_ctx": {"var": "ctx"}
    },
    "body": {
      "_mode": "match_done",
      "_status": "no_match",
      "_match_ctx": {"var": "ctx"}
    }
  },
  {
    "id": "match.lookup.not_found_yet",
    "description": "Name not at head of bindings, continue searching",
    "pattern": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": {
        "name": {"var": "other_name"},
        "value": {"var": "_"},
        "rest": {"var": "rest"}
      },
      "_original_bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    },
    "body": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": {"var": "rest"},
      "_original_bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    }
  },
  {
    "id": "match.lookup.not_found",
    "description": "Name not in bindings (null), add new binding",
    "pattern": {
      "mode": "match",
      "_phase": "lookup_binding",
      "_lookup_name": {"var": "name"},
      "_lookup_value": {"var": "value"},
      "_lookup_bindings": null,
      "_original_bindings": {"var": "bindings"},
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    },
    "body": {
      "mode": "match",
      "pattern_focus": null,
      "value_focus": null,
      "bindings": {
        "name": {"var": "name"},
        "value": {"var": "value"},
        "rest": {"var": "bindings"}
      },
      "stack": {"var": "stack"},
      "_match_ctx": {"var": "ctx"}
    }
  }
]
```

### Projection Count Estimate

| Projection | Purpose |
|------------|---------|
| `match.var.check_existing` | Entry: start lookup phase |
| `match.lookup.found_same` | Non-linear OK (same value) |
| `match.lookup.found_different` | Binding conflict → NO_MATCH |
| `match.lookup.not_found_yet` | Continue searching bindings |
| `match.lookup.not_found` | First occurrence → add binding |

**Total new projections:** 5 (replacing 1 existing `match.var`)
**Net change:** +4 projections

match.v3 would have: 8 (current) + 4 (new) = **12 projections**

---

## Critical Design Question: Non-Linear Patterns for Lookup

The `match.lookup.found_same` projection uses a non-linear pattern:

```json
"pattern": {
  "_lookup_name": {"var": "name"},
  "_lookup_bindings": {
    "name": {"var": "name"},  // Same var "name" twice!
    ...
  }
}
```

**Problem:** match.v3 is supposed to ADD non-linear support, but we need it to IMPLEMENT non-linear support!

### Options

**Option A: Bootstrap the Bootstrapper**
- match.v3 uses non-linear patterns (eval_seed)
- Once match.v3 exists, enginenews/exhaust can use match.v3
- But match.v3 itself remains BOOTSTRAP

**Option B: Structural Name Comparison**
- Don't use non-linear pattern for name equality
- Use explicit structural comparison projections
- Adds more projections but is truly meta-circular

**Option C: Two-Phase Approach**
- match.v3a: Linear lookup (string comparison via projections)
- match.v3b: Non-linear support (uses v3a for its own lookup)
- Then v3b can run v3b (truly self-hosting)

### Recommendation

**Option A** for now. Accept that match.v3 is BOOTSTRAP. Document this as an irreducible layer (like Forth's NEXT). The goal is to enable enginenews/exhaust to become meta-circular, not to make match itself meta-circular (which may be impossible without infinite regress).

### L4 Implications

**match.v3 remains BOOTSTRAP forever in this architecture.** This is an irreducible bootstrap layer:

- **What this means:** match.v3's own projections use non-linear patterns, so it requires `eval_seed.match()` to run
- **Why it's acceptable:** Every computing system has irreducible primitives (Forth's NEXT, Lisp's EVAL, x86 microcode)
- **L4 goal adjustment:** L4 becomes "minimize and document the bootstrap layer" not "eliminate it entirely"
- **What match.v3 achieves:** Moves the bootstrap boundary DOWN one layer, enabling enginenews/exhaust to become META_CIRCULAR
- **Trust boundary:** The security-critical code is `eval_seed.match()` binding conflict detection (~6 lines of Python/JS)

This is NOT a compromise on L4 goals - it's a recognition that some bootstrap layer is mathematically irreducible.

---

## Security Requirements (9-Agent Adversary Review)

### 1. KERNEL_RESERVED_FIELDS Update (CRITICAL)

Before implementation, add these fields to `step_mu.py` KERNEL_RESERVED_FIELDS:

```python
# Match v3 lookup phase fields (MatchV3NonLinear.v0.md)
"_lookup_name",        # Variable name being looked up
"_lookup_value",       # Value to compare against existing binding
"_lookup_bindings",    # Current position in bindings search
"_original_bindings",  # Preserved for adding new binding
```

**Why:** Without this, domain data could inject forged lookup state to bypass match validation.

### 2. Projection Ordering (SECURITY-CRITICAL)

Lookup phase projections MUST be ordered (first-match-wins):

1. `match.lookup.found_same` - Non-linear match for equal values
2. `match.lookup.found_different` - Catch-all for found but different (→ NO_MATCH)
3. `match.lookup.not_found_yet` - Continue searching bindings
4. `match.lookup.not_found` - End of bindings (→ add new binding)

**Why:** If `found_different` comes before `found_same`, ALL found bindings would be treated as conflicts (false positives).

### 3. Variable Name Collision Mitigation

User variable names (from `{"var": "x"}`) should NOT start with underscore to avoid confusion with reserved fields. Options:

- **Option A (Validation):** Reject patterns with variables named `_mode`, `_phase`, etc.
- **Option B (Prefixing):** Internally prefix user variables (e.g., `user_x`)
- **Recommendation:** Option A (simpler, explicit error for bad patterns)

### 4. Security Test Vectors

Add these to the test suite:

| Vector | Purpose | Expected |
|--------|---------|----------|
| `reserved_name_collision` | Pattern `{"a": {"var": "_mode"}}` | Match works (no state confusion) |
| `lookup_injection` | Domain input with `_lookup_name` field | Rejected at kernel boundary |
| `ordering_critical` | Non-linear with conflict | found_different fires, NO_MATCH |

---

## Reserved Fields

New fields for match.v3 (must be added to KERNEL_RESERVED_FIELDS before implementation):

| Field | Value/Type | Purpose |
|-------|------------|---------|
| `_phase` | `"lookup_binding"` | New phase value (field already exists) |
| `_lookup_name` | string | Variable name being looked up |
| `_lookup_value` | Mu | Value to compare against existing binding |
| `_lookup_bindings` | linked list | Current position in bindings search |
| `_original_bindings` | linked list | Preserved for adding new binding |

**Implementation checklist:**
1. [ ] Add 4 new fields to `KERNEL_RESERVED_FIELDS` in `rcx_pi/selfhost/step_mu.py`
2. [ ] Add fields to JS equivalent in `mu/host/js/eval_step.js`
3. [ ] Add test verifying domain data with these fields is rejected

---

## Success Criteria

1. [ ] match.v3.json exists with ~12 projections
2. [ ] `match.var` replaced with `match.var.check_existing` + lookup projections
3. [ ] Parity tests: match.v3 gives same results as match.v2 for linear patterns
4. [ ] Non-linear tests: match.v3 correctly detects binding conflicts
5. [ ] enginenews.v1 can declare `"execution_layer": "META_CIRCULAR"` using match.v3
6. [ ] exhaust.v1 can declare `"execution_layer": "META_CIRCULAR"` using match.v3
7. [ ] Cross-substrate parity: Python and JS match.v3 produce identical results

---

## Test Vectors

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `linear_ok` | `{"a": {"var": "x"}}` | `{"a": 1}` | Match, x=1 |
| `nonlinear_same` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 1, "b": 1}` | Match, x=1 |
| `nonlinear_diff` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 1, "b": 2}` | NO_MATCH |
| `nested_nonlinear` | `{"outer": {"inner": {"var": "x"}, "check": {"var": "x"}}}` | `{"outer": {"inner": 5, "check": 5}}` | Match |
| `triple_same` | `{"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}` | `{"a": 1, "b": 1, "c": 1}` | Match |
| `triple_one_diff` | `{"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}` | `{"a": 1, "b": 1, "c": 2}` | NO_MATCH |

---

## Implementation Sequence

1. **Design doc review** (this doc) - 9-agent review
2. **Create match.v3.json** with new projections
3. **Create parity tests** (v3 == v2 for linear patterns)
4. **Create non-linear tests** (binding conflict detection)
5. **Port to JS** and verify parity
6. **Update enginenews.v1 and exhaust.v1** to use match.v3
7. **Update execution_layer** declarations to META_CIRCULAR
8. **Add integration tests** verifying meta-circular execution

---

## Related Documents

- `docs/core/MetaCircularKernel.v0.md` - Kernel architecture
- `docs/core/BootstrapPrimitives.v0.md` - Bootstrap layer definition
- `mu/substrate/match.v2.json` - Current linear-only matcher
- `mu/closures/recurrence.v1.json` - Requires non-linear patterns
- `mu/closures/exhaustion.v1.json` - Requires non-linear patterns

---

## Changelog

- **v0.1 (2026-02-02):** Added Security Requirements section from 9-agent adversary review:
  - KERNEL_RESERVED_FIELDS update requirement
  - Projection ordering specification
  - Variable name collision mitigation
  - Security test vectors
  - L4 implications clarification ("BOOTSTRAP forever" is acceptable)
- **v0 (2026-02-02):** Initial design doc created after 9-agent review discovered match.v2/enginenews incompatibility

---

## Open Questions

1. **Should match.v3 replace match.v2 or coexist?**
   - **Answer (9-agent consensus):** Coexist initially, consider unification after 6+ months
   - match.v2 is simpler and sufficient for linear-only seeds
   - Seeds declare `"requires_patterns": ["non-linear"]` to request match.v3

2. **Is Option A (bootstrap the bootstrapper) acceptable for L4?**
   - **Answer (9-agent consensus):** Yes. This is analogous to Forth's NEXT or Lisp's EVAL
   - Some primitive must exist - the goal is minimizing it, not eliminating it
   - match.v3 being BOOTSTRAP is acceptable and documented
   - L4 goal becomes: "minimize bootstrap layer to ~6 lines of auditable code"

3. **Should KERNEL_RESERVED_FIELDS be extended now?**
   - **Answer (adversary finding):** YES - must be extended BEFORE implementation
   - 4 new fields required (see Security Requirements section)
   - Without this, domain data can inject forged lookup state
