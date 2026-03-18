# Boot1 Observer Step Monotonicity Gap

## Status: NON-BLOCKING (pre-existing, not introduced by W4A)

## Finding

Boot1 `_run_engine_recursive` resets the inner loop `iteration` counter on each re-entry pass. This produces observer `step_boundary` events with non-monotonic step values: `[0,1,2,3,4,0,1,2,3,4,5]`.

The trampoline path produces monotonic steps: `[0,1,2,3,4,5,6,7,8,9,10]`.

This violates `ObserverEventContract.v0.md`'s monotonic-step requirement and prevents true Boot1/trampoline observer stream parity.

## Pre-existing evidence

This behavior existed before Wave 4A. The Boot1 inner loop counter has always reset on re-entry (line 1084: `for iteration in range(remaining_iterations)`). The W4A extraction did not change this — it preserved the exact same iteration counting.

## Fix path

The fix is in `_run_engine_recursive`: use `_total_iterations[0]` for observer `step` instead of the inner `iteration` counter. This is a separate behavioral change and should be its own wave, not bundled into W4A (classifier extraction).

## Discovered by

Bridge R2 review (2026-03-18, W4A implementation review).
