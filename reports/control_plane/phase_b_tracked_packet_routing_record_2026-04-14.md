# Phase B Tracked-Packet Routing-Record Handoff

Date: 2026-04-14
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-RECOVERY/phase-b-tracked-packet-routing-record-2026-04-14]
Phase-A-Lock: LOCKED
Phase: B
Wave class: MAINTENANCE
Target gate: G8
Governing packet: This file
Wave ID: phase-b-tracked-packet-routing-record-2026-04-14

## Scope

Keep this wave tightly bounded to the Phase B dispatcher authority-chain defect
that blocks tracked-packet waves from progressing truthfully through the
pipeline:

1. `mu/tools/executors/executor_dispatch.py`
2. `mu/tests/tools/test_executor_dispatch.py`
3. `TASKS.md`
4. `reports/control_plane/phase_b_tracked_packet_routing_record_2026-04-14.md`
5. `reports/l4_wave_indicators/phase-b-tracked-packet-routing-record-2026-04-14.json`

## Trigger

While rerunning `[CODEX-STARTUP-HARDENING]` through the dispatcher, the live
Phase B command was:

`phase_b_executor.py --plan reports/control_plane/codex_startup_hardening_2026-04-14.md --json`

That command omitted `--routing-record`, even though the tracked packet came
from the routing record. The missing flag reopens the same broken handoff that
previously produced a supervisor package with the wrong `task_id`,
`wave_name`, and evidence handles.

Direct code-path evidence:

- `mu/tools/executors/phase_b_executor.py:1975-1983` requires tracked-packet
  callers to use `--plan` instead of planless mode.
- `mu/tools/executors/phase_b_executor.py:3605-3640` only injects routing
  authority when `--routing-record` or `--task-id` is provided on the CLI.

The dispatcher therefore has to preserve the routing record on tracked-packet
Phase B launches; otherwise downstream supervisor packaging falls back to
ambient repo state instead of the authoritative route.

## Constraints

1. Do not widen into startup-hardening docs, startup audit tooling, or other
   unrelated wave content.
2. Do not change `phase_b_executor.py`, `commit_executor.py`, or bridge
   supervisor behavior in this slice.
3. Preserve the existing tracked-packet path-traversal fail-closed checks.
4. Keep the fix to dispatcher argument propagation plus the narrow regression
   that proves `task_id` and `wave_name` remain attached on the tracked-packet
   path.
5. If the Phase B package claims an indicator evidence handle, materialize the
   referenced artifact in-repo so the bridge/convergence claim is repo-backed.

## Acceptance Criteria

1. `executor_dispatch.py` always passes `--routing-record` for
   `ROUTE_PHASE_B`, whether or not a tracked packet is present.
2. The tracked-packet regression asserts both `--plan` and `--routing-record`
   are forwarded together and that the routed payload preserves
   `task_id` / `wave_name`.
3. The planless and path-traversal tests remain green.
4. The packet scope stays limited to dispatcher routing propagation, the
   targeted regression, and the authorization docs above.
5. `reports/l4_wave_indicators/phase-b-tracked-packet-routing-record-2026-04-14.json`
   exists and matches the evidence handle emitted by the Phase B supervisor
   package for this wave.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q -k 'phase_b_planless_passes_routing_record or phase_b_with_tracked_packet_passes_plan or tracked_packet_with_dotdot_blocked or tracked_packet_escaping_repo_root_blocked or tracked_packet_valid_path_passes'`
- `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-tracked-packet-routing-record-2026-04-14 --output reports/l4_wave_indicators/phase-b-tracked-packet-routing-record-2026-04-14.json`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged`