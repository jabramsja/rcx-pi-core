# Post-Merge Completed Packet Routing Guard

Date: 2026-05-06
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-merge-completed-packet-routing-guard-2026-05-06
Class: L4_ENABLER
Category: tooling/control-plane
Severity: BLOCKING pipeline repair
Founder override: FOUNDER_OVERRIDE:post-merge-completed-packet-routing-guard-2026-05-06
Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05

## Scope

This same-session pipeline repair prevents dispatcher from rerunning a bounded
control-plane packet whose packet `Status:` already marks it complete, even if
post-merge tracker closure or package refresh leaves a stale candidate selected.

## Reproduced Failure

After PR #883 merged the tooling blocking remediation, the canonical routing
record still selected
`reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`.
The selected packet at `HEAD` has:

- `Status: COMPLETED (commit-ready, supervisor COMMIT_GO)`
- `Wave ID: founder-ordered-redteam-tooling-blocking-remediation-2026-05-06`

Before this repair, rerunning dispatcher rebound the stale record and entered
Phase A/Phase B for that completed packet.

## Mechanical Fix

- `mu/tools/executors/executor_common.py` now reads the packet `Status:` field
  and rejects post-merge routing-record builds whose `tracked_packet` is already
  complete.
- `mu/tools/executors/executor_dispatch.py` now stops `ROUTE_PHASE_A` and
  `ROUTE_PHASE_B` before invoking phase executors when the selected packet is
  already complete.
- `mu/tools/executors/executor_dispatch.py` now resolves tracked packets from
  the selected bounded candidate set, with legacy fallback only when no bounded
  candidate exists.
- `mu/tools/agents/meta_bridge_supervisor.py` now removes completed bounded
  candidates from post-merge local routing decisions.
- Regression tests cover builder rejection, dispatcher stop behavior, and
  post-merge supervisor filtering, including a mixed-candidate case where an
  unbounded completed historical packet must not block or become the Phase A
  plan target when an open bounded packet is present.

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_bounded_candidate_before_phase_executor mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_ignores_completed_unbounded_candidate_when_bounded_open_exists mu/tests/tools/test_executor_dispatch.py::TestRoutingRecordBuilderCompletedPacketRejection::test_rejects_completed_control_plane_packet mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_canonical_explicit_stale_record_rebinds_with_builder mu/tests/tools/test_meta_bridge_supervisor.py::TestPostMergeIntegration::test_decide_post_merge_route_locally_skips_completed_packet mu/tests/tools/test_meta_bridge_supervisor.py::TestPostMergeIntegration::test_decide_post_merge_route_locally_routes_phase_b_when_packet_locked mu/tests/tools/test_meta_bridge_supervisor.py::TestPostMergeIntegration::test_decide_post_merge_route_locally_routes_phase_a_when_packet_unlocked`
  exited `0` with `7 passed`.
- `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json -v`
  exited `0` and returned `status: stopped` with the message:
  `Refusing to dispatch an already-complete bounded candidate`.

## Stop Boundary

This repair does not implement docs, tests, tooling non-blocking, or `/mu`
structural remediation. After this repair lands, the dispatcher routing record
must be refreshed to the next open non-`/mu` remediation packet. The hard stop
before `/mu` structural remediation remains in force.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-completed-packet-routing-guard-2026-05-06`
- Active packet: `reports/control_plane/post_merge_completed_packet_routing_guard_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f0dcb6cf29737bb7698c0a92f8680eac83e0b100a8a47b5b4f04ad9e67219afe`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-completed-packet-routing-guard-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/post-merge-completed-packet-routing-guard-2026-05-06.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-completed-packet-routing-guard-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/post_merge_completed_packet_routing_guard_2026-05-06.md`
  - `reports/l4_wave_indicators/post-merge-completed-packet-routing-guard-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
