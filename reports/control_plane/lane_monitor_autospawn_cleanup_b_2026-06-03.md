# Lane Monitor Autospawn Cleanup B 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: lane-monitor-autospawn-cleanup-2026-06-03b
Phase-A-Lock: LOCKED
Purpose: Automate the per-lane tmux monitor LIFECYCLE in the dispatcher so a lane wave's 4-pane monitor is auto-spawned at launch AND its self-healing owner-loop + session are auto-cleaned at wave-end -- fixing the founder-observed 'lane N tmux opens for a few seconds then exits' zombie-monitor pain and 'where are the lane sessions'. ONLY mu/tools/executors/executor_dispatch.py is modified; tools/observability/pipeline_monitor.sh is INVOKED / process-matched, NOT changed. READ FIRST in executor_dispatch.py: BOTH wave-launch surfaces -- the routing-driven dispatch-loop launch path (where it routes ROUTE_PHASE_A and launches the wave for the active bus_dir) AND the modular subcommand/subparser launch path; how the lane name is derivable from bus_dir (`.agent_bus-<laneN>` has a lane suffix -> laneN; the default `.agent_bus` / no-suffix bus is MAIN, NOT a lane); how the configured tmux session name is resolved from pipeline_monitor lane config (load_monitor_lanes / pipeline_monitor.lanes.*.tmux_session); `_cleanup_for_signal` and its `signal.signal(...)` registration; and the dispatch loop's normal-return/exit path. In pipeline_monitor.sh read `start [--detach]`, `--lane <name>` handling, the `__owner-loop` spawn, `has-session`, and `kill-session` (INVOKE / process-match targets only). SHIP ALL OF THE FOLLOWING TOGETHER (auto-spawn WITHOUT auto-clean would make the zombie problem WORSE because the owner-loop self-heals/recreates the session): (1) AUTO-SPAWN on a LANE bus only: when a wave launches on a `.agent_bus-<laneN>` lane bus (NOT the default `.agent_bus`/main), spawn the lane monitor ONCE via a non-blocking subprocess `pipeline_monitor.sh --bus-dir <bus_dir> --lane <laneN> start --detach`. Cover BOTH launch surfaces (the dispatch-loop path AND the modular subparser path). IDEMPOTENT: skip the spawn if the lane's configured tmux session already exists (`tmux has-session` against the EXACT configured name). BEST-EFFORT: on spawn error, log and continue -- never block or fail the launch. (2) AUTO-CLEAN at wave-end on ALL exit paths -- normal completion/return, the `_cleanup_for_signal` signal path, AND an error/exception exit -- by wrapping the loop body in try/finally so cleanup runs regardless, INCLUDING the non-fatal post-merge-verify `Status: error` exit. Clean once, idempotently. (3) OWNER-LOOP MATCH BY EXACT TOKEN + IDENTITY: the owner-loop process match must require `--lane laneN` as a WHOLE shell token (NOT a substring -- `--lane lane1` must NOT match `--lane lane10`; guard the prefix collision) AND `__owner-loop`, AND must be bound to the CURRENT repo-root / session identity (match the owner-loop's repo path / bus_dir, NOT the lane token alone -- two different repos can both run a laneN owner-loop; a cross-repo same-lane owner-loop must NOT be killed). (4) EXACT TMUX TARGETS: every `tmux has-session` (spawn idempotency) and `tmux kill-session` (cleanup) must use an EXACT session target (e.g. `tmux has-session -t =<session>` / `kill-session -t =<session>` exact-match form), never a prefix-capable target. (5) TERM -> BOUNDED WAIT -> SIGKILL: kill surviving owner-loops with SIGTERM first, then a bounded liveness wait, then SIGKILL the survivors (the owner-loop's TERM trap does cleanup but does NOT exit, so SIGTERM alone leaves it alive -- a SIGKILL fallback is required). (6) CLOSE THE ASYNC-START RACE: retain the spawn subprocess (Popen) handle so an in-flight monitor spawn cannot create the owner-loop / session AFTER the final wave-end cleanup ran (reap/await or kill the in-flight spawn during cleanup so no session/owner-loop survives the cleanup). (7) HONOR THE CONFIGURED SESSION NAME: a lane may be configured with `pipeline_monitor.lanes.*.tmux_session` != `rcx-pipeline-<laneN>` (the identity helper allows arbitrary validated names and pipeline_monitor.sh creates exactly that configured session). Resolve the configured session name from the SAME config the monitor reads (load_monitor_lanes, matched by bus_dir) and use it for spawn-idempotency probe AND cleanup kill; fall back to `rcx-pipeline-<laneN>` only when repo_root is unknown / the bus has no configured identity / the config cannot be read. NEVER raise on a config error (a config error must not turn a real lane into an uncleanable zombie). (8) HARD SAFETY (non-negotiable): NEVER match or kill the MAIN no-`--lane` `__owner-loop` (it targets the main repo, has NO `--lane` token) or the bare `rcx-pipeline` session. The configured-name resolution and the fallback can never collapse to the bare `rcx-pipeline` MAIN session. SCOPE: ONLY mu/tools/executors/executor_dispatch.py + regression tests in the EXISTING mu/tests/tools/test_executor_dispatch.py (NO new test file -- growth cap). pipeline_monitor.sh INVOKED, not modified. L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by FUNCTION NAME only; NO file:line in the plan. REGRESSION TESTS (existing test_executor_dispatch.py), one per requirement: (a) a LANE-bus launch invokes the monitor spawn (mock subprocess; assert `pipeline_monitor.sh ... --lane laneN ... start ... --detach`); (b) a DEFAULT/main bus launch does NOT spawn; (c) the modular subparser launch path ALSO spawns on a lane bus; (d) prefix-collision: `--lane lane1` cleanup must NOT select a `--lane lane10` owner-loop; (e) exact tmux target: kill-session uses the exact-match form, not prefix; (f) TERM-survivor -> SIGKILL fallback fires for an owner-loop whose TERM trap does not exit; (g) async-race: an in-flight spawn handle is reaped/killed so no session survives final cleanup; (h) configured-name: a lane configured with a non-default tmux_session is probed/cleaned by the CONFIGURED name, not the hardcoded rcx-pipeline-laneN; (i) hard-safety: a MAIN no-`--lane` owner-loop / bare `rcx-pipeline` session is NEVER selected for kill.

## Scope

Files/directories in scope:
- `mu/tools/executors/executor_dispatch.py` -- the ONLY production file modified. Touch BOTH wave-launch surfaces (the routing-driven dispatch-loop launch path and the modular subcommand/subparser launch path), the `_cleanup_for_signal` signal path, and the dispatch loop's normal-return/exit path.
- `mu/tests/tools/test_executor_dispatch.py` -- EXISTING regression test file; one test per requirement is appended here (NO new test file -- growth cap).

Invoked / process-matched but NOT modified:
- `tools/observability/pipeline_monitor.sh` -- invoked as `... --bus-dir <bus_dir> --lane <laneN> start --detach`; its `__owner-loop`, `has-session`, and `kill-session` are process-match / tmux targets only.

L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by FUNCTION NAME only; no file:line in this plan. The complete 8-point spec is enumerated up front (Work items) so the review converges without round-by-round path mining (the prior PR #1069 specified only 3 of 8 and stranded -- bridge mined the rest plus a bot P2 on the configured-session-name gap).

- `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03b_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks from the `[NEXT-CODEX-POST-REDTEAM]` current phase. SHIP ALL EIGHT TOGETHER -- auto-spawn without auto-clean makes the zombie problem worse because the owner-loop self-heals/recreates the session. Each maps to exactly one regression test (a-i) in the existing `test_executor_dispatch.py`:

1. AUTO-SPAWN on a LANE bus only: when a wave launches on a `.agent_bus-<laneN>` lane bus (NOT the default `.agent_bus`/MAIN), spawn the lane monitor ONCE via a non-blocking subprocess `pipeline_monitor.sh --bus-dir <bus_dir> --lane <laneN> start --detach`. Cover BOTH launch surfaces (dispatch-loop path AND modular subparser path). IDEMPOTENT: skip the spawn if the lane's configured tmux session already exists (exact `tmux has-session`). BEST-EFFORT: on spawn error, log and continue -- never block or fail the launch.
2. AUTO-CLEAN at wave-end on ALL exit paths -- normal completion/return, the `_cleanup_for_signal` signal path, AND an error/exception exit -- by wrapping the loop body in try/finally so cleanup runs regardless, INCLUDING the non-fatal post-merge-verify `Status: error` exit. Clean once, idempotently.
3. OWNER-LOOP MATCH BY EXACT TOKEN + IDENTITY: the owner-loop process match must require `--lane laneN` as a WHOLE shell token (NOT a substring -- `--lane lane1` must NOT match `--lane lane10`) AND `__owner-loop`, AND must be bound to the CURRENT repo-root / session identity (match the owner-loop's repo path / bus_dir, not the lane token alone -- a cross-repo same-lane owner-loop must NOT be killed).
4. EXACT TMUX TARGETS: every `tmux has-session` (spawn idempotency) and `tmux kill-session` (cleanup) must use an EXACT session target (`-t =<session>` exact-match form), never a prefix-capable target.
5. TERM -> BOUNDED WAIT -> SIGKILL: kill surviving owner-loops with SIGTERM first, then a bounded liveness wait, then SIGKILL the survivors (the owner-loop's TERM trap does cleanup but does NOT exit, so SIGTERM alone leaves it alive).
6. CLOSE THE ASYNC-START RACE: retain the spawn subprocess (Popen) handle so an in-flight monitor spawn cannot create the owner-loop / session AFTER the final wave-end cleanup ran (reap/await or kill the in-flight spawn during cleanup).
7. HONOR THE CONFIGURED SESSION NAME: resolve the configured session name from the SAME config the monitor reads (load_monitor_lanes, matched by bus_dir; `pipeline_monitor.lanes.*.tmux_session`) and use it for the spawn-idempotency probe AND the cleanup kill; fall back to `rcx-pipeline-<laneN>` only when repo_root is unknown / the bus has no configured identity / the config cannot be read. NEVER raise on a config error.
8. HARD SAFETY (non-negotiable): NEVER match or kill the MAIN no-`--lane` `__owner-loop` (targets the main repo, has NO `--lane` token) or the bare `rcx-pipeline` session. The configured-name resolution and the fallback can never collapse to the bare `rcx-pipeline` MAIN session.

## Constraints

What is NOT in scope:
- Do NOT modify `tools/observability/pipeline_monitor.sh` -- invoke / process-match only.
- Do NOT create a new test file -- regression tests go into the EXISTING `mu/tests/tools/test_executor_dispatch.py` (growth cap).
- Do NOT touch any runtime/substrate dir; this is an L4_ENABLER and the production change is confined to `mu/tools/executors/executor_dispatch.py`.
- Do NOT auto-spawn or auto-clean on the default `.agent_bus` / no-suffix MAIN bus -- lane buses (`.agent_bus-<laneN>`) only.
- Do NOT match or kill the MAIN no-`--lane` `__owner-loop` or the bare `rcx-pipeline` session under any config-resolution or fallback path.
- Do NOT use file:line citations -- function names only.
- Do NOT raise on a config-read error -- a config error must not turn a real lane into an uncleanable zombie.

## Stop conditions

- HARD STOP -- this is a Phase A DESIGN packet. Do NOT begin implementation until this plan is agent-reviewed and bridge-converged and `Phase-A-Lock` flips to LOCKED.
- Do NOT proceed if any requirement cannot be satisfied without editing `pipeline_monitor.sh` or touching a runtime/substrate dir -- halt and escalate for a new packet (scope is `executor_dispatch.py` + the existing test file only).
- Do NOT proceed if a requirement would require a NEW test file -- halt (growth cap; tests append to the existing `test_executor_dispatch.py`).
- Do NOT ship auto-spawn without auto-clean, or auto-clean without the hard-safety guard -- partial delivery makes the zombie-monitor problem worse. Halt unless all eight requirements land together.
- Do NOT ship if the configured-session-name resolution or its fallback can collapse to the bare `rcx-pipeline` MAIN session, or if the `--lane laneN` match can select a MAIN no-`--lane` owner-loop, a cross-repo same-lane owner-loop, or a `--lane lane10` owner-loop under a `--lane lane1` cleanup -- halt; the hard-safety and identity invariants are non-negotiable.
- Do NOT advance to Phase B / commit until all nine regression tests (a-i) exist and the validation gate passes green.
- Do NOT perform manual git operations (commit/push/merge) -- use the executor pipeline only; stop and ask if the pipeline cannot run.

## Acceptance criteria

Validation gate (must pass green): `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py -k "monitor or lane or spawn or cleanup"`.

One regression test per requirement in the existing `test_executor_dispatch.py`:
- (a) a LANE-bus launch invokes the monitor spawn (mock subprocess; assert `pipeline_monitor.sh ... --lane laneN ... start ... --detach`);
- (b) a DEFAULT/main bus launch does NOT spawn;
- (c) the modular subparser launch path ALSO spawns on a lane bus;
- (d) prefix-collision: `--lane lane1` cleanup must NOT select a `--lane lane10` owner-loop;
- (e) exact tmux target: kill-session uses the exact-match form, not prefix;
- (f) TERM-survivor -> SIGKILL fallback fires for an owner-loop whose TERM trap does not exit;
- (g) async-race: an in-flight spawn handle is reaped/killed so no session survives final cleanup;
- (h) configured-name: a lane configured with a non-default tmux_session is probed/cleaned by the CONFIGURED name, not the hardcoded rcx-pipeline-laneN;
- (i) hard-safety: a MAIN no-`--lane` owner-loop / bare `rcx-pipeline` session is NEVER selected for kill.

Additional acceptance gates: `tools/observability/pipeline_monitor.sh` is unmodified (invoke / process-match only); no new test file is added; the plan contains no file:line citations; no runtime/substrate dir is touched.

## Grounding / Authorization

- TASKS.md authorizes this wave under `[NEXT-CODEX-POST-REDTEAM]` -- Tracker sync note (2026-06-03, lane-monitor-autospawn-cleanup-2026-06-03b): Class L4_ENABLER; target_gate_id G8; Packet `reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`; evidence_command `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py -k "monitor or lane or spawn or cleanup"`; primary_blocker_class INTEGRATION; primary_invariant_id INV_STRUCTURAL_FORWARD_MOTION; bootstrap_endgame_policy SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id V1; boot0_progress_state HOLD.
- FOUNDER_OVERRIDE:lane-monitor-autospawn-cleanup-2026-06-03b -- wave-bound override present on the TASKS.md tracker note so commit automation can derive the same-wave override mechanically.
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (control-surface L4_ENABLER dispatcher fix; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance).
- Governing packet: this file (`reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`).
- indicator_artifact_ref: reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json; indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id lane-monitor-autospawn-cleanup-2026-06-03b --output reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`.

## Request from Post-Merge Supervisor

Automate the per-lane tmux monitor LIFECYCLE in the dispatcher so a lane wave's 4-pane monitor is auto-spawned at launch AND its self-healing owner-loop + session are auto-cleaned at wave-end -- fixing the founder-observed 'lane N tmux opens for a few seconds then exits' zombie-monitor pain and 'where are the lane sessions'. ONLY mu/tools/executors/executor_dispatch.py is modified; tools/observability/pipeline_monitor.sh is INVOKED / process-matched, NOT changed. READ FIRST in executor_dispatch.py: BOTH wave-launch surfaces -- the routing-driven dispatch-loop launch path (where it routes ROUTE_PHASE_A and launches the wave for the active bus_dir) AND the modular subcommand/subparser launch path; how the lane name is derivable from bus_dir (`.agent_bus-<laneN>` has a lane suffix -> laneN; the default `.agent_bus` / no-suffix bus is MAIN, NOT a lane); how the configured tmux session name is resolved from pipeline_monitor lane config (load_monitor_lanes / pipeline_monitor.lanes.*.tmux_session); `_cleanup_for_signal` and its `signal.signal(...)` registration; and the dispatch loop's normal-return/exit path. In pipeline_monitor.sh read `start [--detach]`, `--lane <name>` handling, the `__owner-loop` spawn, `has-session`, and `kill-session` (INVOKE / process-match targets only). SHIP ALL OF THE FOLLOWING TOGETHER (auto-spawn WITHOUT auto-clean would make the zombie problem WORSE because the owner-loop self-heals/recreates the session): (1) AUTO-SPAWN on a LANE bus only: when a wave launches on a `.agent_bus-<laneN>` lane bus (NOT the default `.agent_bus`/main), spawn the lane monitor ONCE via a non-blocking subprocess `pipeline_monitor.sh --bus-dir <bus_dir> --lane <laneN> start --detach`. Cover BOTH launch surfaces (the dispatch-loop path AND the modular subparser path). IDEMPOTENT: skip the spawn if the lane's configured tmux session already exists (`tmux has-session` against the EXACT configured name). BEST-EFFORT: on spawn error, log and continue -- never block or fail the launch. (2) AUTO-CLEAN at wave-end on ALL exit paths -- normal completion/return, the `_cleanup_for_signal` signal path, AND an error/exception exit -- by wrapping the loop body in try/finally so cleanup runs regardless, INCLUDING the non-fatal post-merge-verify `Status: error` exit. Clean once, idempotently. (3) OWNER-LOOP MATCH BY EXACT TOKEN + IDENTITY: the owner-loop process match must require `--lane laneN` as a WHOLE shell token (NOT a substring -- `--lane lane1` must NOT match `--lane lane10`; guard the prefix collision) AND `__owner-loop`, AND must be bound to the CURRENT repo-root / session identity (match the owner-loop's repo path / bus_dir, NOT the lane token alone -- two different repos can both run a laneN owner-loop; a cross-repo same-lane owner-loop must NOT be killed). (4) EXACT TMUX TARGETS: every `tmux has-session` (spawn idempotency) and `tmux kill-session` (cleanup) must use an EXACT session target (e.g. `tmux has-session -t =<session>` / `kill-session -t =<session>` exact-match form), never a prefix-capable target. (5) TERM -> BOUNDED WAIT -> SIGKILL: kill surviving owner-loops with SIGTERM first, then a bounded liveness wait, then SIGKILL the survivors (the owner-loop's TERM trap does cleanup but does NOT exit, so SIGTERM alone leaves it alive -- a SIGKILL fallback is required). (6) CLOSE THE ASYNC-START RACE: retain the spawn subprocess (Popen) handle so an in-flight monitor spawn cannot create the owner-loop / session AFTER the final wave-end cleanup ran (reap/await or kill the in-flight spawn during cleanup so no session/owner-loop survives the cleanup). (7) HONOR THE CONFIGURED SESSION NAME: a lane may be configured with `pipeline_monitor.lanes.*.tmux_session` != `rcx-pipeline-<laneN>` (the identity helper allows arbitrary validated names and pipeline_monitor.sh creates exactly that configured session). Resolve the configured session name from the SAME config the monitor reads (load_monitor_lanes, matched by bus_dir) and use it for spawn-idempotency probe AND cleanup kill; fall back to `rcx-pipeline-<laneN>` only when repo_root is unknown / the bus has no configured identity / the config cannot be read. NEVER raise on a config error (a config error must not turn a real lane into an uncleanable zombie). (8) HARD SAFETY (non-negotiable): NEVER match or kill the MAIN no-`--lane` `__owner-loop` (it targets the main repo, has NO `--lane` token) or the bare `rcx-pipeline` session. The configured-name resolution and the fallback can never collapse to the bare `rcx-pipeline` MAIN session. SCOPE: ONLY mu/tools/executors/executor_dispatch.py + regression tests in the EXISTING mu/tests/tools/test_executor_dispatch.py (NO new test file -- growth cap). pipeline_monitor.sh INVOKED, not modified. L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by FUNCTION NAME only; NO file:line in the plan. REGRESSION TESTS (existing test_executor_dispatch.py), one per requirement: (a) a LANE-bus launch invokes the monitor spawn (mock subprocess; assert `pipeline_monitor.sh ... --lane laneN ... start ... --detach`); (b) a DEFAULT/main bus launch does NOT spawn; (c) the modular subparser launch path ALSO spawns on a lane bus; (d) prefix-collision: `--lane lane1` cleanup must NOT select a `--lane lane10` owner-loop; (e) exact tmux target: kill-session uses the exact-match form, not prefix; (f) TERM-survivor -> SIGKILL fallback fires for an owner-loop whose TERM trap does not exit; (g) async-race: an in-flight spawn handle is reaped/killed so no session survives final cleanup; (h) configured-name: a lane configured with a non-default tmux_session is probed/cleaned by the CONFIGURED name, not the hardcoded rcx-pipeline-laneN; (i) hard-safety: a MAIN no-`--lane` owner-loop / bare `rcx-pipeline` session is NEVER selected for kill.

Routed next-candidate:
lane-monitor-autospawn-cleanup-2026-06-03b

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03b`
- Active packet: `reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03b`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03b_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03b`
- Active packet: `reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e2cdcb38460027015501e0bffeb5fc29fca2f0e47a78a5471ee0dd6b370e7dd7`
- Indicator artifact: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/lane_monitor_autospawn_cleanup_b_2026-06-03.md`
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03b.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
