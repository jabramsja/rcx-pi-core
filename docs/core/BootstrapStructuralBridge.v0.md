<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-09
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

# Bootstrap-Structural Bridge: Non-Linear Pattern Support

**Status:** IMPLEMENTED (two execution paths: match_mu direct + kernel bridge mode)
**Created:** 2026-02-02
**Implemented:** 2026-02-02
**Origin:** Architectural gap found in 9-agent review of Step 6
**Location:** `mu/bridge/bootstrap_structural.v1.json`
**Depends on:** match.v2.json (context passthrough)
**Enables:** recurrence.v1, exhaustion.v1 to become META-CIRCULAR

---

## Executive Summary

match.v2.json explicitly states "Linear patterns only (no conflict detection)." However, recurrence.v1.json and exhaustion.v1.json rely on non-linear patterns (same variable appears twice in pattern) to detect equality structurally.

These seeds work via `eval_seed.step()` which implements binding conflict detection in Python. The bootstrap-structural bridge adds binding conflict detection as structural projections.

**Status (2026-02-09):** Bridge projections are IMPLEMENTED and VERIFIED to fire. Two execution paths now use bridge:
1. **match_mu direct** (B-structural, 2026-02-09): `match_mu()` loads match.v2 + bridge projections via `projection_runner` for `apply_mu()` non-linear conflict detection.
2. **kernel bridge mode**: `run_algorithm_meta_circular()` dispatches to `step_kernel_mu(kernel_mode="bridge")` for recurrence/exhaustion.

Bootstrap execution remains explicit debug fallback only. `step_mu()`/`run_mu()` are fail-closed: they reject non-linear patterns with ValueError.

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

### Implementation Status

The bridge is IMPLEMENTED (`mu/bridge/bootstrap_structural.v1.json` with 5 projections). Execution path verification tests prove bridge projections fire. Production algorithm execution is structural via kernel bridge mode (see "Current Execution Architecture" section).

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

**Non-linear semantics (bootstrap_structural):** Binds `x` to `value.a`, then checks if `value.b` equals existing binding.
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

### Required Changes for Bootstrap-Structural Bridge

When encountering `{"var": "name"}` in pattern:

**match.v2 (current):**
1. Add `{name, value, rest: bindings}` to bindings
2. Clear focus, continue

**bootstrap_structural (proposed):**
1. Check if `name` already exists in bindings (new lookup phase)
2. If NOT found: add binding as before
3. If found: compare existing value to current value
   - If equal: continue (binding is consistent)
   - If not equal: transition to NO_MATCH

### New Projections Required

```json
[
  {
    "id": "bridge.var.check_existing",
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
    "id": "bridge.lookup.found_same",
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
    "id": "bridge.lookup.found_different",
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
    "id": "bridge.lookup.not_found_yet",
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
    "id": "bridge.lookup.not_found",
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

### Projection Count

| Projection | Purpose |
|------------|---------|
| `bridge.var.check_existing` | Entry: start lookup phase |
| `bridge.lookup.found_same` | Non-linear OK (same value) |
| `bridge.lookup.found_different` | Binding conflict → NO_MATCH |
| `bridge.lookup.not_found_yet` | Continue searching bindings |
| `bridge.lookup.not_found` | First occurrence → add binding |

**Actual count:** See `tests/structural/test_seed_counts.py` for verified projection count.

---

## Critical Design Question: Non-Linear Patterns for Lookup

The `bridge.lookup.found_same` projection uses a non-linear pattern:

```json
"pattern": {
  "_lookup_name": {"var": "name"},
  "_lookup_bindings": {
    "name": {"var": "name"},  // Same var "name" twice!
    ...
  }
}
```

**Problem:** The bridge is supposed to ADD non-linear support, but we need it to IMPLEMENT non-linear support!

### Options

**Option A: Bootstrap the Bootstrapper**
- bootstrap_structural uses non-linear patterns (eval_seed)
- Once bootstrap_structural exists, recurrence/exhaustion can use it
- But bootstrap_structural itself remains BOOTSTRAP

**Option B: Structural Name Comparison**
- Don't use non-linear pattern for name equality
- Use explicit structural comparison projections
- Adds more projections but is truly meta-circular

**Option C: Two-Phase Approach**
- bootstrap_structural_a: Linear lookup (string comparison via projections)
- bootstrap_structural_b: Non-linear support (uses v3a for its own lookup)
- Then v3b can run v3b (truly self-hosting)

### Recommendation

**Option A** for now. Accept that bootstrap_structural is BOOTSTRAP. Document this as an irreducible layer (like Forth's NEXT). The goal is to enable recurrence/exhaustion to become meta-circular, not to make the bridge itself meta-circular (which may be impossible without infinite regress).

### L4 Implications

**bootstrap_structural remains BOOTSTRAP forever in this architecture.** This is an irreducible bootstrap layer:

- **What this means:** The bridge's own projections use non-linear patterns, so it requires `eval_seed.match()` to run
- **Why it's acceptable:** Every computing system has irreducible primitives (Forth's NEXT, Lisp's EVAL, x86 microcode)
- **L4 goal adjustment:** L4 becomes "minimize and document the bootstrap layer" not "eliminate it entirely"
- **What the bridge achieves:** Moves the bootstrap boundary DOWN one layer, enabling recurrence/exhaustion to become META_CIRCULAR
- **Trust boundary:** The security-critical code is `eval_seed.match()` binding conflict detection (~6 lines of Python/JS)

This is NOT a compromise on L4 goals - it's a recognition that some bootstrap layer is mathematically irreducible.

---

## Security Requirements (9-Agent Adversary Review)

### 1. KERNEL_RESERVED_FIELDS Update (CRITICAL)

Before implementation, add these fields to `step_mu.py` KERNEL_RESERVED_FIELDS:

```python
# Bootstrap-structural bridge lookup phase fields (BootstrapStructuralBridge.v0.md)
"_lookup_name",        # Variable name being looked up
"_lookup_value",       # Value to compare against existing binding
"_lookup_bindings",    # Current position in bindings search
"_original_bindings",  # Preserved for adding new binding
```

**Why:** Without this, domain data could inject forged lookup state to bypass match validation.

### 2. Projection Ordering (SECURITY-CRITICAL)

Lookup phase projections MUST be ordered (first-match-wins):

1. `bridge.lookup.found_same` - Non-linear match for equal values
2. `bridge.lookup.found_different` - Catch-all for found but different (→ NO_MATCH)
3. `bridge.lookup.not_found_yet` - Continue searching bindings
4. `bridge.lookup.not_found` - End of bindings (→ add new binding)

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

New fields for bootstrap_structural (must be added to KERNEL_RESERVED_FIELDS before implementation):

| Field | Value/Type | Purpose |
|-------|------------|---------|
| `_phase` | `"lookup_binding"` | New phase value (field already exists) |
| `_lookup_name` | string | Variable name being looked up |
| `_lookup_value` | Mu | Value to compare against existing binding |
| `_lookup_bindings` | linked list | Current position in bindings search |
| `_original_bindings` | linked list | Preserved for adding new binding |

**Implementation checklist:**
1. [x] Add 4 new fields to `KERNEL_RESERVED_FIELDS` in `rcx_pi/selfhost/step_mu.py` (2026-02-02, 9-agent review)
2. [x] Add fields to JS equivalent in `mu/host/js/eval_step.js` (2026-02-02, 9-agent review)
3. [ ] Add test verifying domain data with these fields is rejected

---

## Success Criteria

1. [x] `mu/bridge/bootstrap_structural.v1.json` exists with 5 projections (2026-02-02)
2. [x] bridge.var.check_existing + lookup projections replace match.var behavior (2026-02-02)
3. [x] Parity tests: bridge gives same results as match.v2 for linear patterns (5 tests)
4. [x] Non-linear tests: bridge correctly detects binding conflicts (8 tests)
5. [x] `load_combined_kernel_with_bridge_projections()` wires bridge correctly (2026-02-03)
6. [x] Execution path verification tests: verify bridge projections are actually executed (2026-02-03)
7. [x] Cross-substrate parity: Python and JS bridge produce identical results (2026-02-04, tests/test_js_parity_automated.py)

**Note on "runs through step_kernel_mu":** The seeds recurrence.v1 and exhaustion.v1 can run through either:
- Bootstrap path: `eval_seed.step()` - Python provides binding conflict detection
- Meta-circular path: `step_kernel_mu()` with bridge projections - structural binding conflict detection

Both paths produce identical results. The execution path verification tests (`tests/test_execution_path_verification.py`) prove bridge projections fire when used.

---

## Test Vectors

### Linear Parity Tests (bridge == match.v2)

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `linear_ok` | `{"a": {"var": "x"}}` | `{"a": 1}` | Match, x=1 |
| `linear_nested` | `{"outer": {"inner": {"var": "x"}}}` | `{"outer": {"inner": 42}}` | Match, x=42 |
| `linear_list` | `[{"var": "h"}, {"var": "t"}]` | `[1, 2]` | Match, h=1, t=2 |
| `linear_catchall` | `{"var": "x"}` | `{"complex": [1, 2, 3]}` | Match, x={complex:[1,2,3]} |
| `linear_empty_dict` | `{"a": {"var": "x"}}` | `{"a": {}}` | Match, x={} |

### Non-Linear Detection Tests (binding conflict)

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `nonlinear_same` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 1, "b": 1}` | Match, x=1 |
| `nonlinear_diff` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 1, "b": 2}` | NO_MATCH |
| `nested_nonlinear` | `{"outer": {"inner": {"var": "x"}, "check": {"var": "x"}}}` | `{"outer": {"inner": 5, "check": 5}}` | Match, x=5 |
| `triple_same` | `{"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}` | `{"a": 1, "b": 1, "c": 1}` | Match, x=1 |
| `triple_one_diff` | `{"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}` | `{"a": 1, "b": 1, "c": 2}` | NO_MATCH |
| `nonlinear_list` | `[{"var": "x"}, {"var": "x"}]` | `[42, 42]` | Match, x=42 |
| `nonlinear_list_diff` | `[{"var": "x"}, {"var": "x"}]` | `[42, 43]` | NO_MATCH |
| `nonlinear_complex` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": {"nested": [1]}, "b": {"nested": [1]}}` | Match (structural equality) |

### Edge Cases

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `empty_bindings_first` | `{"var": "x"}` | `5` | Match, x=5 (first var, empty bindings) |
| `null_value_binding` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": null, "b": null}` | Match, x=null |
| `empty_list_match` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": [], "b": []}` | Match, x=[] |
| `type_mismatch` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": [1], "b": {"0": 1}}` | NO_MATCH (list ≠ dict) |

### Security Vectors

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `reserved_var_ok` | `{"a": {"var": "_mode"}}` | `{"a": "test"}` | Match (var name collision harmless) |
| `lookup_injection` | N/A | `{"_lookup_name": "x", "data": 1}` | REJECTED at kernel boundary |
| `ordering_critical` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 1, "b": 2}` | NO_MATCH (found_same before found_diff) |

### Cross-Substrate Parity Vectors (Python == JS)

| Vector | Pattern | Value | Expected |
|--------|---------|-------|----------|
| `parity_unicode` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": "🎉", "b": "🎉"}` | Match, x="🎉" |
| `parity_float` | `{"a": {"var": "x"}, "b": {"var": "x"}}` | `{"a": 3.14159, "b": 3.14159}` | Match, x=3.14159 |
| `parity_deep` | (3 levels) | (3 levels, same var twice) | Match (deep structural equality) |

---

## Implementation Sequence

1. **Design doc review** (this doc) - 9-agent review
2. **Create `mu/bridge/bootstrap_structural.v1.json`** with new projections
3. **Create parity tests** (bridge == match.v2 for linear patterns)
4. **Create non-linear tests** (binding conflict detection)
5. **Port to JS** and verify parity
6. **Update recurrence.v1 and exhaustion.v1** to use bridge
7. **Update execution_layer** declarations to META_CIRCULAR (completed in Gate 4 cutover)
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

- **v0.7 (2026-02-09):** B-structural match_mu direct usage
  - match_mu now uses match.v2 + bridge projections directly via projection_runner
  - Two execution paths documented: match_mu direct (Path 1) and kernel bridge mode (Path 2)
  - Fail-closed guard: step_mu/run_mu reject non-linear patterns with ValueError
  - 18 structural invariant tests added (test_match_bridge_invariants.py)
- **v0.6 (2026-02-08):** Gate 4 runtime wording corrected
  - Updated status language to reflect structural-default execution
  - Clarified bootstrap path is explicit debug fallback only
- **v0.5 (2026-02-03):** Algorithm execution layer clarification
  - **CRITICAL DISCOVERY:** Structural kernel normalizes to linked-list format, which breaks algorithm state
  - Algorithm projections (recurrence, exhaustion) require dict format with specific keys (e.g., `_state`, `_check_list`)
  - Normalization converts dict → linked-list kv-pairs, breaking pattern matching in algorithm projections
  - **Historical solution (superseded by Gate 4):** `step_algorithm_with_bridge()` provided Python bootstrap execution for algorithms
  - This was an intermediate transition stage before structural-default cutover
  - **Two execution layers now documented:**
    1. Structural layer: kernel + bridge + match.v2 + subst.v2 (production path after Gate 4)
    2. Bootstrap layer: explicit debug fallback (`execution_mode="bootstrap"`)
  - Path to true meta-circular algorithm execution required structural format standardization
  - Fixed subst entry format bug: changed `template` to `body` key in step_mu.py
- **v0.4 (2026-02-03):** Execution path verification added
  - Created `tests/test_execution_path_verification.py` with 9 tests
  - Tests prove bridge projections actually fire (not just correct behavior)
  - Fixed wiring: bridge projections come BEFORE match.v2 in combined kernel
  - Added Execution Path Verification section to AgentGuardrails.v0.md
  - Removed match.v3.json references (we use match.v2 + bootstrap_structural directly)
- **v0.3 (2026-02-02):** 9-agent review completed, security hardening applied
  - Added 4 reserved fields to KERNEL_RESERVED_FIELDS (Python + JS)
  - Expanded test vectors from 6 to 22 covering: linear parity, non-linear detection, edge cases, security, cross-substrate
  - All 9 agents: Verifier (APPROVE), Adversary (NEEDS HARDENING→fixed), Expert (MINIMAL), Structural-proof (DESIGN SOUND), Grounding (PARTIALLY_GROUNDED→fixed), Fuzzer (DESIGN COMPLETE), Translator (MATCHES_INTENT), Visualizer (3 DIAGRAMS), Advisor (PROMOTE TO NEXT)
- **v0.2 (2026-02-02):** Renamed from "Match v3" to "Bootstrap-Structural Bridge"
  - File: `mu/bridge/bootstrap_structural.v1.json`
  - Better reflects architectural role: bridge between bootstrap and structural execution
  - Projection IDs changed from `match.*` to `bridge.*`
- **v0.1 (2026-02-02):** Added Security Requirements section from 9-agent adversary review:
  - KERNEL_RESERVED_FIELDS update requirement
  - Projection ordering specification
  - Variable name collision mitigation
  - Security test vectors
  - L4 implications clarification ("BOOTSTRAP forever" is acceptable)
- **v0 (2026-02-02):** Initial design doc created after 9-agent review discovered match.v2/recurrence incompatibility

---

## Current Execution Architecture (2026-02-09)

### Runtime Layers

The bridge projections are IMPLEMENTED and VERIFIED to fire. Two primary paths use bridge projections:

**Path 1: match_mu Direct (B-structural, 2026-02-09)**
- `match_mu()` loads match.v2 + bridge projections (13 combined) via `projection_runner`
- `apply_mu()` calls `match_mu → subst_mu` — fast path with correct non-linear semantics
- No kernel overhead; bridge projections intercept variable binding for conflict detection
- `load_match_with_bridge_projections()` caches the combined set
- `make_projection_runner("match", terminal_field="_mode")` detects v2 terminal states

**Path 2: Kernel Bridge Mode (algorithm execution)**
- `run_algorithm_meta_circular()` dispatches to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Bridge projections provide non-linear pattern support inside structural execution
- This is the production path for recurrence/exhaustion

**Fail-Closed Guard (2026-02-09):**
- `step_mu()` and `run_mu()` reject non-linear patterns with `ValueError`
- Callers needing non-linear support must use `apply_mu()` (Path 1) or `run_algorithm_meta_circular()` (Path 2)
- See `tests/structural/test_match_bridge_invariants.py::TestSplitSemanticsContract`

**Fallback Layer: Bootstrap Debug Path**
- `execution_mode="bootstrap", allow_bootstrap_fallback=True` calls `step_algorithm_with_bridge()` for controlled debugging
- This path is no longer the default runtime

### Why This Architecture Exists

The fundamental issue is **format mismatch**:

```
Algorithm pattern: {"_state": {"var": "state"}, "_check_list": {...}}
After normalization: {head: {key: "_state", value: {...}}, tail: ...}
```

The algorithm pattern won't match the normalized format. Options considered:

1. **Rewrite algorithm projections in normalized format** - Complex, error-prone
2. **Use Python match/substitute for algorithms** - Current choice
3. **Add denormalization layer** - Tried, but body normalization breaks state

### Path to True Meta-Circular Algorithm Execution

To run algorithms through the full structural kernel, we need:

1. **Standardize on a single format** - Either all algorithms use linked-list format, OR normalization becomes optional
2. **Body normalization control** - Substitution normalizes bodies, which breaks algorithm state format
3. **Context-aware normalization** - Different behavior for match state vs algorithm state

**Current status:** The bridge provides structural non-linear support. Production algorithm execution defaults to structural kernel bridge mode via `run_algorithm_meta_circular(..., execution_mode="structural")`. Bootstrap algorithm execution remains explicit debug fallback only (`execution_mode="bootstrap", allow_bootstrap_fallback=True`).

---

## Open Questions

1. **Should bootstrap_structural replace match.v2 or coexist?**
   - **Answer (9-agent consensus):** Coexist initially, consider unification after 6+ months
   - match.v2 is simpler and sufficient for linear-only seeds
   - Seeds declare `"requires_patterns": ["non-linear"]` to request the bridge

2. **Is Option A (bootstrap the bootstrapper) acceptable for L4?**
   - **Answer (9-agent consensus):** Yes. This is analogous to Forth's NEXT or Lisp's EVAL
   - Some primitive must exist - the goal is minimizing it, not eliminating it
   - bootstrap_structural being BOOTSTRAP is acceptable and documented
   - L4 goal becomes: "minimize bootstrap layer to ~6 lines of auditable code"

3. **Should KERNEL_RESERVED_FIELDS be extended now?**
   - **Answer (adversary finding):** YES - must be extended BEFORE implementation
   - 4 new fields required (see Security Requirements section)
   - Without this, domain data can inject forged lookup state
