# Parallel Pipeline Lanes Config 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: parallel-pipeline-lanes-config-2026-05-31
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Add the `pipeline_monitor.lanes` config block (5 committed parallel lanes) to `mu/tools/executors/executor_config.json`. The lane MACHINERY already exists on dev (`pipeline_monitor_identity.py` `load_monitor_lanes`/`validate_*`, `executor_dispatch --bus-dir` threading, `mu/tests/tools/test_agent_bus_namespacing.py`). The ONLY gap is the committed lanes config. Each lane needs `{bus_dir, dashboard_port, tmux_session}` satisfying `load_monitor_lanes` constraints: `bus_dir` matches `^\.agent_bus-<id>$` and != `.agent_bus`; `dashboard_port` in 1-65535 and != 8099 (default) and unique; `tmux_session` matches `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$` and != `rcx-pipeline` (default) and unique; lane name matches `LANE_NAME_RE`. Proposed 5 lanes (lane1..lane5): `bus_dir` `.agent_bus-lane1..5`, `dashboard_port` 8101..8105, `tmux_session` `rcx-pipeline-lane1..5`.

## Scope

In scope (files/directories):
- `mu/tools/executors/executor_config.json` — add the `pipeline_monitor.lanes` block only (config edit; this is NOT a runtime directory).
- `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md` — this governing packet.
- `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json` — generated L4 wave-indicator evidence artifact.
- `TASKS.md` — same-wave tracker note already present (line ~561); kept/confirmed, not re-authored.

This is a config-only `L4_ENABLER` wave. The lane machinery already exists on dev (PRs from 2026-04-29/30); this wave only adds the committed lane definitions so each named lane resolves via `python3 mu/tools/observability/pipeline_monitor_identity.py --repo-root . --lane laneN --format json` and the existing `mu/tests/tools/test_agent_bus_namespacing.py` suite covers them. (The monitor CLI exposes only `--repo-root/--lane/--bus-dir/--port/--allow-unconfigured-named-bus/--format`; there is no `--list-lanes` mode, and adding one is out of scope per the constraints below.)

- `reports/deferred/non_blocking/parallel-pipeline-lanes-config-2026-05-31_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks from the TASKS.md current-phase tracker (`parallel-pipeline-lanes-config-2026-05-31`, TASKS.md ~line 561). Only the committed config is unlanded — the validators, `--bus-dir` dispatch threading, and the namespacing test suite already exist on dev and are NOT re-implemented here.

1. Add a `pipeline_monitor.lanes` block to `mu/tools/executors/executor_config.json` defining 5 lanes, each `{bus_dir, dashboard_port, tmux_session}`, all satisfying the `load_monitor_lanes` collision/format constraints:
   - `lane1`: `bus_dir` `.agent_bus-lane1`, `dashboard_port` 8101, `tmux_session` `rcx-pipeline-lane1`
   - `lane2`: `bus_dir` `.agent_bus-lane2`, `dashboard_port` 8102, `tmux_session` `rcx-pipeline-lane2`
   - `lane3`: `bus_dir` `.agent_bus-lane3`, `dashboard_port` 8103, `tmux_session` `rcx-pipeline-lane3`
   - `lane4`: `bus_dir` `.agent_bus-lane4`, `dashboard_port` 8104, `tmux_session` `rcx-pipeline-lane4`
   - `lane5`: `bus_dir` `.agent_bus-lane5`, `dashboard_port` 8105, `tmux_session` `rcx-pipeline-lane5`
   Each `bus_dir` matches `^\.agent_bus-<id>$` and != `.agent_bus`; each `dashboard_port` is in 1-65535, != 8099, and unique; each `tmux_session` matches `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`, != `rcx-pipeline`, and unique; each lane name matches `LANE_NAME_RE`.
2. Generate the L4 wave-indicator artifact: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id parallel-pipeline-lanes-config-2026-05-31 --output reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`.

## Constraints (NOT in scope)

- NO runtime-dir changes. This is a config-only `L4_ENABLER`; touching `rcx_pi/selfhost/` or any `mu/` runtime/projection/substrate/scheduler/seed/parity/VM-semantics path voids the class and is forbidden.
- NO modification or re-implementation of the lane machinery: `mu/tools/observability/pipeline_monitor_identity.py` (`load_monitor_lanes`/`validate_*`), `executor_dispatch.py` `--bus-dir` threading, and `mu/tests/tools/test_agent_bus_namespacing.py` already exist on dev. Do NOT re-list them as unresolved or edit them.
- NO change to the default lane (`bus_dir` `.agent_bus`, `dashboard_port` 8099, `tmux_session` `rcx-pipeline`).
- NO new files beyond the generated L4 indicator artifact; do not split the config into a separate file.
- NO more than 5 lanes and no deviation from the `lane1..lane5` naming scheme without founder re-authorization.
- NO L3 parity / JS substrate work — config-only, no projection semantics change, so `eval_step.js` is untouched.

## Stop conditions

- STOP and escalate (do NOT force-commit) if `load_monitor_lanes(repo_root)` raises any collision or format error on the 5 lanes (duplicate/forbidden `dashboard_port`, duplicate/forbidden `bus_dir`, duplicate/forbidden `tmux_session`, or a name/regex mismatch).
- STOP if the proposed ports (8101..8105) or sessions (`rcx-pipeline-lane1..5`) collide with the default (8099 / `rcx-pipeline`) or any pre-existing committed lane — re-scope and escalate rather than silently renumbering.
- STOP and re-scope if delivering the config appears to require editing lane machinery (`pipeline_monitor_identity.py` validators, `executor_dispatch` threading, or `test_agent_bus_namespacing.py`). That would mean the "machinery pre-exists" premise is false; do not widen scope to implement machinery in this wave.
- STOP before the commit boundary if `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bus_namespacing.py --tb=short` fails after adding the config.
- STOP and hard-fail before touching any runtime directory; any runtime-dir edit voids the `L4_ENABLER` class.
- STOP after Phase A: this packet is design-only. Do not implement until it is agent-reviewed and bridge-converged (Phase-A-Lock semantics).

## Acceptance criteria

- `load_monitor_lanes(repo_root)` returns 5 normalized lanes with no collision error. This is proven by the per-lane CLI resolve below: `resolve_monitor_identity` calls `load_monitor_lanes` first, so any clean `--lane` resolve (exit 0) implies the full lanes block validated — all names, formats, and the session/port/bus_dir collision checks passed.
- Each named lane resolves via the real CLI surface — `python3 mu/tools/observability/pipeline_monitor_identity.py --repo-root . --lane laneN --format json` for `laneN` in `lane1..lane5` — printing `"configured": true`, `"named": true`, and the configured `bus_dir`/`dashboard_port`/`tmux_session`. (There is no `--list-lanes` flag; the CLI accepts only `--repo-root/--lane/--bus-dir/--port/--allow-unconfigured-named-bus/--format`, so resolution is verified per lane rather than via a listing mode.)
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bus_namespacing.py --tb=short` passes.
- No runtime-dir file is modified (config-only); the `L4_ENABLER` class holds.
- L4 wave-indicator artifact exists at `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json` (via `indicator_collection_command`).

Evidence command (runnable; corrected from the stale TASKS.md tracker-note form):
`PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_bus_namespacing.py --tb=short && for L in lane1 lane2 lane3 lane4 lane5; do python3 mu/tools/observability/pipeline_monitor_identity.py --repo-root . --lane "$L" --format json; done`

NOTE — TASKS.md tracker-note staleness (not editable from this packet): the tracker sync note for `parallel-pipeline-lanes-config-2026-05-31` (TASKS.md ~line 561) records `evidence_command: ... && python3 ... --list-lanes`, but `--list-lanes` is not a real CLI flag — `argparse` exits 2 with `unrecognized arguments: --list-lanes`, and the tool exposes only `--repo-root/--lane/--bus-dir/--port/--allow-unconfigured-named-bus/--format`. Adding `--list-lanes` would require editing `pipeline_monitor_identity.py`, which the constraints above forbid for this config-only `L4_ENABLER`. The per-lane resolve above is therefore the canonical, runnable proof; the TASKS.md tracker-note `evidence_command` should be corrected to match via `tracker_sync_note` (tracker text is owned by that tool and is not hand-edited from this packet).

## Grounding / Authorization

Same-wave authorization is carried by the TASKS.md tracker note for `parallel-pipeline-lanes-config-2026-05-31` (TASKS.md ~line 561, under the NEXT ledger), which routes this wave under task `[NEXT-CODEX-POST-REDTEAM]` and names this packet (`reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md`) as its governing packet.

- Task: `[NEXT-CODEX-POST-REDTEAM]` (TASKS.md ~line 680; **UNPARKED** 2026-03-28, founder-authorized; queue remains OPEN for future bounded work).
- Governing packet: `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md` (this file).
- Class: `L4_ENABLER`. target_gate_id: `G8`.
- primary_blocker_class: `INTEGRATION`. primary_invariant_id: `INV_STRUCTURAL_FORWARD_MOTION`.
- indicator_artifact_ref: `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`.
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id parallel-pipeline-lanes-config-2026-05-31 --output reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`.
- bootstrap_endgame_policy: `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`. boot0_track_id: `V1`. boot0_progress_state: `HOLD`.
- evidence_delta: (1) The lane MACHINERY already exists on dev (`pipeline_monitor_identity.load_monitor_lanes`/`validate_*`, `executor_dispatch --bus-dir` threading, `test_agent_bus_namespacing.py`); this wave only adds the committed `pipeline_monitor.lanes` block. (2) Five lanes (lane1..lane5) are configured with disjoint `bus_dir` (`.agent_bus-lane1..5`), `dashboard_port` (8101..8105), and `tmux_session` (`rcx-pipeline-lane1..5`), each satisfying `load_monitor_lanes` collision and format constraints. (3) No runtime-dir change: config-only `L4_ENABLER` under `mu/tools/executors/executor_config.json`.
- progress_proof_before: `executor_config.json` had no `pipeline_monitor.lanes` block, so named lanes could not resolve and the 5 committed parallel lanes were unconfigured despite the machinery being present.
- progress_proof_after: `executor_config.json` carries 5 collision-free committed lanes that `load_monitor_lanes` normalizes, the namespacing suite covers them, and parallel dispatch can target a named lane via `--bus-dir`.

Authorization: standing pipeline-bug-fix / enabler authorization per memory `feedback_autonomous_executor_fix.md`, scoped to this control-surface `L4_ENABLER` wave. The wave-bound override below lets commit automation derive the same-wave override mechanically (exact `Wave ID:` equality required); it must match the header `Wave ID:`.

FOUNDER_OVERRIDE:parallel-pipeline-lanes-config-2026-05-31

## Request from Post-Merge Supervisor

Add the `pipeline_monitor.lanes` config block (5 committed parallel lanes) to `mu/tools/executors/executor_config.json`. The lane MACHINERY already exists on dev (`pipeline_monitor_identity.py` `load_monitor_lanes`/`validate_*`, `executor_dispatch --bus-dir` threading, `test_agent_bus_namespacing.py`). The ONLY gap is the committed lanes config. Each lane needs `{bus_dir, dashboard_port, tmux_session}` satisfying `load_monitor_lanes` constraints: `bus_dir` matches `^\.agent_bus-<id>$` and != `.agent_bus`; `dashboard_port` in 1-65535 and != 8099 (default) and unique; `tmux_session` matches `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$` and != `rcx-pipeline` (default) and unique; lane name matches `LANE_NAME_RE`. Proposed 5 lanes (lane1..lane5): `bus_dir` `.agent_bus-lane1..5`, `dashboard_port` 8101..8105, `tmux_session` `rcx-pipeline-lane1..5`.

Routed next-candidate:
parallel-pipeline-lanes-config-2026-05-31

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `parallel-pipeline-lanes-config-2026-05-31`
- Active packet: `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md`
  - `reports/deferred/non_blocking/parallel-pipeline-lanes-config-2026-05-31_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `parallel-pipeline-lanes-config-2026-05-31`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/parallel-pipeline-lanes-config-2026-05-31_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `parallel-pipeline-lanes-config-2026-05-31`
- Active packet: `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `40141208856f1b038679f983081c14be48a3daef319742a0eb2a95be9db2b900`
- Indicator artifact: `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id parallel-pipeline-lanes-config-2026-05-31 --output reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md. (2) Commit handoff carries 5 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/parallel_pipeline_lanes_config_2026-06-01.md`
  - `reports/deferred/non_blocking/parallel-pipeline-lanes-config-2026-05-31_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parallel-pipeline-lanes-config-2026-05-31.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
