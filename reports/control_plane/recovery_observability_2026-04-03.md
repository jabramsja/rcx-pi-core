# Recovery Observability Hardening

Date: 2026-04-03
Status: Implementation ready for routed supervisor
Task: [PIPELINE-RECOVERY]
Wave ID: recovery-observability-2026-04-03

## Scope

Make recovery state readable in plain English and stop observability panes from
reporting stale log watchers as live executor work.

## Changed surfaces

- `mu/tools/executors/recovery_gate.py`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tools/observability/_pane_processes.sh`
- `mu/tools/observability/pipeline_dashboard_web.py`
- `mu/tools/observability/pipeline_status.sh`
- `mu/tests/tools/test_recovery_gate.py`

## Proof points

1. Recovery now writes `.agent_bus/recovery/recovery_status.json` with:
   - wave id
   - failure class and tier
   - retry target
   - wave invocation counter
   - tuple attempt index
   - owner PID and active child PID/role
   - current state, command, note, and terminal outcome
2. `pipeline_dashboard.py` renders that status into short human-facing lines
   for tmux and other text dashboards, and exposes a one-shot recovery-only
   mode used by `_pane_processes.sh`.
3. `_pane_processes.sh` now includes the recovery section directly.
4. The terminal pane, text dashboard, web dashboard, and one-shot status script
   all ignore `tail -f ...executor_live.log` and other observability helper
   processes when deciding whether a real executor is running.

## Validation

- `python3 -m py_compile mu/tools/executors/recovery_gate.py mu/tools/observability/pipeline_dashboard.py mu/tools/observability/pipeline_dashboard_web.py mu/tests/tools/test_recovery_gate.py`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`
- `python3 mu/tools/observability/pipeline_dashboard.py --render-recovery --repo-root .`
- live pane smoke: `_pane_processes.sh` shows `Pipeline is idle` while the stale
  `tail -f ...phase_a_executor_live.log` watcher still exists, proving watcher
  noise no longer fakes an active Phase A
