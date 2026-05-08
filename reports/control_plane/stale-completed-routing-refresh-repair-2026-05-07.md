# Stale Completed Routing Refresh Repair 2026-05-07

Date: 2026-05-07
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stale-completed-routing-refresh-repair-2026-05-07
Class: L4_ENABLER
Category: dispatcher/control-plane repair
Source authorization: FOUNDER_OVERRIDE:stale-completed-routing-refresh-repair-2026-05-07

## Root Cause Evidence

- After PR #904 merged, `.agent_bus/meta/post_merge_package.json` pointed at
  `deferred-non-mu-tooling-control-plane-remediation-2026-05-07`, but
  `.agent_bus/meta/post_merge_routing.json` still pointed at completed packet
  `reports/control_plane/deferred-non-mu-docs-control-plane-remediation-2026-05-07_2026-05-07.md`.
- Running `python3 mu/tools/executors/executor_dispatch.py --json -v --loop --max-waves 1`
  returned `status: stopped` and
  `Refusing to dispatch an already-complete bounded candidate`.
- Code readback showed `_completed_candidate_stop_result(...)` ran before
  `validate_routing_record_freshness(...)` in
  `mu/tools/executors/executor_dispatch.py`, so stale canonical routing could
  stop on a completed packet before post-merge auto-refresh had a chance to
  select the next open packet.

## Fix

- Move the completed-candidate stop until after freshness validation and
  canonical auto-refresh.
- Preserve the completed-packet safety for fresh records, refreshed records, and
  `skip_freshness=True` callers.
- Add regression coverage proving a stale canonical completed candidate refreshes
  to the current open packet before dispatching Phase A.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_refreshes_stale_canonical_completed_candidate_before_stop mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_bounded_candidate_before_phase_executor mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_bounded_candidate_before_tracker_update mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_inline_stale_record_matching_canonical_allows_refresh`
  - Result: exit `0`; `4 passed in 0.94s`.
- `python3 -m py_compile mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py`
  - Result: exit `0`.
- `git diff --check`
  - Result: exit `0`.

## Closeout

This is a bounded pipeline-control repair. It does not implement `/mu`
structural runtime work and does not edit Claude-related files.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stale-completed-routing-refresh-repair-2026-05-07`
- Active packet: `reports/control_plane/stale-completed-routing-refresh-repair-2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a0e44b7d888ec8ba15440f8baa18ea24f870157500d312b848a1333c8e7a2235`
- Indicator artifact: `reports/l4_wave_indicators/stale-completed-routing-refresh-repair-2026-05-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/stale-completed-routing-refresh-repair-2026-05-07.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stale-completed-routing-refresh-repair-2026-05-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/stale-completed-routing-refresh-repair-2026-05-07.md`
  - `reports/l4_wave_indicators/stale-completed-routing-refresh-repair-2026-05-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
