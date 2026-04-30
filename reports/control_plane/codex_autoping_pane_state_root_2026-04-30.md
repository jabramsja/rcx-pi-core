# Codex Autoping Pane State Root - 2026-04-30

Wave ID: codex-autoping-pane-state-root-2026-04-30
Task: [PIPELINE-RECOVERY]
Class: L4_ENABLER
Lane: control-surface
target_gate_id: G8

## Authorization

Standing pipeline-bug-fix authorization applies to Codex-local pager/autoping
control-surface hardening. This packet is bounded to the pane-4 timeline
renderer reading the same Codex state root as the autoping watcher, pager, and
startup-state checks.

FOUNDER_OVERRIDE:codex-autoping-pane-state-root-2026-04-30

## Root Cause Evidence

- Deferred finding
  `reports/deferred/non_blocking/post-reentry-reroute-and-notification-truth-2026-04-23_bridge_nonblockers.md`
  recorded: "Timeline pane ignores RCX_CODEX_HOME for autoping state".
- Pre-fix diff evidence for this wave shows
  `mu/tools/observability/_pane_timeline.sh` used
  `Path.home() / ".codex" / "state"` inside `render_autoping_status()`, while
  the other autoping/pager state readers already use `RCX_CODEX_HOME` or
  `CODEX_HOME`.
- When Codex runs with an overridden state root, pane 4 could render pager
  state while omitting current autoping state because it was reading the wrong
  state directory.

## Fix

- Changed the timeline pane autoping renderer to resolve the Codex home from
  `RCX_CODEX_HOME`, then `CODEX_HOME`, then `~/.codex`.
- Added a regression test that sets `HOME` to an empty directory, writes the
  autoping state under `RCX_CODEX_HOME/state`, and verifies pane 4 still prints
  the last ping, detail, and summary lines.
- Archived the matching deferred non-blocking finding as closed by this wave.

## Validation

- `bash -n tools/observability/_pane_timeline.sh`
- `bash -n mu/tools/observability/_pane_timeline.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q -k 'pane_timeline_honors_rcx_codex_home_for_autoping_state or pane_timeline_shows_last_pager_wake_summary'`
  - Result: `2 passed, 959 deselected in 1.96s`
- `./tools/checks/check_docs_consistency.sh`
  - Result: all checks passed; existing STATUS freshness warning remained.

## Scope

- `mu/tools/observability/_pane_timeline.sh`
- `mu/tests/tools/test_recovery_gate.py`
- `reports/deferred/archive/post-reentry-reroute-and-notification-truth-2026-04-23_bridge_nonblockers_CLOSED_by_codex-autoping-pane-state-root-2026-04-30.md`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-autoping-pane-state-root-2026-04-30`
- Active packet: `reports/control_plane/codex_autoping_pane_state_root_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c9eade20e1817a6ea1577552e8d6de5eacfab361c7ef44d792f9bbf0e93e1554`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-pane-state-root-2026-04-30.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipt.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Routed commit handoff scopes 6 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/codex-autoping-pane-state-root-2026-04-30.json..
- Evidence handles:
  - `docs_consistency`: `all checks passed; existing STATUS freshness warning only`
  - `indicator`: `reports/l4_wave_indicators/codex-autoping-pane-state-root-2026-04-30.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipt.json`
  - `targeted_pytest`: `2 passed, 959 deselected`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_timeline.sh`
  - `reports/control_plane/codex_autoping_pane_state_root_2026-04-30.md`
  - `reports/deferred/archive/post-reentry-reroute-and-notification-truth-2026-04-23_bridge_nonblockers_CLOSED_by_codex-autoping-pane-state-root-2026-04-30.md`
  - `reports/l4_wave_indicators/codex-autoping-pane-state-root-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
