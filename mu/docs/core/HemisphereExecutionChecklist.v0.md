<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-02-19
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_status_tasks_consistency.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Hemisphere Metabolization Execution Checklist v0

**Status:** NEXT (promoted from VECTOR P1, 2026-02-19)
**Design doc:** `roadmap/MuHemispheresDesign.md` (Section: FUTURE_TARGET: Hemisphere Metabolization Contract)
**Predecessor:** Boot1 Recursive Loop Contract (`mu/docs/core/Boot1LoopContract.v0.md`) — same E1-E5 pattern

---

## Purpose

This checklist defines the evidence gates (E1-E5) required to close the Hemisphere Metabolization Contract in NEXT. Each gate has explicit pass/fail criteria and a verification command. No gate may be marked MET without a passing test or evidence artifact.

This follows the same E1-E5 pattern used for Boot1 (shadow-merge scope) and GAP-10-LOOP.

---

## Scope (Bounded)

**In scope:**
- Metabolization projections: sink re-expression cycle (sink -> metabolization -> storage -> residual -> sink)
- Truth-table tests for T1-T10 transitions (from design doc)
- Adversarial edge cases (from design doc: at least 3 adversarial scenarios)
- Python and JS parity for metabolization projections
- Engine exception policy Option B: shadow-only (not activated as default)

**Out of scope:**
- Engine exception policy Option B activation (default flip) — requires separate promotion
- L4 implications of metabolization
- Performance optimization of hemisphere routing

---

## Evidence Gates

### E1: Metabolization Projections Exist (Python)

**Criterion:** Metabolization projections are defined in a seed file and loaded by the Python substrate.

**Pass condition:**
- Seed file exists (e.g., `mu/programs/metabolization.v1.json` or additions to `hemispheres.v1.json`)
- Projections implement sink re-expression cycle (at minimum: sink-classify, metabolize-null, metabolize-inf, store-result, residual-return)
- Projections loaded and verified by `seed_integrity.py`

**Evidence command:** `pytest tests/engine/test_seed_integrity.py -k metabolization`

**Contract test:** `tests/structural/test_hemisphere_metabolization_contract.py` — locks 6 projection IDs, T1-T10 truth table, S1-S5 invariants against design doc.

**Status:** E1 MET (2026-02-20). Seed file `mu/programs/metabolization.v1.json` created with 6 projections. Registered in `seed_integrity.py` (checksum + expected IDs + location). All 15 contract tests pass (11 ground truth + 4 seed existence). `load_verified_seed()` verifies integrity.

### E2: Metabolization Projections Exist (JavaScript)

**Criterion:** Same metabolization projections are loaded and functional in the JS substrate.

**Pass condition:**
- JS substrate loads the metabolization seed file
- JS inline tests verify projection behavior matches Python
- `node mu/host/js/eval_step.js` passes all metabolization tests

**Evidence command:** `node mu/host/js/eval_step.js` (metabolization tests section)

**Status:** PARTIAL (2026-02-20). JS substrate loads metabolization.v1.json with full integrity verification (SHA256 checksum, structure validation, projection ID ordering). Seed wiring complete. JS inline metabolization behavior tests not yet written — remaining for E2 closure.

### E3: Truth-Table Coverage (T1-T10 + Adversarial)

**Criterion:** All 10 designed transitions and at least 3 adversarial cases are test-locked.

**Pass condition:**
- T1-T10 transitions from design doc each have at least 1 test
- At least 3 adversarial edge cases tested (e.g., double-metabolization, empty sink, malformed residual)
- All 5 hemisphere buckets (r_null, r_inf, r_a, lobes, sink) appear in test coverage
- Tests run in both Python and JS (cross-substrate parity)

**Evidence command:** `pytest tests/parity/test_hemisphere_metabolization_parity.py -v` (or equivalent)

**Status:** NOT STARTED

### E4: Security and Invariant Tests

**Criterion:** Metabolization cannot violate hemisphere routing invariants or introduce new attack surfaces.

**Pass condition:**
- Metabolization respects existing hemisphere routing priority order
- No new bootstrap primitives introduced
- No new KERNEL_RESERVED_FIELDS required
- Engine exception policy Option B (if shadowed) does not alter default engine behavior
- Sink-safety invariants S1-S5 (from design doc) each have at least 1 test

**Evidence command:** `pytest tests/structural/ -k "metabolization or hemisphere" -v`

**Status:** NOT STARTED

### E5: Governance Closure

**Criterion:** All governance artifacts are updated to reflect metabolization completion.

**Pass condition:**
- TASKS.md NEXT entry marked COMPLETE with evidence summary
- This checklist updated with LAST_VERIFIED date
- STATUS.md reflects metabolization completion
- Tracker sync note added to Ra
- Boot1LoopContract.v0.md and this doc cross-referenced where applicable

**Evidence command:** `pytest tests/docs/test_status_tasks_consistency.py -v`

**Status:** NOT STARTED (this gate closes last)

---

## Constraints

1. **Shadow-only:** Metabolization projections exist and are testable, but engine exception policy Option B is NOT activated as the default. This mirrors Boot1's shadow-merge approach.
2. **No new primitives:** Metabolization must work within the existing 4 bootstrap primitives.
3. **Parity required:** Python and JS must produce identical results for all metabolization transitions.
4. **Projection-first:** Metabolization logic must be expressed as Mu projections (seed data), not host code. Host code may provide the execution loop (like `run_engine_pipeline`), but routing decisions must be structural.

---

## Timeline

This checklist does not include time estimates. Gates are completed in order (E1 before E2, etc.) with E5 closing last. See TASKS.md for current execution status.
