<!-- DOC_STATUS: REFERENCE -->
# Pre-commit targeted pytest gate cannot run the Phase B executor test module in its budget — 2026-11-26

Class: DEFECT · Severity: high · Disposition: **BLOCKING**. Every wave that edits
`mu/tests/tools/test_phase_b_executor.py` fails to commit. That includes the heartbeat
observation fix and throughput R8, because R7 edits this file. Owner: 40
`[FLEET-NATIVE-LIFECYCLE-PREVENTION]`.

## Observed

Wave `workingrcx-phase-b-heartbeat-observation-fix-2026-11-26` passed Phase A and Phase B, with
bridge convergence in round 1. It then failed at commit Step 8b (`run_pre_commit_script`):

> `targeted pytest gate failed (exit=-1): pytest timed out after 600s`

Nothing was committed. Recovery then entered tier 3.

A measurement on dev `b6544dfc` ran the module's 1,466 tests in 129s with 8 xdist workers. Summed
per-test durations came to 656s, which is roughly what a serial run costs.

## Root cause

`commit_executor._run_pytest_on_files` backs both the Step 8b pre-commit gate and the Step 15
bot-remediation gate. It gives each exact full module a fixed serial budget:
- `test_phase_b_executor.py`: 600s, justified in the code comment by a 305s measurement from
  2026-10-09;
- `test_worktree_lifecycle.py`: 600s;
- `test_workingrcx_fleet_apply.py`: 900s.

Only the fleet module gets the bounded xdist policy (`-n 4 --dist worksteal`). The Phase B module
has since grown past its serial budget. Per-module serial budgets drift every time a heavy module
grows.

## Required fix (most structural first)

1. **Recommended.** Run the targeted gate under the same bounded xdist execution model as the local
   pre-push, whatever the selection, keeping every selector, the marker filter and the import mode.
   The pre-push already runs every test this way, so the suite is xdist-safe. This removes
   per-module budget drift.
2. **Minimal variant.** Apply the existing fleet policy (`-n 4 --dist worksteal`) to the exact full
   `test_phase_b_executor.py` and `test_worktree_lifecycle.py` modules.
3. Extend the existing targeted-gate regressions in
   `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`. The fix wave must not edit
   `test_phase_b_executor.py`, or it would hit this gate itself.

## Sequencing

1. This fix lands first.
2. The heartbeat observation fix relaunches under a fresh wave id.
3. Throughput R8 depends on this fix.

Check hunk overlap with the preserved R7 candidate in `commit_executor.py` before scoping.
