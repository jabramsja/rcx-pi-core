# Autoping Owner Health Self-Heal - 2026-05-03

Wave ID: autoping-owner-health-selfheal-2026-05-03
Task: [PIPELINE-AUTOPING]
Task ID: [PIPELINE-AUTOPING]
Phase-A-Lock: ROUTING_RECORD_AUTHORITY
Class: MAINTENANCE
Target gate: G8
Lane: control-surface
Authorization: standing pipeline-bug-fix authorization for bounded pipeline/autoping hardening.

## Problem

Live autoping state could become stale after the interactive session was already
running. The reproduced state for thread `019dc06c-8639-7150-8121-efc11a7aa5df`
showed `watcher_pid: 90160`, but `ps -p 90160` returned no process. The state
file still showed `updated_at: 2026-05-03T04:49:51.863041+00:00`, while the
current session had already moved past PR #858 merge closeout.

## Root Evidence

- `ps -p 90160 -o pid,ppid,stat,etime,command` returned only the header, proving
  the recorded watcher PID was dead.
- `python3 tools/session/check_codex_startup_state.py` repaired the live symptom
  and reported `codex_autoping: OK started Codex autoping pid=74868`.
- `mu/tools/observability/pipeline_monitor.sh` previously reseeded autoping only
  in `cmd_start`; `cmd_owner_tick` only called `ensure_tmux_session_under_owner_lock`.
- `mu/tools/session/ensure_codex_autoping.sh` previously accepted a live
  `watcher_pid` without checking whether the tmux-managed `AUTO-PING` window was
  actually present.

## Scope

1. Make `ensure_codex_autoping.sh` treat an active tmux session with no
   `AUTO-PING` window as unhealthy even when the watcher PID is live, then
   restart the tmux-managed autoping window.
2. Make the pipeline monitor owner tick run a non-force autoping health ensure
   after tmux health, so a dead or missing autoping lane is repaired during the
   normal monitor heartbeat.
3. Preserve startup `--force-restart` behavior for explicit monitor starts.
4. Add regression coverage for owner tick reseeding and the missing-window
   launcher case.
5. Mechanize the commit-package repair surfaced by the supervisor: Phase B must
   collect same-wave indicators and derive the authorized override for
   control-surface `MAINTENANCE` packets before supervisor review.

## Bridge Round 2 Remediation

The pre-commit supervisor rejected the first converged package because the
Phase B tracker note referenced the same-wave L4 indicator artifact while the
artifact was absent, and the tracker note did not carry the wave-bound founder
override required by the current non-structural adjacency gate. Phase B now
collects same-wave indicators for `MAINTENANCE` tracker notes as well as L4
waves, and authorized control-surface maintenance packets derive the same
wave-bound `FOUNDER_OVERRIDE:<wave_id>` token that L4 enabler packets already
derive.

## CI Repair Follow-Up

PR #859 CI failed after commit on the `python-only` green gate. The failed
GitHub Actions log showed
`tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_ensure_codex_autoping_restarts_live_watcher_when_tmux_window_missing`
failing at `tests/tools/test_recovery_gate.py:6768` because the launcher printed
`recorded pid=... is live but not this autoping watcher` instead of the expected
`AUTO-PING window missing` recovery path.

This follow-up keeps the same wave authority and stages only the CI-repair
scope:

- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/session/ensure_codex_autoping.sh`
- `reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md`
- `reports/l4_wave_indicators/autoping-owner-health-selfheal-2026-05-03.json`

The repair is mechanical, not just manual: the autoping PID identity check now
uses Linux `/proc/<pid>/cmdline` before falling back to wide `ps`, commit
executor `wait_ci` failures now carry failed required-check/log excerpts, and
recovery classification honors explicit `test_failure` payloads so future
required-CI failures can route to test recovery with diagnostic evidence.

## Codex Review Follow-Up

PR #859 remained blocked after CI passed because GraphQL review-thread evidence
showed one unresolved non-outdated Codex P1 on
`mu/tools/observability/pipeline_monitor.sh:400`: starting the pipeline monitor
without `CODEX_THREAD_ID` returned before clearing
`codex_autoping.thread`, allowing later owner ticks to continue using a stale
saved thread. The same GraphQL query showed the earlier
`mu/tools/session/ensure_codex_autoping.sh` P1 as outdated after the CI repair.

This follow-up makes the monitor clear `codex_autoping.thread` whenever
`CODEX_THREAD_ID` is absent, launches detached monitor owners with
`CODEX_THREAD_ID` stripped so owner ticks rely on the saved thread file rather
than a stale launch environment, and adds regression coverage that starts with
a stale saved thread, restarts without `CODEX_THREAD_ID`, and proves no stale
autoping launch remains. That makes the review fix structural in the monitor
path instead of a one-off state cleanup.

## Validation

- `bash -n mu/tools/session/ensure_codex_autoping.sh`
- `bash -n mu/tools/observability/pipeline_monitor.sh`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_start_clears_saved_autoping_thread_when_thread_id_is_absent mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_start_reseeds_autoping_when_thread_id_is_present mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_owner_tick_keeps_autoping_seeded_after_start -p no:cacheprovider`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_pipeline_monitor_owner_tick_keeps_autoping_seeded_after_start mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution::test_ensure_codex_autoping_restarts_live_watcher_when_tmux_window_missing -p no:cacheprovider`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestObservabilityWorktreeResolution -p no:cacheprovider`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_startup_state.py::test_codex_autoping_accepts_live_state mu/tests/tools/test_codex_startup_state.py::test_codex_autoping_restarts_named_lane_when_live_state_lacks_identity mu/tests/tools/test_codex_startup_state.py::test_codex_autoping_context_exhausted_restarts_recovery mu/tests/tools/test_codex_startup_state.py::test_codex_autoping_recovers_missing_state mu/tests/tools/test_codex_startup_state.py::test_tmux_pane_4_rejects_autoping_without_detail mu/tests/tools/test_codex_startup_state.py::test_tmux_pane_4_accepts_observability_detail -p no:cacheprovider`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_codex_autoping_watch.py::test_autoping_window_restarts_dead_watcher_without_manual_preflight -p no:cacheprovider`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'authorized_control_surface_maintenance_override or l4_indicator_collection_includes_maintenance_tracker_notes' -p no:cacheprovider`
- `git diff --check`

## Stop Conditions

- Do not change runtime, substrate, seed, or Mu semantic behavior.
- Do not widen into pager transport, app-server provisioning, or dashboard UI
  work beyond the autoping health surface.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `autoping-owner-health-selfheal-2026-05-03`
- Active packet: `reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md`
- Indicator artifact: `reports/l4_wave_indicators/autoping-owner-health-selfheal-2026-05-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Original Phase B staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `mu/tools/session/ensure_codex_autoping.sh`
  - `reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md`
  - `reports/deferred/non_blocking/autoping-owner-health-selfheal-2026-05-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/autoping-owner-health-selfheal-2026-05-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
