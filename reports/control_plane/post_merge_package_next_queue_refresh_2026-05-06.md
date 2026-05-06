# Post-Merge Package Next-Queue Refresh

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-package-next-queue-refresh-2026-05-06
Class: L4_ENABLER
Target Gate: G8
Tracked packet: reports/control_plane/post_merge_package_next_queue_refresh_2026-05-06.md

## Problem

After PR #886 merged, `.agent_bus/meta/post_merge_package.json` still carried
`merge_sha=38f8747f...` and still selected the already-completed docs
non-blocking packet. The dispatcher correctly refused to auto-refresh that
stale package because `executor_dispatch.py` requires the package merge SHA to
match current `HEAD` before invoking the post-merge supervisor.

## Mechanical Fix

- `commit_executor.py` now refreshes `.agent_bus/meta/post_merge_package.json`
  after successful merge verification.
- The refresh scans the founder-ordered remediation queue in `TASKS.md`, skips
  completed packets using the shared packet-status predicate, and writes the
  next open non-completed packet as the post-merge supervisor candidate.
- If the next open packet is marked `HARD STOP`, the package is written with no
  `next_candidates`, preserving the stop-before-/mu-structural boundary instead
  of auto-routing implementation.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short`
  exited `0` with `10 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_auto_refresh_rejects_stale_post_merge_package_before_supervisor --tb=short`
  exited `0` with `1 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short`
  exited `0` with `98 passed`.
- `python3 -m py_compile mu/tools/executors/commit_executor.py` exited `0`.

## Files

- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
- `reports/control_plane/post_merge_package_next_queue_refresh_2026-05-06.md`
- `reports/l4_wave_indicators/post-merge-package-next-queue-refresh-2026-05-06.json`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-package-next-queue-refresh-2026-05-06`
- Active packet: `reports/control_plane/post_merge_package_next_queue_refresh_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `93519c35f5cfa57881c1dd35ea7169b32a73a935477e25623d4969c263121743`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-package-next-queue-refresh-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_auto_refresh_rejects_stale_post_merge_package_before_supervisor --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short && python3 -m py_compile mu/tools/executors/commit_executor.py`.
- Evidence delta: (1) commit_executor writes a fresh post_merge_package.json after successful merge verification. (2) The package selector scans the founder-ordered remediation queue in TASKS.md and skips packets whose tracked packet Status is complete. (3) The selector writes the next open tests/tooling packet as the bounded candidate and writes an empty-candidate hard-stop package when the next open queue packet is /mu structural.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-package-next-queue-refresh-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/post_merge_package_next_queue_refresh_2026-05-06.md`
  - `reports/l4_wave_indicators/post-merge-package-next-queue-refresh-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
