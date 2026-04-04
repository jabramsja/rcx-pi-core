# Recovery Observability Hardening

Date: 2026-04-03
Status: Routed live proof complete; ready for routed supervisor
Task: [PIPELINE-RECOVERY]
Wave ID: recovery-observability-2026-04-03

## Scope

Make recovery state readable in plain English and stop observability panes from
reporting stale log watchers as live executor work. Also restore live Tier 3
dispatcher wiring on the current `dev` branch, which still had
`attempt_recovery()` returning `not_implemented` for Tier 3 despite earlier
reports claiming it was already live.

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
4. `pipeline_dashboard_web.py` now exposes the same recovery state in the web
   sidebar, including tier, target, loop counter, live PIDs, reason, note, and
   terminal outcome.
5. The terminal pane, text dashboard, web dashboard, and one-shot status script
   all ignore `tail -f ...executor_live.log` and other observability helper
   processes when deciding whether a real executor is running.
6. `attempt_recovery()` now actually calls `run_recovery_loop()` for Tier 3 on
   current `dev`, and the recovery reason extractor now pulls the real embedded
   executor error instead of useless trailing JSON punctuation.

## Validation

- `python3 -m py_compile mu/tools/executors/recovery_gate.py mu/tools/observability/pipeline_dashboard.py mu/tools/observability/pipeline_dashboard_web.py mu/tests/tools/test_recovery_gate.py`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short -k 'tier3_recovery_loop_grants_retry or tier3_unrecovered_fails_closed_under_retries or phase_b_surface_recovery_retries_after_tier3_success'`
- `python3 mu/tools/observability/pipeline_dashboard.py --render-recovery --repo-root .`
- live pane smoke: `_pane_processes.sh` shows `Pipeline is idle` while the stale
  `tail -f ...phase_a_executor_live.log` watcher still exists, proving watcher
  noise no longer fakes an active Phase A
- live routed dispatcher proof:
  `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR RCX_AGENT_PREFLIGHT_FORCE_FAIL=1 PYTHONHASHSEED=0 python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name recovery_live_probe_2026-04-03 --json -v`
  during the run `pipeline_status.sh` showed:
  `ACTIVE — Tier 3 agent_review_crash`,
  `Retry target: Phase A`,
  `State: tier3_waiting_on_claude · loop 1/3`,
  live owner/child PIDs,
  and the exact reason
  `bridge_supervisor.py: error: unrecognized arguments: --packet-review`
  instead of the previous useless `}` summary
- final routed outcome from the same probe:
  `class=agent_review_crash tier=3 recovered=False`, with
  `pipeline_status.sh` ending at
  `LAST RECOVERY — Tier 3 agent_review_crash` and
  `Outcome: exhausted via exhausted`
