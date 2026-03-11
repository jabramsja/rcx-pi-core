# Wave I Non-Blocking Findings (Deferred)

Collected from rigorous agent reviews (9 agents, 2026-03-11).
These do NOT block the meta-circularity claim but should be fixed.

Updated after second rigorous run (post-fix, 2026-03-11).

## Performance

### _resolve_trace_projection_id O(N^2) per run
- **File:** step_mu.py lines 1408-1445
- **Issue:** Iterates all projections calling step_kernel_mu per projection to find which one matched. Called once per step in run_mu_structural. O(steps * projections).
- **Fix:** Modify step_kernel_mu to return matched projection ID in return_meta mode.
- **Agents:** structural-proof, expert, adversary, grounding

## Dead Code / Duplication

### _match_inner budget/depth path duplication (~150 LOC)
- **File:** eval_seed.py lines 334-506
- **Issue:** Budget path and depth path are near-identical type-dispatch logic duplicated.
- **Fix:** Extract shared helper or unify paths.
- **Agent:** expert

### Stage0 dead else-branches in _apply_projection_trusted
- **File:** eval_seed.py lines 854-865
- **Issue:** _STAGE0_PILOT = True permanently. else branches are dead code.
- **Fix:** Remove flag and dead branches once Stage0 is permanently committed.
- **Agent:** expert

### Validation boilerplate repeated 4x in step_mu.py
- **File:** step_mu.py lines 955-982, 1371-1382, 1476-1488, 1168-1187
- **Issue:** assert_mu + validate_no_kernel_reserved_fields repeated at 4 entry points.
- **Fix:** Extract _validate_projection_list helper (~60 LOC eliminated).
- **Agent:** expert

### 25+ backward-compat re-exports from engine_pipeline.py
- **File:** step_mu.py lines 1610-1640
- **Issue:** KNOWN_COMPAT_SHIM re-exports that should be migrated.
- **Fix:** Grep callers, update imports, remove shim.
- **Agent:** expert

### step_algorithm_with_bridge dead production code
- **File:** step_mu.py ~50 LOC labeled DEBUG_ONLY
- **Issue:** Not used in production path.
- **Fix:** Remove or gate behind explicit debug flag.
- **Agent:** expert

## Debt Tracking (Non-Structural)

### step_mu.py isinstance calls in infra functions unmarked
- **File:** step_mu.py lines 210, 215, 220, 816
- **Issue:** is_kernel_projection, is_kernel_intermediate use isinstance without @host_builtin markers.
- **Fix:** Add markers or AST_OK annotations. Update baseline.
- **Agents:** verifier, visualizer, translator

## Fuzz Coverage Gaps

### No fuzz test for step_kernel_mu unbound-variable stall path
- **Issue:** Hypothesis doesn't generate projection-body-variable not-in-pattern for step_kernel_mu path.
- **Fix:** Add targeted fuzz test for structural lookup exhaustion.
- **Agent:** fuzzer

## Cross-Substrate Parity (Pre-existing)

### evidence_walker.v1.json missing from JS SEED_CHECKSUMS/EXPECTED_PROJECTION_IDS
- **File:** mu/host/js/cli/main.js
- **Issue:** Python seed_integrity.py has evidence_walker.v1.json in all registries. JS has 13 seeds but not evidence_walker. Pre-existing gap, not introduced by Wave I.
- **Fix:** Add evidence_walker.v1.json to JS SEED_CHECKSUMS and EXPECTED_PROJECTION_IDS.
- **Agents:** verifier, adversary, structural-proof, translator, advisor

## Test Quality

### Python == on Mu values in test_step_mu_parity.py
- **File:** mu/tests/parity/test_step_mu_parity.py
- **Issue:** All ~20 parity assertions use Python `==` instead of `mu_equal`. mu_equal not imported. For simple shapes (int, str, flat dict) this is correct, but philosophically undermines parity claim.
- **Fix:** Import mu_equal and use for dict/list assertions. Keep `==` for primitives.
- **Agents:** verifier, adversary, structural-proof, visualizer, translator

### _stage0_substitute skips assert_mu body validation
- **File:** eval_seed.py _stage0_substitute
- **Issue:** Pre-existing design — stage0 substitute trusts seed bodies from integrity-checked seeds.
- **Fix:** Add assert_mu call if budget permits (currently 32/36 LOC).
- **Agent:** fuzzer

## Architecture (Pre-existing, Acknowledged)

### Three parallel seed registries in seed_integrity.py
- **Issue:** SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS, MU_SEED_LOCATIONS maintained separately. No mechanical cross-check.
- **Fix:** Unify into single registry dict or add cross-validation test.
- **Agents:** advisor, structural-proof

### Dual code paths (_STAGE0_PILOT flag)
- **File:** eval_seed.py
- **Issue:** _STAGE0_PILOT = True permanently. Non-pilot code paths are dead.
- **Fix:** Remove flag and dead branches (see also "Stage0 dead else-branches" above).
- **Agent:** advisor
