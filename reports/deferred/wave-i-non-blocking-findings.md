# Wave I Non-Blocking Findings (Deferred)

Collected from rigorous agent reviews (9 agents, 2026-03-11).
These do NOT block the meta-circularity claim but should be fixed.

**Resolution sweep: 2026-03-13. Stage0 items resolved by waves 4-9. O(N^2) perf resolved by wave 18. Compat shims resolved by wave 13. Fuzz gap + registry consistency resolved by wave 20. 11 RESOLVED, 1 DEFERRED (refactoring), 1 NO-GO (design ruling).**

## Performance

### _resolve_trace_projection_id O(N^2) per run
- **File:** step_mu.py lines 1408-1445
- **Issue:** Iterates all projections calling step_kernel_mu per projection to find which one matched. Called once per step in run_mu_structural. O(steps * projections).
- **Fix:** Modify step_kernel_mu to return matched projection ID in return_meta mode.
- **Status:** RESOLVED (Wave 18, 2026-03-13). Replaced with O(N) inline Stage 0 match. `_resolve_trace_projection_id` deleted from Python, `resolveTraceProjectionId` + `_resolveIdFast` deleted from JS. 7 L4 gate tests in `mu/tests/l4_gates/test_wave18_trace_id_resolution_gate.py`. ~78 LOC removed.
- **Agents:** structural-proof, expert, adversary, grounding

## Dead Code / Duplication

### _match_inner budget/depth path duplication (~150 LOC)
- **File:** eval_seed.py lines 334-506
- **Issue:** Budget path and depth path are near-identical type-dispatch logic duplicated.
- **Fix:** Extract shared helper or unify paths.
- **Status:** DEFERRED (founder decision, 2026-03-13) — Hot-path refactoring with low research value. Only inside a dedicated parity-locked refactor wave with before/after corpus replay.
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
- **Status:** RESOLVED (Wave 13, 2026-03-12). 29-name backward-compat re-export shim removed from step_mu.py. All callers migrated to direct engine_pipeline imports. KNOWN_COMPAT_SHIM and compatibility layer fully eliminated.
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
- **Status:** RESOLVED (Wave 20, 2026-03-13). 5 hypothesis fuzz tests in `mu/tests/fuzz/test_unbound_variable_stall.py` covering _stage0_substitute, substitute, and apply_projection unbound-variable paths. Both fail-closed (KeyError) and success paths tested.
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
- **Status:** NO-GO (founder decision, 2026-03-13) — Adding host validation in the execution path is the wrong direction. Seed body integrity comes from loader/bundle validation, not runtime policing. If the guarantee is weak, strengthen the loader contract, not the kernel semantics.
- **Agent:** fuzzer

## Architecture (Pre-existing, Acknowledged)

### Three parallel seed registries in seed_integrity.py
- **Issue:** SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS, MU_SEED_LOCATIONS maintained separately. No mechanical cross-check.
- **Fix:** Unify into single registry dict or add cross-validation test.
- **Status:** RESOLVED (Wave 20, 2026-03-13). 47 cross-validation tests in `mu/tests/engine/test_seed_registry_consistency.py` — CHECKSUMS↔PROJECTION_IDS↔LOCATIONS key alignment, SEED_STATUS subset check, SEED_DEPENDENCIES referential integrity + acyclicity, path resolution for all 18 seeds.
- **Agents:** advisor, structural-proof

### Dual code paths (_STAGE0_PILOT flag)
- **Status:** RESOLVED (Waves 4/9). `_STAGE0_PILOT` flag completely removed from both Python and JS. Stage0 is the sole production path.
- **Agent:** advisor
