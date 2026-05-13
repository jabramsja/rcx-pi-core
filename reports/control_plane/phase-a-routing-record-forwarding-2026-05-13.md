# Phase A Routing Record Forwarding 2026-05-13

Date: 2026-05-13
Status: READY FOR COMMIT / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-a-routing-record-forwarding-2026-05-13
Class: L4_ENABLER
Category: dispatcher/control-plane repair
Source authorization: FOUNDER_OVERRIDE:phase-a-routing-record-forwarding-2026-05-13

## Root Cause Evidence

- The transparent JS Proxy successor route was launched with an explicit routing
  record at `.scratch/transparent_proxy_route.XXXXXX.json`.
- Live process evidence showed the dispatcher parent was invoked with that
  routing record, but the child Phase A command was only
  `phase_a_executor.py --plan-name transparent_js_proxy_provenance_implementation_202 --json`.
- The generated Phase A packet was named for transparent JS Proxy provenance,
  but its content still carried `Wave ID:
  deferred-active-inventory-n1-closure-cleanup-2026-05-13` and described the
  completed N1 cleanup wave.
- Code readback showed `executor_dispatch.py` built the Phase A command with
  `--plan-name` only, while `phase_a_executor.py` falls back to the canonical
  `.agent_bus/meta/post_merge_routing.json` when no `--routing-record` override
  is present.
- The canonical routing file still described the completed N1 cleanup route, so
  Phase A planned from stale canonical state instead of the dispatcher-selected
  transparent Proxy route.

## Fix

- Pass the dispatcher-selected routing record to `phase_a_executor.py` for every
  `ROUTE_PHASE_A` dispatch.
- Preserve existing plan-name selection from `tracked_packet`, candidate slug,
  or wave fallback.
- Add a regression proving Phase A dispatch includes `--routing-record` with the
  selected wave name, summary, and candidate payload.
- Add a commit-step retry for the already-supported self-cleared `index.lock`
  case. The retry remains fail-closed when the lock file persists or a live git
  owner remains.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherPhaseARecordForwarding::test_phase_a_passes_selected_routing_record_to_executor --tb=short`
  - Result: exit `0`; `1 passed in 0.62s`.

Additional commit-path validation must include:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherPhaseARecordForwarding::test_phase_a_passes_selected_routing_record_to_executor mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_a_surface_forwards_explicit_routing_record_context mu/tests/tools/test_executor_dispatch.py::TestModularSurfaceEntrypoints::test_phase_a_surface_uses_explicit_request_not_stale_default_routing --tb=short`
  - Result: exit `0`; `3 passed in 0.10s`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_git_commit_retries_self_cleared_index_lock_once mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_git_commit_fails_closed_when_index_lock_persists --tb=short`
  - Result: exit `0`; `2 passed in 0.04s`.
- `python3 -m py_compile mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py`
  - Result: exit `0`.
- `python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py`
  - Result: exit `0`.
- `git diff --check`
  - Result: exit `0`.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-a-routing-record-forwarding-2026-05-13`

## Closeout

This is a bounded pipeline-control repair. It does not implement `/mu`
structural production runtime semantics and does not edit Claude-related files.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-a-routing-record-forwarding-2026-05-13`
- Active packet: `reports/control_plane/phase-a-routing-record-forwarding-2026-05-13.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `04df139f6e4a2b3093fd1af524d4c9c5b024109dd301bc467ddd873b4a63aab2`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-routing-record-forwarding-2026-05-13.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Routed commit handoff scopes 7 wave-owned file(s). (2) Evidence gate exercises 2 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/phase-a-routing-record-forwarding-2026-05-13.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-a-routing-record-forwarding-2026-05-13.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/phase-a-routing-record-forwarding-2026-05-13.md`
  - `reports/l4_wave_indicators/phase-a-routing-record-forwarding-2026-05-13.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
