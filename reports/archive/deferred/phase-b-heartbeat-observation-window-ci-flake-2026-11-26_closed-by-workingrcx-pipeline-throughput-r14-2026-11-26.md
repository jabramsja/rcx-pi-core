<!-- DOC_STATUS: REFERENCE -->
# Phase B native process-observation test races its own heartbeat writer — 2026-11-26

Class: DEFECT (test) · Severity: high · Disposition: **BLOCKING** (it fails a required CI check,
`green-gate`, on an unrelated PR) · Owner: 40 `[FLEET-NATIVE-LIFECYCLE-PREVENTION]` (runner
lifetime / process observation follow-ups).

## Observed

- PR #1346 (`workingrcx-tmux-pane-exec-identity-r3-2026-11-26`, head `ff12f654`) `green-gate`:
  `1 failed, 14968 passed, 22 skipped`.
- Failing test:
  `tests/tools/test_phase_b_executor.py::test_native_uncertain_process_observation_holds_every_consumer[failed-query]`
  - `AssertionError: assert '' != ''`, at the `heartbeat.read_text() != before_pulse` check that
    follows `time.sleep(0.1)`.
- The wave's diff (monitor pane commands, autofollow fixture, reports) does not touch this test
  or its code path.
- The same test passed in that head's local pre-push on macOS and in the earlier R3 full
  pre-push.

## Root cause

- **Writer:** the test's detached heartbeat child writes the observed file with
  `Path(...).write_text(...)`, which truncates before writing. A concurrent reader can observe an
  empty file.
- **Reader:** the assertion samples the file twice, 100 ms apart, and requires a change.
- **Interaction:** under CI load, both samples can land before the first write, or inside
  truncation windows. That yields `'' == ''`, a timing failure, not a product regression.

## Required fix

1. Make the heartbeat writer publish atomically: write a sibling temp file, then `replace()`.
   Readers then never see an empty pulse.
2. Replace the fixed `sleep(0.1)` single comparison with a bounded wait-until, polling for a
   changed non-empty pulse up to a few seconds, so slow runners still exercise the real liveness
   property.
3. Do not weaken the assertion that the escaped child is alive at the HOLD.

The tier-3 recovery delegate for PR #1346 independently proposed fix 1 inside that wave's lane.
The file is outside that wave's allowlist, so the fix belongs in its own owner-40 wave, which must
check hunk overlap first because this test file is also edited by the preserved throughput R7
candidate.

## Interim

An informed single re-run of the failed job is justified for PR #1346: the test is outside the
diff, it passed on the same head locally, and the failure is a 100 ms observation window. That
re-run is not a substitute for the fix above, which lands before the next wave whose CI runs
this test.
