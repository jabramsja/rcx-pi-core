# Deferred: Boot1 Observer Timestamp Regression on Re-Entry

**Source:** Bridge R2 review of W5A implementation (2026-03-19)
**Classification:** NON-BLOCKING (pre-existing, outside W5A scope)

## Issue

Both Python and JS Boot1 runtimes reset the observer timestamp counter (`_obs_ts[0]`
/ `obsTs`) to 0 on each re-entry pass. This produces non-monotonic timestamps across
re-entry boundaries, violating ObserverEventContract.v0.md's per-run monotonic
timestamp requirement.

- Python: `engine_pipeline.py:1077` — `_obs_ts[0] = 0`
- JS: `engine/pipeline.js:1051` — `obsTs = 0`

## Pre-Existing Evidence

This behavior existed before W5A. The timestamp reset was introduced with the original
Boot1 recursive engine implementation and is unrelated to the step index normalization
that W5A addresses.

## Why Non-Blocking

1. W5A scope explicitly excludes "Boot1 timestamp/depth semantics" (promotion packet constraints)
2. The timestamp regression is separate from step value monotonicity — W5A fixes step values only
3. No existing test asserts timestamp monotonicity across re-entry boundaries
4. The fix pattern is straightforward: remove the `_obs_ts[0] = 0` / `obsTs = 0` reset,
   or preserve the counter across re-entry like `_total_iterations[0]` / `totalIterations`

## Recommended Fix

Remove the timestamp reset on re-entry in both substrates. The total counter pattern
(already used for `_total_iterations[0]` / `totalIterations`) works identically:
preserve the counter across re-entry passes instead of resetting it.

## Behavioral Reproduction (Phase 1 Audit, 2026-03-19)

Cross-substrate reproduction confirmed identical behavior:

```
=== Python Real Re-Entry ===
depth | timestamp | step
    0 |         4 |    4   <- BEFORE re-entry
    1 |         0 |    5   <- AFTER (timestamp RESET, step MONOTONIC)

=== JS Real Re-Entry ===
depth | timestamp | step
    0 |         4 |    4   <- BEFORE re-entry
    1 |         0 |    5   <- AFTER (timestamp RESET, step MONOTONIC)
```

**Verifier finding:** Step values remain monotonic (primary sort key per
ObserverEventContract.v0.md lines 64-67). Timestamp is only a tie-breaker for
same-step events, which never span re-entry depths. No actual ordering violation.

**Repro test:** `.scratch/boot1_timestamp_repro.py` (3 tests, all pass)

## Discovered By

Bridge R2 review (2026-03-19, W5A implementation review via Codex).
Phase 1 red-team audit (2026-03-19) - behavioral reproduction on both substrates.
