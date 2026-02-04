# Tooling Delta Checklist (8 → 9+)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document tracks tooling improvements only. Does not define gates or milestones.

Track tooling improvements to move quality score from ~8 to 9+.
Created: 2026-02-04

---

## Completed Items

### Parity Constants Coverage (DONE)
- Added `MAX_MU_WIDTH` to `test_js_parity_automated.py` constants check
- **Commit**: 2026-02-04
- **Test**: `test_python_js_constants_match` now verifies MAX_DEPTH, MAX_WIDTH, and KERNEL_RESERVED_FIELDS

### Head/Tail Policy Parity (DONE)
- Added parity test documenting "classify" policy for `{head: X, tail: Y}` structures
- **Decision**: CLASSIFY (treat as linked-list format)
- **Test**: `test_head_tail_classify_policy_parity` in test_js_parity_automated.py
- **Rationale**: Both substrates implicitly treat head/tail as linked-list. This is intentional.
  Domain data using those keys will be classified as linked-list. This is documented behavior.

### Projection Validation Parity (DONE)
- Python projection reserved-field validation in place
- Tests explicitly cover kernel projection rejection
- **Commit**: Gate 2 (PR #197)

### JS Mu Validation Parity (DONE)
- Depth/width guards in JS `isValidMu`
- Locked with tests in `test_js_mu_validation_parity`
- **Commit**: Gate 2 (PR #197)

### Doc Accuracy Drift (DONE)
- "Known Architectural Constraints" documented in MetaCircular_Boot0_GatePlan.md
- STATUS.md "last verified" pointer added linking to gate plan constraints section

---

## Pending Items

### CI Timing Hygiene (Medium)
- Keep fast audit required; run heavy fuzzers on dev-merge or nightly
- Document expected CI timing ranges so slow runs aren't treated as regressions

**Acceptance Criteria**:
1. Add `docs/ci/CI_TIMING_EXPECTATIONS.md` with timing baselines
2. Update CI workflow with timing annotations
3. Add warning threshold (not failure) for slow runs

### Coverage Visibility (Medium)
- Make `projection_coverage` produce a CI artifact or summary (JSON blob)
- Add lightweight check that no projection is never hit across core tests

**Acceptance Criteria**:
1. `tools/projection_coverage.py` outputs JSON summary
2. CI uploads coverage artifact
3. Test fails if any projection has 0 hits in core test suite

---

## Policy Decisions

### Head/Tail Classification (Decided: CLASSIFY)

**Options considered**:
1. **CLASSIFY**: Treat `{head: X, tail: Y}` as linked-list format always
2. **PRESERVE**: Only treat as linked-list if explicitly tagged or in known contexts

**Decision**: CLASSIFY (current implicit behavior)

**Rationale**:
- Both substrates already do this implicitly
- Changing would break existing normalization round-trips
- Domain data rarely uses "head" and "tail" as simultaneous keys
- If someone needs dict keys named head/tail, they can use different names

**Documented in**: `test_head_tail_classify_policy_parity` test

---

## Dependencies

- CI timing hygiene can be done in parallel with Gate 3
- Coverage visibility can be done in parallel with Gate 3
- Neither blocks Gate 3 progress
