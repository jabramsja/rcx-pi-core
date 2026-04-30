# Pipeline Dashboard Recovery Agent Label - 2026-04-30

Wave ID: pipeline-dashboard-recovery-agent-label-2026-04-30
Task: [PIPELINE-RECOVERY]
Class: L4_ENABLER
Lane: control-surface
target_gate_id: G8

## Authorization

Standing pipeline-bug-fix authorization applies to control-surface hardening.
This packet is bounded to recovery-agent subprocess labeling in the terminal
and web pipeline dashboards, plus closure of the matching deferred finding.

FOUNDER_OVERRIDE:pipeline-dashboard-recovery-agent-label-2026-04-30

## Root Cause Evidence

- The governing `pipeline_control_surface_split_2026-04-14` packet requires
  recovery observability to describe the actor generically as the recovery
  agent so operator surfaces stop leaking Claude-only truth
  (`reports/control_plane/pipeline_control_surface_split_2026-04-14.md:122-125`).
- The active deferred packet recorded the remaining dashboard labeling gap at
  `reports/deferred/non_blocking/pipeline-control-surface-split-2026-04-14_bridge_nonblockers.md:9-14`.
- Pre-fix terminal dashboard evidence:
  `git show HEAD:mu/tools/observability/pipeline_dashboard.py | nl -ba | sed -n '176,183p;1235,1245p'`
  showed `bridge_role_for_pid()` returned only `review`, `implement`, or
  `unknown`, and the subprocess render path used
  `bridge_agent_display_name(...)` for all non-SDK subprocesses.
- Pre-fix web dashboard evidence:
  `git show HEAD:mu/tools/observability/pipeline_dashboard_web.py | nl -ba | sed -n '236,242p;288,298p;1452,1478p'`
  showed the same missing recovery role, backend display name emission in
  `detect_subs()`, and no recovery subprocess card in the sidebar.

## Fix

- Classify subprocesses with a `recovery_gate.py` ancestor as recovery-agent
  subprocesses before reviewer/implementer role detection.
- Render terminal recovery subprocesses as `Recovery agent diagnosing` instead
  of the underlying Claude or Codex backend display name.
- Emit web dashboard recovery subprocess state with `role: recovery` and
  `name: Recovery agent`, then render a dedicated `RECOVERING` card.
- Added regressions covering both `claude --print` and `codex exec` recovery
  command shapes.
- Archived the matching deferred non-blocking finding as closed by this wave.

## Validation

- `python3 -m py_compile mu/tools/observability/pipeline_dashboard.py mu/tools/observability/pipeline_dashboard_web.py`
  - Result: passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestObservabilityNoiseFilters::test_terminal_dashboard_labels_recovery_agent_subprocess_generically mu/tests/tools/test_recovery_gate.py::TestObservabilityNoiseFilters::test_web_dashboard_labels_recovery_agent_subprocess_generically`
  - Result: `2 passed in 0.77s`.
- `git diff --check`
  - Result: passed.

## Scope

- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tools/observability/pipeline_dashboard_web.py`
- `mu/tests/tools/test_recovery_gate.py`
- `reports/control_plane/pipeline_dashboard_recovery_agent_label_2026-04-30.md`
- `reports/deferred/archive/pipeline-control-surface-split-2026-04-14_bridge_nonblockers_CLOSED_by_pipeline-dashboard-recovery-agent-label-2026-04-30.md`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-dashboard-recovery-agent-label-2026-04-30`
- Active packet: `reports/control_plane/pipeline_dashboard_recovery_agent_label_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `82ab47e4cf941c0081aae6d7202754fdba3c2bd9cbe19905555faebb010b5ee1`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-dashboard-recovery-agent-label-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipt.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Routed commit handoff scopes 7 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/pipeline-dashboard-recovery-agent-label-2026-04-30.json..
- Evidence handles:
  - `diff_check`: `passed`
  - `docs_consistency`: `all checks passed; existing STATUS freshness warning only`
  - `indicator`: `reports/l4_wave_indicators/pipeline-dashboard-recovery-agent-label-2026-04-30.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipt.json`
  - `py_compile`: `passed`
  - `targeted_pytest`: `5 passed in TestObservabilityNoiseFilters; 2 new regressions passed in 0.77s`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/pipeline_dashboard.py`
  - `mu/tools/observability/pipeline_dashboard_web.py`
  - `reports/control_plane/pipeline_dashboard_recovery_agent_label_2026-04-30.md`
  - `reports/deferred/archive/pipeline-control-surface-split-2026-04-14_bridge_nonblockers_CLOSED_by_pipeline-dashboard-recovery-agent-label-2026-04-30.md`
  - `reports/l4_wave_indicators/pipeline-dashboard-recovery-agent-label-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
