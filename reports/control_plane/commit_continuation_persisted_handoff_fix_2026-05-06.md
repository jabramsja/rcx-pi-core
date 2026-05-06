# Commit Continuation Persisted Handoff Fix

Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-continuation-persisted-handoff-fix-2026-05-06
Class: L4_ENABLER
Category: tooling
Founder override: FOUNDER_OVERRIDE:commit-continuation-persisted-handoff-fix-2026-05-06
Authorization: same-session pipeline repair required after dispatcher/commit continuation failed to resume an already-created local commit.

## Trigger

The docs non-blocking wave reached a local commit, then pre-push failed on a
transient observability timeout. A direct focused rerun of the failing test
passed, and the full `TestObservabilityWorktreeResolution` class also passed.

When the commit surface was rerun through the dispatcher, the executor did not
resume from the local commit. It fell back to Step 4 and failed with:

```text
Nothing staged after git add (nothing to commit)
```

## Root Cause Evidence

- `mu/tools/executors/commit_executor.py` computed `handoff_sha` before Step 5c
  refreshed and persisted `.agent_bus/executors/phase_b_handoff.json`.
- Step 5c persisted the refreshed handoff for retry/review surfaces, and Step 7
  persisted it again after adding supervisor receipt evidence.
- The continuation record kept the original pre-refresh hash, so the next CLI
  run loaded the durable refreshed handoff, failed the hash check, ignored the
  continuation record, and restarted staging against an already-committed diff.
- The existing regression encoded that stale behavior by asserting continuation
  remained bound to the original handoff instead of the durable handoff used by
  CLI reruns.

## Repair

- Rebind `result["handoff_sha"]` after Step 5c handoff refresh.
- Recompute `handoff_sha` again after supervisor receipt evidence is injected,
  immediately before the final durable handoff persist and continuation write.
- Preserve the original caller handoff hash for standalone runs, because
  standalone runs do not persist refreshed Phase B handoff files for reruns.
- Update the continuation regression to rerun with the persisted
  `.agent_bus/executors/phase_b_handoff.json`, matching the real dispatcher and
  CLI resume path.
- Extend the standalone receipt regression to prove standalone continuations
  remain bound to the original caller handoff hash even after Step 7 injects
  supervisor receipt evidence in memory.
- Extend the completed-packet routing guard to the recoverable dispatcher
  surface path, including Phase B and commit subcommands, so completed bounded
  packets stop before any executor process launches.
- Narrow the completed-packet status predicate so `IMPLEMENTED ... PENDING
  COMMIT` packets remain routable until the commit actually lands.

## Validation

```text
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_binds_continuation_to_persisted_handoff -vv --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestSupervisorReceiptIsAuthority::test_standalone_empty_handoff_receipt_skips_provenance_check -vv --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_bounded_candidate_before_tracker_update mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_b_surface_stops_completed_bounded_packet_before_executor mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_commit_surface_stops_completed_bounded_packet_before_executor mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection::test_status_predicate_keeps_pending_commit_routable mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection::test_accepts_implemented_pending_commit_control_plane_packet -vv --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py --tb=short
```

All passed locally before commit packaging or PR bot-review remediation.

## Stop Conditions

- Stop if the repair tries to alter docs-wave content.
- Stop if the continuation path cannot be proven by a regression that reruns
  from the persisted durable handoff.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-continuation-persisted-handoff-fix-2026-05-06`
- Active packet: `reports/control_plane/commit_continuation_persisted_handoff_fix_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6682d626d3dcba0923a0a766edf593c9dbdda8fac3c7152f6428c7438563a8ea`
- Indicator artifact: `reports/l4_wave_indicators/commit-continuation-persisted-handoff-fix-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestSupervisorReceiptIsAuthority::test_standalone_empty_handoff_receipt_skips_provenance_check mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_commit_packet_truth_refresh_binds_continuation_to_persisted_handoff -vv --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_bounded_candidate_before_tracker_update mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_b_surface_stops_completed_bounded_packet_before_executor mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_commit_surface_stops_completed_bounded_packet_before_executor mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection::test_status_predicate_keeps_pending_commit_routable mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection::test_accepts_implemented_pending_commit_control_plane_packet -vv --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py --tb=short`.
- Evidence delta: (1) commit_executor rekeys Phase B continuations after Step 5c persists the refreshed Phase B handoff. (2) commit_executor rekeys Phase B continuations again after Step 7 adds supervisor receipt evidence immediately before final durable handoff persist and continuation write. (3) Standalone continuations keep the original caller handoff hash because no refreshed Phase B handoff is persisted for standalone reruns. (4) Regressions now cover both the persisted .agent_bus/executors/phase_b_handoff.json rerun path and the standalone caller-handoff rerun path. (5) Dispatcher completed-packet stops now apply to UPDATE_TRACKER_ONLY and recoverable Phase B/commit surfaces before executor launch. (6) `IMPLEMENTED ... PENDING COMMIT` packet statuses remain routable until commit completion.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/commit-continuation-persisted-handoff-fix-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/commit_continuation_persisted_handoff_fix_2026-05-06.md`
  - `reports/l4_wave_indicators/commit-continuation-persisted-handoff-fix-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
