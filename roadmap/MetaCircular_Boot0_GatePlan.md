# Meta-Circular and Boot0-Aligned Gate Plan (Draft)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines SEQUENCE and EXIT CRITERIA only. Gate completion updates TASKS.md, not this file.

This is a sequential gate plan with explicit dependencies and exit criteria. Gates must be completed in order.

**Gate Levels:**
- Gates 1, 0, 2–5: L2/L3 (structural algorithm execution)
- Gates 6–8: L4 (boot chain / substrate independence)

**Execution Order (9-agent reviewed 2026-02-04):**
> Gate 1 (spec) → Gate 0 (baseline freeze) → Gate 2 (adapters) → Gate 3 (seed rewrite) → Gate 4 → Gate 5
>
> Rationale: Spec can be written without risk; baseline freeze should be immediately before code changes to avoid checkpoint drift.

---

## Gate 1: Canonical Algorithm Normalization Spec ✅ COMPLETE
Goal: define the normalized schema for algorithm state.

**Status:** COMPLETE (2026-02-04). Spec at `roadmap/AlgorithmNormalizationSpec.v0.md`.

Work:
1. Write a full spec in `roadmap/AlgorithmNormalizationSpec.v0.md` for normalized algorithm state.
2. Define canonical normalized forms for `_detect_closure`, `_detect_exhaustion`, trace lists, and mode or phase fields.
3. Include at least one short JSON example for each normalized algorithm state.
4. Resolve open questions in spec (output denormalization boundaries, observability exceptions).

Exit criteria:
1. Spec exists and is reviewed.
2. Normalized examples are included and unambiguous.
3. All open questions have explicit answers (no TBD items remain).

---

## Gate 0: Baseline Freeze ✅ COMPLETE
Goal: lock current behavior and verify parity baselines before refactor.

**Status:** COMPLETE (2026-02-04). Baseline at `roadmap/Gate0_Baseline_2026-02-04.md`.

**Timing:** Run immediately before Gate 2 begins. Do not run standalone.

Work:
1. Run and record baseline results for `tests/test_recurrence_parity.py`.
2. Run and record baseline results for `tests/test_exhaustion_parity.py`.
3. Run and record baseline results for `tests/test_meta_circular_gate6.py`.
4. Run and record baseline results for `tests/test_execution_path_verification.py`.
5. Run and record baseline results for `tests/test_js_parity_automated.py`.
6. Snapshot current seed checksums in `rcx_pi/selfhost/seed_integrity.py`.

Exit criteria:
1. All baseline tests pass on current main.
2. Checksums match current seeds.

---

## Gate 2: Normalization Adapters ✅ COMPLETE
Goal: implement safe conversion between raw algorithm state and normalized form.

**Status:** COMPLETE (2026-02-04). Adapters at `rcx_pi/selfhost/algorithm_adapters.py`, tests at `tests/structural/test_algorithm_normalization.py` (29 tests).

Work:
1. Add adapter functions in `rcx_pi/selfhost/step_mu.py` or a dedicated helper module.
2. Add round-trip tests in `tests/structural/test_algorithm_normalization.py`.

Exit criteria:
1. Round-trip normalization tests pass.
2. No existing behavior changes before seed refactor.
3. **Adapter window closure rule:** Adapters must be removed or strictly gated before Gate 4 begins (hard requirement per adversary review).
4. **Parity scope:** REQUIRED = normalize/denormalize equivalence + projection execution. NOT REQUIRED = adapter-level validation (temporary Python-only scaffolding).

---

## Gate 3: Rewrite Algorithm Seeds for Normalized State
Goal: make recurrence and exhaustion projections operate on normalized state.

Work:
1. Update `mu/closures/recurrence.v1.json` for normalized input and output.
2. Update `mu/closures/exhaustion.v1.json` for normalized input and output.
3. Update checksums and expected projection IDs in `rcx_pi/selfhost/seed_integrity.py`.
4. Add fuzzer tests for edge cases identified in 9-agent review.

Exit criteria:
1. `tests/test_recurrence_parity.py` passes under the hybrid path.
2. `tests/test_exhaustion_parity.py` passes under the hybrid path.
3. **Fuzzer edge cases pass (9-agent review 2026-02-04):**
   - `test_large_frozen_list_stress` - exhaustion with 50-100 pre-frozen operators
   - `test_multi_state_cycle_detection` - recurrence with 3-5 state cycles (not just oscillation)
   - `test_quadruple_nonlinear_var` - 4+ occurrences of same variable in pattern
   - `test_mixed_linear_nonlinear_patterns` - combined linear and non-linear vars in same pattern

---

## Gate 4: Structural Algorithm Execution
Goal: remove Python match or substitute from algorithm execution.

Work:
1. Update `run_algorithm_meta_circular()` to use structural match and substitute.
2. Remove or strictly gate the hybrid path as a debug-only fallback.
3. Update `tests/test_meta_circular_gate6.py` to require the structural path.

Exit criteria:
1. Recurrence and exhaustion pass under structural execution only.
2. Execution-path tests prove structural projections were used.
3. Gate 2 adapter window is confirmed closed (no adapter code in production path).

**Optional:** If touching `run_algorithm_meta_circular()`, consider renaming to clarify execution path (per translator review).

---

## Known Architectural Constraints (Gate 2–5 Context)

These are **intentional constraints** in the current architecture. They are **not bugs**. They exist until Gates 3–5 are completed.

### 1. Kernel reserved fields block algorithm entry

Algorithm states use fields like `_detect_closure`, `_detect_exhaustion`, `_mode`, `_phase`.
`step_kernel_mu()` rejects any input containing reserved kernel fields.
**Result:** algorithm states **cannot enter the kernel**, so algorithms run via bootstrap `match/substitute`.

### 2. Kernel-internal bypass exists to keep hybrid execution safe

`eval_seed._is_kernel_internal_state()` treats `_mode`/`_phase` states as kernel-internal and skips deep Mu validation.
This keeps hybrid execution viable but **allows non-Mu values to slip through**.
This bypass must be removed once algorithms run structurally.

### 3. Trace "matched_id" uses a different matcher than execution

`run_mu_structural()` uses `match.v1` (via `match_mu`) to find `matched_id`, but execution uses kernel + `match.v2`.
If v1 and v2 diverge, traces can misreport which projection fired.

### Resolution Path

- **Gate 3:** Rewrite algorithm state format (or define an algorithm-specific entry path) so it no longer conflicts with kernel reserved fields.
- **Gate 4:** Run recurrence/exhaustion through structural kernel + bridge.
- **Gate 5:** Remove `_is_kernel_internal_state` bypass and align trace matching with the execution path.

**Note:** Gate 2 adapters do **not** remove these constraints. They only prepare the migration.

---

## Gate 5: Full Meta-Circular Parity
Goal: confirm no semantic drift after structural execution.

Work:
1. Add parity tests that compare structural execution to prior baseline outputs.
2. Ensure JS parity remains green for the same vectors.

Exit criteria:
1. All parity tests pass with structural execution.
2. Cross-substrate parity remains intact.

**Milestone:** After Gate 5, hemisphere implementation may proceed (currently blocked).

---

## Gate 6: Boot0-Aligned Seed Encoding
Goal: define minimal seed encoding and compiler.

Work:
1. Define the minimal encoding spec.
2. Add `tools/compile_seeds.py` to compile to current JSON format.
3. Add round-trip tests in `tests/test_seed_minimal_roundtrip.py`.

Exit criteria:
1. Minimal encoding spec and compiler exist.
2. Round-trip equivalence passes.

## Gate 7: Boot1 Minimal Evaluator
Goal: implement a tiny evaluator for kernel, match, and subst.

Work:
1. Add a minimal evaluator under `rcx_pi/boot1/` or equivalent.
2. Add parity tests versus `eval_seed.step`.

Exit criteria:
1. Boot1 evaluator passes parity for kernel, match, and subst.

## Gate 8: Full Boot Chain
Goal: demonstrate end-to-end bootstrap chain.

Work:
1. Build Boot0 loader to Boot1 evaluator to load kernel, bridge, and closures.
2. Verify recurrence and exhaustion run structurally via Boot1.
3. Add `scripts/bootstrap_chain.sh`.

Exit criteria:
1. End-to-end chain produces identical outputs to the current Python substrate.

## Timeline Summary (Gantt-Style)

**Execution order (reordered per 9-agent review):**
```
L2/L3 GATES (Active):
Gate 1: Normalization Spec      [##]       ✅ COMPLETE (2026-02-04)
Gate 0: Baseline Freeze         [##]       ✅ COMPLETE (2026-02-04)
Gate 2: Adapters                [###]      ✅ COMPLETE (2026-02-04)
Gate 3: Rewrite Seeds + Fuzzers [#####]    ✅ COMPLETE (2026-02-07)
Gate 4: Structural Execution    [####]     ← NEXT (prep started 2026-02-07)
Gate 5: Meta-Circular Parity    [###]      ← Hemisphere unblocked after this

L4 GATES (Parked - per advisor recommendation):
Gate 6: Boot0 Encoding          [----]     SINK
Gate 7: Boot1 Evaluator         [----]     SINK
Gate 8: Full Boot Chain         [----]     SINK
```

**Risk assessment (9-agent consensus):**
- Gates 3-4: HIGHEST RISK (seed rewrite + structural execution)
- Gates 1-2: LOW RISK (spec and adapters)
- Gates 6-8: PARKED (L4 research, revisit when third substrate needed)
