# Deferred Non-Mu Post-Merge Routed Queue Selection Repair 2026-05-07

Date: 2026-05-07
Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07
Class: L4_ENABLER
Category: tooling/control-plane pipeline repair
Phase-A-Lock: LOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07

## Scope

Repair the post-merge queue selector so routed non-`/mu` tracker-note packets
remain visible after the deferred lane truth sweep, and so open non-hard-stop
packets are selected before `/mu` structural hard stops.

This packet is a bounded pipeline repair. It does not authorize `/mu`
structural runtime, Stage0, seed, parity, scheduler, or production
implementation. It does not authorize Claude-related edits.

## Root-Cause Evidence

After PR #900 merged, commit executor Step 15b refreshed
`.agent_bus/meta/post_merge_package.json` to
`founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06` with
`post_merge_next_hard_stop: true`.

Direct code inspection showed why: `mu/tools/executors/commit_executor.py`
parsed only numbered `FOUNDER-ORDERED-REDTEAM-...` TASKS lines when building
post-merge queue entries, so the three routed non-`/mu` tracker-note packets
created by `deferred-non-mu-deferred-lane-truth-sweep-2026-05-07` were
invisible to the queue selector.

## Implemented Fix

- Added routed tracker-note queue extraction for control-plane packets whose
  live packet status starts with `Routed - Phase A`.
- Preserved the existing completed-packet skip behavior.
- Changed next-open selection to prefer any open non-hard-stop queue entry
  before returning an open hard-stop entry.
- Added a regression proving an open routed non-`/mu` tracker packet after a
  `/mu` hard-stop line is selected before the hard stop.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_routes_open_tracker_packet_before_hard_stop mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_stops_before_mu_structural_queue mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_selects_next_open_queue_packet`
  exited 0 with `3 passed in 0.56s`.
- `python3 -m py_compile mu/tools/executors/commit_executor.py` exited 0.
- `python3 mu/tools/checks/linters/check_private_attr_access.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  exited 0.

## Stop Boundary

After this pipeline repair lands, resume the non-`/mu` routed packet queue.
Hard stop before implementing either `/mu` structural packet.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07`
- Active packet: `reports/control_plane/deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `37cfc1d296def171b085042774f85bc31ca64a1eb4b3d96e60d576181da14016`
- Indicator artifact: `reports/l4_wave_indicators/deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_routes_open_tracker_packet_before_hard_stop mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_stops_before_mu_structural_queue mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_selects_next_open_queue_packet && python3 -m py_compile mu/tools/executors/commit_executor.py && python3 mu/tools/checks/linters/check_private_attr_access.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) PR #900 Step 15b selected the `/mu` structural hard-stop package while three routed non-`/mu` packets still had `Status: Routed - Phase A required before implementation`. (2) `mu/tools/executors/commit_executor.py` now extracts open routed tracker-note queue entries and selects open non-hard-stop entries before hard-stop entries. (3) The repair is bounded to post-merge queue selection and does not authorize `/mu` structural implementation or Claude-related edits.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07.md`
  - `reports/l4_wave_indicators/deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
