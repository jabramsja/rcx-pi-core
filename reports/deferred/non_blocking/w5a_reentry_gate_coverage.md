# Deferred: W5A Gate Test Re-Entry Coverage Gap

**Source:** Adversary agent review of W5A implementation (2026-03-19)
**Classification:** NON-BLOCKING (test quality, not runtime defect)

## Issue

The W5A gate test (`mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`) verifies
multi-step monotonicity and exhaustion anchoring but does NOT exercise actual re-entry
(boot1_depth > 0). The pre-W5A bug (non-monotonic step values) only manifested when the
inner `for iteration in range(remaining_iterations)` loop reset to 0 on re-entry.

Without re-entry, `iteration` equals `_total_iterations[0]`, so both pre-fix and post-fix
produce identical monotonic sequences. The gate test would pass against the pre-fix code.

## Why Non-Blocking

1. The W5A runtime fix is structurally sound (verified by all 4 agents)
2. The exhaustion anchoring math is proven correct
3. The trampoline path (no re-entry) is correctly unchanged
4. Existing `test_boot1_structural_iteration_gate.py` tests mock-injected re-entry
   for depth monotonicity (but not step value monotonicity)
5. Cross-substrate parity is verified (302 JS parity tests pass)

## Recommended Fix

Add a mock-injected re-entry variant to the gate test that:
1. Patches `_classify_engine_step` to return "reentry" after N steps
2. Verifies step values remain monotonic across the re-entry boundary
3. Verifies step values do NOT reset to 0 after re-entry

Pattern exists in `mu/tests/l4_gates/test_boot1_structural_iteration_gate.py::test_mock_injected_reentry_increments_depth`.

## Phase 1 Verification (2026-03-19)

Behavioral reproduction confirmed W5A fix works correctly:

```
depth=0, step=4 -> depth=1, step=5  (step MONOTONIC across re-entry)
```

Both Python and JS show identical behavior. The runtime fix is verified working.
The gap remains: gate test doesn't exercise this path, so it lacks regression coverage.

**Repro test:** `.scratch/boot1_timestamp_repro.py::test_boot1_timestamp_reset_on_real_reentry_python`
