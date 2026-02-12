# Algorithm State Normalization Spec (Draft v0)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines DESIGN only. Draft specs live in `roadmap/`; approved specs migrate to `docs/core/`.

Status: **Gate 1 complete** (2026-02-04). Open questions resolved. Ready for approval and migration to `docs/core/`.

**Note (2026-02-10):** This spec describes the base normalization rules for recurrence.v1. Since Gate 1, `recurrence.v2.json` was created with hash-accelerated closure detection (boundary hashing via `hash_trace_for_recurrence()`). v2 adds `state_hash` fields to trace entries but does not change the normalization rules defined here. See `docs/core/recurrence_v2_design.md` and `roadmap/ContentAddressedMu.md` for the v2 evolution.

## Purpose
Define a single canonical normalized representation for algorithm state used by recurrence, exhaustion, and rcx_engine so these algorithms can run via structural match/subst without hybrid host execution.

## Scope
1. Normalized representation rules for Mu lists and Mu dicts.
2. Canonical algorithm state schemas (recurrence, exhaustion, rcx_engine).
3. Trace representation requirements.
4. Execution-layer requirements and test obligations.

## Non-Goals
1. No changes to algorithm semantics.
2. No Boot0 encoding or compiler work.
3. No performance optimization work.

## Definitions
1. **Raw algorithm state**: JSON-like structures authored in seeds.
2. **Normalized form**: Output of `normalize_for_match()` (and JS equivalent) used by structural match/subst.
3. **Mu list**: Linked list form with `head` and `tail` (and `_type: "list"` for host lists).
4. **Mu dict**: Linked list of key-value pairs with `_type: "dict"`.

## Canonical Normalization Rules
1. **Scalars** (`null`, booleans, numbers, strings) are unchanged.
2. **Lists** are encoded as:
   - Non-empty: `{ "_type": "list", "head": <item>, "tail": <next> }`
   - Empty: `{ "_type": "list" }`
3. **Dicts** are encoded as:
   - Non-empty: `{ "_type": "dict", "head": <kv>, "tail": <next> }`
   - Empty: `{ "_type": "dict" }`
4. **Key-value pairs** are encoded as a 2-element list:
   - `{ "head": <key>, "tail": { "head": <value>, "tail": null } }`
5. **Ordering is structural**:
   - Dict key order is the explicit linked-list order of kv-pairs.
   - Projection code must build dicts as linked lists in a defined order.
6. **Canonical dict order (Gate 3 contract)**:
   - Normalization MUST order dict keys lexicographically (`sorted()` in Python, `Array.sort()` in JS).
   - All normalized algorithm projections MUST match this exact linked-list order.
   - This is a Gate 3 contract; L4 may later add order-independent field access projections.
7. **Variable sites** remain literal `{"var": "x"}` in patterns.
8. **Reserved kernel fields** remain prohibited in domain inputs.
   - Validation MUST inspect keys inside normalized dict encodings (kv-pair keys),
     not just raw dict keys, to prevent bypass.
9. **List `_type` matching (Gate 3 behavior)**:
   - Patterns may omit `_type` when matching normalized **lists**.
   - Patterns for normalized **dicts** MUST include `_type:"dict"` explicitly.

## Trace Representation
1. Trace is a Mu linked list with `head` and `tail`.
2. Each entry is a Mu dict with required fields: `step`, `state`, `projection`.
3. Optional fields include `stall` and `max_steps` where applicable.
4. Trace entries must be deterministic and structural (no host-only metadata).

## Algorithm State Schemas (Raw View)

### Recurrence
**Input (raw):**
```
{
  "_detect_closure": {
    "trace": <Mu linked list>,
    "result": <Mu value>
  }
}
```
**Internal fields (raw names used by projections):**
`_mode`, `_phase`, `_current`, `_seen`, `_rest`, `_check_list`, `_state`, `_tau_step`, `_closure`, `_result`, `closure_detected`, `final_result`, `tau_step`.

**Canonical rule:** the normalized recurrence state is exactly `normalize_for_match(raw_state)`.

**Minimal normalized example (recurrence input):**
```json
{
  "_type": "dict",
  "head": {
    "head": "_detect_closure",
    "tail": {
      "head": {
        "_type": "dict",
        "head": {
          "head": "result",
          "tail": {
            "head": "A",
            "tail": null
          }
        },
        "tail": {
          "head": {
            "head": "trace",
            "tail": {
              "head": null,
              "tail": null
            }
          },
          "tail": null
        }
      },
      "tail": null
    }
  },
  "tail": null
}
```

### Exhaustion
**Input (raw):**
```
{
  "_detect_exhaustion": {
    "trace": <Mu linked list>,
    "frozen": <Mu linked list or null>,
    "tau_step": <Mu value or null>,
    "operator_ids": <Mu linked list>
  }
}
```
**Internal fields (raw names used by projections):**
`_mode`, `_phase`, `_trace`, `_operator`, `_operator_ids`, `_frozen`, `_tau_operator`, `_tau_step`, `action`, `exhaustion_detected`, `operator_to_freeze`, `frozen`.

**Canonical rule:** the normalized exhaustion state is exactly `normalize_for_match(raw_state)`.

### RCX Engine
**Input (raw):**
```
{
  "_run_engine": {
    "projections": <list of projection dicts>,
    "input": <Mu value>
  }
}
```
**Internal fields (raw names used by projections):**
`_mode`, `_phase`, `_projections`, `_input`, `_max_steps`, `_trace_result`, `_recurrence_result`, `_exhaustion_result`, `_frozen`, `_engine_context`, `_engine_recurrence`.

**Canonical rule:** the normalized engine state is exactly `normalize_for_match(raw_state)`.

## Execution-Layer Requirements
1. After refactor, recurrence and exhaustion must declare `execution_layer: META_CIRCULAR` and be proven via execution-path tests.
2. Structural execution must be the default path for algorithms; hybrid execution is not allowed outside debug or migration gates.
3. JS parity must load the same normalized seeds and use equivalent normalization semantics.

## Migration and Refactor Plan
1. Gate 0 through Gate 5 in `roadmap/MetaCircular_Boot0_GatePlan.md` define the sequence.
2. During Gate 2, adapters may normalize raw inputs at algorithm entry.
3. After Gate 4, adapters should be removed or strictly gated.

## Test Requirements
1. Round-trip normalization tests for algorithm state during migration.
2. Execution-path tests that fail if structural match/subst are not used.
3. Updated parity vectors for recurrence/exhaustion and JS parity cross-checks.

## Open Questions (Resolved 2026-02-04)

**These questions have been answered. Gate 1 exit criteria met.**

1. Should engine outputs remain normalized end-to-end, or is denormalization permitted only at external I/O boundaries?
   - **Answer:** **Option B - Denormalize at external I/O boundaries only.**
   - Internal execution remains fully normalized (structural purity).
   - Denormalization occurs only when outputting to users, logs, or external tools.
   - This provides a single clean boundary and avoids dual-path drift.

2. Is there any algorithm state that must remain raw for observability tooling?
   - **Answer:** **Option A - No exceptions.**
   - All internal state is normalized. Observability tools consume denormalized output.
   - No alternate raw truth path exists (prevents drift from structural runtime).
   - The denormalizer becomes the sole readability boundary.

## Denormalizer Requirements (Added per Gate 1 review)

The denormalizer (`denormalize_for_output()` and JS equivalent) is part of the trusted I/O boundary:

1. **Deterministic**: Same normalized input must always produce identical denormalized output.
2. **Tested**: Round-trip tests required (`normalize → denormalize → normalize` must be stable).
3. **Audited**: Changes to denormalizer require full 9-agent review (it's a trust boundary).
4. **Parity**: Python and JS denormalizers must produce identical output for same input.

## Cross-Substrate Parity Requirement (MANDATORY)

**Parity scope:**
- **REQUIRED** = normalize/denormalize equivalence + projection execution results
- **NOT REQUIRED** = adapter-level validation (temporary Python-only migration scaffolding)

**HARD REQUIREMENT**: The JavaScript bootstrap must produce identical results to Python for all in-scope operations. This is not optional.

Rationale:
- JS is the "smaller bootstrap" that proves substrate independence
- If JS and Python diverge, we have two different runtimes (not one portable system)
- Any parity violation is a blocking bug that must be fixed before proceeding

Required parity tests:
1. `test_python_js_normalization_matches` - normalize/denormalize round-trip parity
2. `test_actual_cross_substrate_comparison` - projection execution parity
3. `test_python_js_constants_match` - MAX_DEPTH, KERNEL_RESERVED_FIELDS parity

When adding new functionality:
1. Add to Python first
2. Add equivalent to JS
3. Add cross-substrate parity test
4. Both must pass before merge

Test location: `tests/test_js_parity_automated.py`
