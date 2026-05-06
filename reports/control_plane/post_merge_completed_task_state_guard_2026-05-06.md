# Post-Merge Completed Task State Guard

Date: 2026-05-06
Status: IMPLEMENTED / LOCAL EVIDENCE (2026-05-06)
Wave ID: post-merge-completed-task-state-guard-2026-05-06
Task: [NEXT-CODEX-POST-REDTEAM]
Class: L4_ENABLER
Target Gate: G8

## Purpose

Close the remaining completed-task routing gap in the founder-ordered
post-merge queue. The previous completed-packet guard prevented rerouting a
bounded candidate whose control-plane packet `Status:` was complete, but the
queue selector still trusted the packet header more than the `TASKS.md` queue
state. A completed task with a stale or missing packet status could still be
chosen as the next open post-merge packet.

## Mechanical Fix

- `mu/tools/executors/commit_executor.py` now skips founder-ordered queue
  entries when either the packet `Status:` or the parsed `TASKS.md` entry state
  is complete.
- `mu/tools/executors/executor_common.py` exposes
  `read_founder_ordered_task_state(...)` so dispatcher-side guards can consult
  the same repo-visible task state by wave id or tracked packet.
- `mu/tools/executors/executor_dispatch.py` now treats a selected bounded
  candidate as already complete when the matching founder-ordered `TASKS.md`
  entry is complete, even if the packet header is stale.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py::test_post_merge_package_refresh_skips_completed_tasks_state_even_if_packet_stale mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_tasks_state_before_phase_executor --tb=short`
  exits `0` with `2 passed in 0.36s`.

## Boundary

- No Claude-related files were edited.
- No runtime, substrate, seed, scheduler, parity, Stage0, or `/mu` structural
  implementation behavior was changed.
- This is a control-plane safety fix for post-merge queue selection and
  dispatcher fail-closed behavior only.

## Authorization

FOUNDER_OVERRIDE:post-merge-completed-task-state-guard-2026-05-06

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-completed-task-state-guard-2026-05-06`
- Active packet: `reports/control_plane/post_merge_completed_task_state_guard_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a404cfa9687268d6d9fd5d1664bf6fc4ece8574c6bd635f1460351a014704a7f`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-completed-task-state-guard-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 8 wave-owned file(s). (2) Evidence gate exercises 2 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/post-merge-completed-task-state-guard-2026-05-06.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-completed-task-state-guard-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/post_merge_completed_task_state_guard_2026-05-06.md`
  - `reports/l4_wave_indicators/post-merge-completed-task-state-guard-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
