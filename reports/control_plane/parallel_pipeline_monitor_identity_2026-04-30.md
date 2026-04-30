# Parallel Pipeline Monitor Identity

Date: 2026-04-30
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED after active-bus correction
Task: [PARALLEL-PIPELINE]
Wave ID: parallel-pipeline-monitor-identity-2026-04-30
Phase-A-Lock: LOCKED
Lane: control-surface
Authorization: standing pipeline-bug-fix authorization for bounded control-surface L4_ENABLER pipeline hardening; commit automation may derive `FOUNDER_OVERRIDE:parallel-pipeline-monitor-identity-2026-04-30` for L4 adjacency/rolling-cap clearance.
Purpose: Plan the next parallel-pipeline slice: per-worktree dashboard port
allocation, tmux session naming, and dashboard active-bus identity from
configuration, without widening executor runtime semantics.
## Scope: Files/Directories in Scope

This packet is the governing tracked Phase A packet for `[PARALLEL-PIPELINE]`
work item 2 only: per-worktree dashboard ports plus tmux session names from
configuration. The bridge-requested correction is that dashboard lane identity
is not port-only. A named dashboard lane must bind its configured port and read
from its configured active bus root.

Subsequent implementation is limited to these control-surface paths:

- `mu/tools/observability/pipeline_monitor.sh` for tmux session identity,
  monitor launch behavior, configured dashboard launch arguments, and direct use
  of the active bus identity already available to the monitor path.
- `mu/tools/observability/pipeline_dashboard_web.py` for dashboard bind-port
  identity, active bus-root identity, and default-port/default-bus
  compatibility.
- `mu/tools/observability/` only for direct monitor/dashboard helpers that
  already launch or consume the monitor, dashboard, or configured bus identity.
- `tools/session/` only for startup, guard, heartbeat, or preflight surfaces
  that launch, report, or recover the pipeline monitor/dashboard and currently
  assume the default tmux session, dashboard port, or default `.agent_bus` root.
- Existing relevant test directories under `mu/tests/` or `tests/` for focused
  coverage of the observability and startup/preflight surfaces above.
- This packet, if the implementation phase must record a Phase B evidence delta
  or a bridge-requested clarification.

No implementation work is authorized in runtime, seed, substrate, host-semantics,
JS parity, bridge schema, receipt authority, or unrelated documentation paths.
Executor dispatch semantics remain out of scope except for the post-Phase-B
commit-path identity repair addendum below.

## Work Items

1. Confirm the active slice boundary from this packet and `TASKS.md`:
   `[PARALLEL-PIPELINE]` item 1, agent bus namespacing, is already landed and is
   not pending work; item 2, per-worktree dashboard ports plus tmux session names
   from config, is the only open work item in scope for this wave.
2. Define the monitor identity contract in the in-scope control surface:
   - Default lane remains compatible: absent configuration keeps tmux session
     `rcx-pipeline`, dashboard port `8099`, and dashboard data root
     `REPO_ROOT / ".agent_bus"`.
   - Named worktree/bus lanes derive deterministic monitor identity from
     configuration. The identity is a single lane tuple: active bus root,
     dashboard port, and tmux session name.
   - The active bus root may come from the existing bus-dir/bus-id boundary, but
     it must be resolved before dashboard launch and passed to or loaded by the
     dashboard web process together with the configured port.
   - A configured dashboard port by itself is not sufficient named-lane
     identity. A named-lane dashboard must fail closed if it cannot resolve the
     active bus root for the same lane.
   - The dashboard must use the resolved active bus root for every bus-backed
     data source it serves, including raw reviewer output, `bridge.db`,
     executor state, routing metadata, bridge locks, and recovery status.
   - Identity validation must reject unsafe tmux names, invalid ports, missing
     named-lane ports, missing named-lane active bus roots, and duplicate
     configured session or port assignments within the same visible monitor
     configuration.
   - Do not introduce free-port probing, opportunistic runtime allocation, or a
     global reservation daemon; collision avoidance is configuration-backed and
     deterministic.
3. Wire `mu/tools/observability/pipeline_monitor.sh` so monitor startup uses the
   configured tmux session for named lanes while preserving the existing default
   session when no identity config is present. If this script launches or reports
   the web dashboard, that launch/reporting path must carry the same lane tuple:
   active bus root plus dashboard port.
4. Wire `mu/tools/observability/pipeline_dashboard_web.py` so dashboard startup
   uses the configured dashboard port and configured active bus root for named
   lanes while preserving port `8099` and `REPO_ROOT / ".agent_bus"` when no
   identity config is present. The legacy positional port override may remain
   only as default-lane compatibility or as part of a complete port-plus-bus
   named-lane launch path; it must not satisfy named-lane acceptance by itself.
5. Replace direct `REPO_ROOT / ".agent_bus"` dashboard data-source reads with a
   single resolved active-bus path helper inside the in-scope dashboard surface.
   The helper must preserve default behavior for the default lane and must route
   named-lane raw output, bridge database reads, executor state, routing, lock
   checks, and recovery status to the configured bus root.
6. Update only direct startup/preflight/heartbeat surfaces under `tools/session/`
   that launch or report monitor/dashboard state so their displayed commands,
   recovery hints, and watcher status use the configured session, dashboard port,
   and active bus root instead of assuming defaults for every worktree.
7. Add focused tests proving:
   - default monitor/dashboard behavior remains compatible;
   - two named worktree/bus identities produce distinct active bus roots, tmux
     session names, and dashboard ports without collision;
   - a named dashboard lane reads bus-backed state from its configured bus root,
     not from the default `.agent_bus`;
   - invalid or duplicate monitor identity config fails closed, including
     port-only named-lane configuration with no active bus root;
   - startup/preflight output or launch command construction propagates the
     configured active bus root together with the configured monitor identity.

## Constraints: Not in Scope

- Do not rework agent bus namespacing. `TASKS.md` records it as landed in PR
  #833; this packet may consume the existing `--bus-dir`/`.agent_bus-<id>`
  boundary but must not change the bus resolver contract.
- Do not implement `[PARALLEL-PIPELINE]` item 3, Recovery gate Tier 2 transient
  kill auto-retry.
- Do not implement `[PARALLEL-PIPELINE]` item 4, agent teams integration or
  teammate-created worktrees.
- Do not change executor runtime semantics, seed execution, substrate behavior,
  host authority, host-semantics ratchets, or JS parity behavior.
- Do not redesign the dashboard, pipeline monitor UX, bridge schema, receipt
  authority, commit-protection behavior, pager behavior, or worktree creation.
- Do not create a broad new configuration framework. Use the narrowest existing
  repo-tracked configuration surface available to the in-scope monitor/startup
  paths; if none exists, keep the new resolver local to the in-scope
  observability/session-control files.
- Do not treat a distinct dashboard bind port as proof of a distinct dashboard
  lane unless the same launch path also resolves and supplies the active bus
  root.
- Do not scan or edit unrelated dirty files. Search during implementation should
  be limited to direct references to the monitor, dashboard, tmux session name,
  dashboard port, and active bus identity inside the scoped paths above.

## Stop Conditions

Stop and return the packet for Phase A revision if any of these conditions are
hit:

- The monitor identity implementation requires changing executor dispatch
  semantics, runtime behavior, seed/substrate behavior, host authority, or JS
  parity.
- The post-Phase-B commit-path identity repair requires anything broader than
  rebinding chained Phase B routing identity to the locked packet's declared
  `Wave ID` and tracked packet path.
- Collision-free dashboard ports require a dynamic allocator, global lock
  service, background daemon, or free-port probing instead of deterministic
  configuration.
- Dashboard active-bus selection requires changing bridge schema, receipt
  authority, executor bus resolver semantics, or worktree creation behavior.
- Startup/preflight support requires broad repo startup redesign rather than
  direct monitor/dashboard command and status plumbing.
- Existing code truth at implementation time proves item 2 is already fully
  landed, including dashboard active-bus selection; update the packet evidence
  instead of duplicating behavior.
- Implementing item 2 requires item 3 Recovery Tier 2 retry behavior or item 4
  agent-team worktree creation.
- Test coverage would require live tmux/browser/network integration outside the
  existing local test harness; split that into a follow-on proof or manual
  validation note instead of expanding this wave.
- Any required write would fall outside the scoped files/directories in this
  packet.

## Acceptance Criteria

- The packet is no longer a stub: it contains explicit scope, bounded work
  items, constraints, stop conditions, acceptance criteria, and grounding.
- Default compatibility is preserved: with no monitor identity configuration,
  monitor startup still uses tmux session `rcx-pipeline`, dashboard startup still
  uses port `8099`, dashboard data still comes from `REPO_ROOT / ".agent_bus"`,
  and existing default bus behavior remains intact.
- Named worktree/bus configuration can run at least two monitor lanes with
  distinct active bus roots, tmux session names, and dashboard ports, without
  relying on dynamic port discovery.
- A named-lane dashboard serves bus-backed state from its configured active bus
  root. Binding a distinct port while still reading default `.agent_bus` state
  does not satisfy this packet.
- Invalid monitor identity configuration fails closed with an actionable error:
  unsafe tmux session name, invalid port, missing named-lane port, missing
  named-lane active bus root, port-only named-lane dashboard configuration,
  duplicate session, or duplicate port.
- Startup/preflight/heartbeat surfaces in scope no longer present default
  session/port/bus-root assumptions as the only monitor identity when a named
  lane is configured.
- Tests cover default behavior, two named identities, configured dashboard bus
  reads, invalid/duplicate config, port-only named-lane rejection, and
  startup/preflight propagation of configured monitor identity.
- The implementation does not modify runtime, seed, substrate, host-semantics,
  JS parity, recovery Tier 2, agent-team, bridge schema, receipt authority, or
  bus-resolver semantics.
- The post-Phase-B commit path no longer derives commit validation identity from
  the undated Phase A surface `--plan-name` when the locked packet declares a
  more specific `Wave ID`; targeted dispatcher regression coverage proves the
  dated packet case and the generic Phase A surface cases both pass.

## Post-Phase-B Commit-Path Repair Addendum

After Phase B reached `commit_ready`, the dispatcher failed before commit because
the chained commit validation expected the undated surface id
`parallel-pipeline-monitor-identity` while the Phase B handoff declared
`parallel-pipeline-monitor-identity-2026-04-30`.

This addendum authorizes only the narrow structural repair needed to continue
the already-converged wave:

- `mu/tools/executors/executor_dispatch.py` may read the locked packet's explicit
  `Wave ID:` during Phase A-to-Phase B chaining and use that id, plus a
  repo-relative tracked packet path, for downstream Phase B/commit handoff
  validation.
- `mu/tests/tools/test_executor_dispatch.py` may add regression coverage for the
  observed dated-wave mismatch and preserve existing generic Phase A surface
  behavior.
- `tests/docs/test_growth_caps.py` may record the one-script growth-cap
  authorization for `mu/tools/observability/pipeline_monitor_identity.py`, which
  is the new helper required by this monitor identity wave.

No handoff bypass is authorized. Handoff validation remains fail-closed; the
dispatcher now supplies the same packet identity that Phase B used to generate
the handoff.

## Grounding / Authorization

- `TASKS.md` authorizes `[PARALLEL-PIPELINE]` as `OPEN / PARTIAL`, records agent
  bus namespacing as landed in PR #833, and records this packet's work item 2 as
  landed in PR #836.
- PR #836 merged this packet at `fc1a2a1d` on 2026-04-30. The implementation
  commit `8bbdf0f3` added `mu/tools/observability/pipeline_monitor_identity.py`
  and updated the monitor, dashboard, startup/autoping, and focused regression
  surfaces for configured monitor identity.
- `mu/tools/observability/pipeline_monitor_identity.py` defines the monitor
  identity tuple: configured lane, active bus root, dashboard port, and tmux
  session. It rejects invalid bus roots, unsafe tmux session names, invalid
  ports, duplicate sessions, duplicate ports, duplicate bus roots, and
  port-only named lanes.
- `mu/tools/observability/pipeline_monitor.sh` resolves that identity before
  launching tmux, uses the configured tmux session and dashboard port in the
  founder-facing startup output, and passes the configured bus/session into
  Codex autoping reseed.
- `mu/tools/observability/pipeline_dashboard_web.py` resolves the same identity
  at startup and uses the configured active bus root for dashboard-backed bus
  reads through `active_bus_path()`, preserving default-lane compatibility with
  `.agent_bus` and port `8099`.
- `mu/tests/tools/test_recovery_gate.py` covers named-lane monitor startup,
  dashboard active-bus reads, invalid/duplicate monitor identity config, and
  autoping reseed propagation.
- Remaining `[PARALLEL-PIPELINE]` residue is outside this packet: recovery Tier
  2 transient-kill auto-retry and teammate worktree integration.
- Post-Phase-B root-cause evidence from
  `.agent_bus/observability/pipeline_agent_events.jsonl` recorded
  `event_type="executor_hard_fail"` with reason
  `Phase B handoff validation failed: Phase B handoff wave_id mismatch:
  expected parallel-pipeline-monitor-identity, got
  parallel-pipeline-monitor-identity-2026-04-30`.
- The handoff truth at `.agent_bus/executors/phase_b_handoff.json:2` declared
  `parallel-pipeline-monitor-identity-2026-04-30`, matching this packet's
  `Wave ID` header.
- The commit gate reproduced the docs growth-cap failure as
  `tests/docs/test_growth_caps.py::TestGrowthCaps::test_tool_script_count_within_cap`:
  tool script count `115` exceeded baseline `68` plus cap `46`, and the wave's
  new counted tool script is `mu/tools/observability/pipeline_monitor_identity.py`.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `parallel-pipeline-monitor-identity-2026-04-30`
- Active packet: `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e593ec1b6121575c5a0fd37f5ab7281dcfcecba5645b7200359e329b604de400`
- Indicator artifact: `reports/l4_wave_indicators/parallel-pipeline-monitor-identity-2026-04-30.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_codex_autoping_watch.py mu/tests/tools/test_codex_startup_state.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T06-42-35p00-00_61b4d68f.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/parallel-pipeline-monitor-identity-2026-04-30.json`
  - `packet`: `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md`
  - `reports/l4_wave_indicators/parallel-pipeline-monitor-identity-2026-04-30.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
