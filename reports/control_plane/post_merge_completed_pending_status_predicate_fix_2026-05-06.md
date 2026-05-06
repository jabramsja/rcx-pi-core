# Post-Merge Completed Pending Status Predicate Fix

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-completed-pending-status-predicate-fix-2026-05-06
Class: L4_ENABLER
Target Gate: G8
Tracked packet: reports/control_plane/post_merge_completed_pending_status_predicate_fix_2026-05-06.md

## Problem

After PR #887 merged, Step 15b refreshed the post-merge package to
`founder-ordered-redteam-docs-audit-2026-05-05` even though the audit tracker
entry is completed and findings-routed. Direct cause: `packet_status_is_completed`
treated any `PENDING` token as open, so `Status: COMPLETED (commit-ready,
pre-commit supervisor pending)` did not count as complete.

## Mechanical Fix

- `packet_status_is_completed` now treats explicit `COMPLETED`, `LANDED`, and
  `CLOSED` statuses as terminal before evaluating pending-detail text.
- `IMPLEMENTED ... PENDING COMMIT` remains routable until the commit actually
  lands.
- Post-merge package refresh now has a regression for the exact completed audit
  status string that caused the wrong hard-stop package selection.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short`
  exited `0` with `12 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection --tb=short`
  exited `0` with `4 passed`.
- `python3 -m py_compile mu/tools/executors/executor_common.py` exited `0`.

## Files

- `mu/tools/executors/executor_common.py`
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `reports/control_plane/post_merge_completed_pending_status_predicate_fix_2026-05-06.md`
- `reports/l4_wave_indicators/post-merge-completed-pending-status-predicate-fix-2026-05-06.json`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-completed-pending-status-predicate-fix-2026-05-06`
- Active packet: `reports/control_plane/post_merge_completed_pending_status_predicate_fix_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `01bd94ae408cc9f345103bf7eeb47cae7c3c3a7c2665d5584cf308a712f5a742`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-completed-pending-status-predicate-fix-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection --tb=short && python3 -m py_compile mu/tools/executors/executor_common.py`.
- Evidence delta: (1) Shared packet-status classification now treats explicit `COMPLETED`, `LANDED`, and `CLOSED` statuses as terminal before evaluating pending-detail text. (2) `IMPLEMENTED ... PENDING COMMIT` remains routable until commit completion. (3) Post-merge package refresh has a regression for `COMPLETED (commit-ready, pre-commit supervisor pending)` audit packets so completed audit packets cannot be selected ahead of queued remediation packets.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-completed-pending-status-predicate-fix-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_common.py`
  - `reports/control_plane/post_merge_completed_pending_status_predicate_fix_2026-05-06.md`
  - `reports/l4_wave_indicators/post-merge-completed-pending-status-predicate-fix-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
