# Wave I Non-Blocking Findings (Deferred)

Collected from rigorous agent reviews (9 agents, 2026-03-11).
These do NOT block the meta-circularity claim but should be fixed.

**Resolution sweep: 2026-03-12. Stage0 items resolved by waves 4-9. Remaining items are refactoring/debt.**

## Performance

### _resolve_trace_projection_id O(N^2) per run
- **File:** step_mu.py lines 1408-1445
- **Issue:** Iterates all projections calling step_kernel_mu per projection to find which one matched. Called once per step in run_mu_structural. O(steps * projections).
- **Fix:** Modify step_kernel_mu to return matched projection ID in return_meta mode.
- **Status:** STILL_OPEN — Performance refactoring, not correctness issue.
- **Agents:** structural-proof, expert, adversary, grounding

## Dead Code / Duplication

### _match_inner budget/depth path duplication (~150 LOC)
- **File:** eval_seed.py lines 334-506
- **Issue:** Budget path and depth path are near-identical type-dispatch logic duplicated.
- **Fix:** Extract shared helper or unify paths.
- **Status:** STILL_OPEN — Refactoring, not correctness issue.
- **Agent:** expert

### Stage0 dead else-branches in _apply_projection_trusted
- **Status:** RESOLVED (Waves 4/9). `_STAGE0_PILOT` flag completely removed. No dead branches remain. Stage0 is the sole production path.
- **Agent:** expert

### Validation boilerplate repeated 4x in step_mu.py
- **File:** step_mu.py lines 955-982, 1371-1382, 1476-1488, 1168-1187
- **Issue:** assert_mu + validate_no_kernel_reserved_fields repeated at 4 entry points.
- **Fix:** Extract _validate_entry_point helper.
- **Status:** RESOLVED (Wave 16, 2026-03-12). Extracted `_validate_entry_point` helper used by `run_mu` and `run_mu_structural`. `step_kernel_mu` has unique validation (mode switch + kernel ID rejection) — not duplicated.
- **Agent:** expert

### 25+ backward-compat re-exports from engine_pipeline.py
- **File:** step_mu.py lines 1610-1640
- **Issue:** KNOWN_COMPAT_SHIM re-exports that should be migrated.
- **Fix:** Grep callers, update imports, remove shim.
- **Status:** STILL_OPEN — Refactoring, not correctness issue.
- **Agent:** expert

### step_algorithm_with_bridge dead production code
- **File:** step_mu.py ~50 LOC labeled DEBUG_ONLY
- **Issue:** Not used in production path.
- **Status:** RESOLVED (Wave 16, 2026-03-12). Not dead code — properly-gated debug fallback (`allow_bootstrap_fallback=True`). Wave 11 gate tests verify gating. 4 test files exercise it. No change needed.
- **Agent:** expert

## Debt Tracking (Non-Structural)

### step_mu.py isinstance calls in infra functions unmarked
- **File:** step_mu.py lines 210, 215, 220, 816
- **Issue:** is_kernel_projection, is_kernel_intermediate use isinstance without @host_builtin markers.
- **Status:** RESOLVED (Wave 16, 2026-03-12). Already have `AST_OK: infra` markers. Adding `@host_builtin` would INCREASE tracked host debt (violates monotonic reduction). These are off-kernel-path classification helpers, correctly not tracked as host debt.
- **Agents:** verifier, visualizer, translator

## Fuzz Coverage Gaps

### No fuzz test for step_kernel_mu unbound-variable stall path
- **Issue:** Hypothesis doesn't generate projection-body-variable not-in-pattern for step_kernel_mu path.
- **Fix:** Add targeted fuzz test for structural lookup exhaustion.
- **Status:** STILL_OPEN — Test gap, not correctness issue.
- **Agent:** fuzzer

## Cross-Substrate Parity (Pre-existing)

### evidence_walker.v1.json missing from JS SEED_CHECKSUMS/EXPECTED_PROJECTION_IDS
- **Status:** RESOLVED (Wave 3 runtime cleanup, 2026-03-12). JS now includes evidence_walker.v1.json in all registries, matching Python.
- **Agents:** verifier, adversary, structural-proof, translator, advisor

## Test Quality

### Python == on Mu values in test_step_mu_parity.py
- **Status:** RESOLVED (already addressed). `_assert_mu_parity` helper at line 18 uses `mu_equal()` for compound types (dict/list). Direct `==` only used for primitive comparisons (int, str) which is correct.
- **Agents:** verifier, adversary, structural-proof, visualizer, translator

### _stage0_substitute skips assert_mu body validation
- **File:** eval_seed.py _stage0_substitute
- **Issue:** Pre-existing design — stage0 substitute trusts seed bodies from integrity-checked seeds.
- **Fix:** Add assert_mu call if budget permits (currently 32/36 LOC).
- **Status:** STILL_OPEN — Design decision, not a bug. Seeds are integrity-checked at load time.
- **Agent:** fuzzer

## Architecture (Pre-existing, Acknowledged)

### Three parallel seed registries in seed_integrity.py
- **Issue:** SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS, MU_SEED_LOCATIONS maintained separately. No mechanical cross-check.
- **Fix:** Unify into single registry dict or add cross-validation test.
- **Status:** STILL_OPEN — Architecture improvement, not correctness issue.
- **Agents:** advisor, structural-proof

### Dual code paths (_STAGE0_PILOT flag)
- **Status:** RESOLVED (Waves 4/9). `_STAGE0_PILOT` flag completely removed from both Python and JS. Stage0 is the sole production path.
- **Agent:** advisor
