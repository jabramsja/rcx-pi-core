# Lane Monitor Autospawn Cleanup 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: lane-monitor-autospawn-cleanup-2026-06-03
Class: L4_ENABLER (control-surface tooling; no runtime/substrate dir)
target_gate_id: G8
Phase-A-Lock: LOCKED

Purpose: Automate the per-lane tmux monitor LIFECYCLE inside the dispatcher (`executor_dispatch.py`) so a LANE wave's 4-pane monitor is auto-spawned once at launch and its self-healing owner-loop + `rcx-pipeline-laneN` session are auto-cleaned at wave-end -- fixing the founder-observed "lane N tmux opens for a few seconds then exits" zombie-monitor pain and "where are the lane sessions". All three behaviors (auto-spawn, auto-clean, hard-safety lane match) ship together: auto-spawn without auto-clean is WORSE, because the owner-loop self-heals and recreates the session. `pipeline_monitor.sh` is INVOKED / process-matched only, never modified.

## Grounding / Authorization

- TASKS.md authorization: this wave is the bounded `lane-monitor-autospawn-cleanup-2026-06-03` slice of the founder-authorized, UNPARKED `[NEXT-CODEX-POST-REDTEAM]` queue (TASKS.md: "**[NEXT-CODEX-POST-REDTEAM]** **UNPARKED** (2026-03-28, founder-authorized)", current phase OPEN). The wave's own TASKS.md tracker note ("Tracker sync note (2026-06-03, lane-monitor-autospawn-cleanup-2026-06-03)") records Class L4_ENABLER, target_gate_id G8, the evidence_command, and `progress_proof_before`/`progress_proof_after`. `progress_proof_before` is authoritative that this work is NOT yet landed (the dispatcher does not spawn a per-lane monitor and the finished lane's owner-loop keeps recreating the session), so all Work items below are pending.
- FOUNDER_OVERRIDE:lane-monitor-autospawn-cleanup-2026-06-03 (carried verbatim in the TASKS.md tracker note; wave-bound same-wave override so commit automation derives it mechanically).
- Authorization: standing pipeline-bug-fix authorization for autonomous dispatcher/executor bug fixes covers this zombie per-lane-monitor lifecycle fix; the wave-bound FOUNDER_OVERRIDE above is the mechanical same-wave anchor for non-structural adjacency. Tooling-only change, no runtime/substrate edit.
- Governing packet: this file (`reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md`); parent queue packet `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` (referenced by the `[NEXT-CODEX-POST-REDTEAM]` task in TASKS.md).
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

## Scope

In scope (the ONLY files this wave may change):
- `mu/tools/executors/executor_dispatch.py` -- add the per-lane monitor lifecycle (auto-spawn at lane-wave launch; auto-clean at wave-end on all exit paths).
- `mu/tests/tools/test_executor_dispatch.py` (EXISTING file) -- add the regression test. NO new test file (growth cap).

Invoke / process-match targets (NOT modified):
- `tools/observability/pipeline_monitor.sh` -- its `start [--detach]`, `--lane <name>` handling, `__owner-loop` spawn, and `kill-session` are invoked / matched only.

Implementation anchors (READ FIRST -- cite by function name, no file:line):
- In `executor_dispatch.py`: the dispatch-loop launch path that routes ROUTE_PHASE_A and launches the wave for the active `bus_dir`; lane-name derivation from `bus_dir` (a `.agent_bus-<laneN>` suffix -> `laneN`; the default `.agent_bus` / no-suffix bus is MAIN, NOT a lane); `_cleanup_for_signal` and its `signal.signal(...)` registration; and the dispatch loop's normal-return / exit path.
- In `pipeline_monitor.sh`: `start [--detach]`, `--lane <name>`, the `__owner-loop` spawn, and `kill-session`.

- `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (the binding design; these supersede any looser wording in the routed request below):

1. AUTO-SPAWN (lane buses only). When the dispatch loop launches a wave on a LANE bus (`bus_dir` has a `.agent_bus-<laneN>` suffix), spawn the lane monitor ONCE via a non-blocking subprocess: `pipeline_monitor.sh --bus-dir <bus_dir> --lane <laneN> start --detach`. IDEMPOTENT: skip if the `rcx-pipeline-<laneN>` tmux session already exists. Do NOT spawn for the default/main `.agent_bus` bus (it already has its monitor). BEST-EFFORT: on spawn error, log and continue -- never block or fail the dispatch loop.

2. AUTO-CLEAN at wave-end (lane buses only, all exit paths). When the dispatch loop terminates for a LANE wave -- on normal completion/return, the `_cleanup_for_signal` signal path, AND error/exception exit (wrap the loop body in try/finally so cleanup runs regardless, INCLUDING the non-fatal post-merge-verify `Status: error` exit) -- kill the lane owner-loop process(es) selected per Work item 3, then `tmux kill-session -t rcx-pipeline-<laneN>`. Clean once, idempotently.

3. HARD SAFETY -- token-delimited argv match (NON-NEGOTIABLE; this is the fix for the lane1/lane10 prefix-collision defect). Select the lane owner-loop by EXACT WHOLE-TOKEN argv matching, NEVER a substring/prefix test. Split each candidate command line into whitespace-delimited tokens and select it ONLY IF: (a) it contains a `--lane` token whose immediately-following token equals exactly `laneN` (full-string equality), AND (b) it contains a `__owner-loop` token. A regex anchored on a token boundary (`--lane laneN` followed by whitespace or end-of-string) is an acceptable equivalent. A bare substring test on `--lane laneN` is FORBIDDEN: it also selects `--lane lane10` for a `lane1` cleanup -- proven by `printf '%s\n' 'bash tools/observability/pipeline_monitor.sh --lane lane10 __owner-loop' | rg --fixed-strings -- '--lane lane1'` matching. Consequences of the exact-token rule: the MAIN owner-loop carries NO `--lane` token, so it can never be selected; a prefix-colliding sibling lane (e.g. lane10) can never be selected by a lane1 cleanup. The session kill targets ONLY the exact `rcx-pipeline-<laneN>` name, NEVER the bare `rcx-pipeline`.

4. REGRESSION TEST (extend EXISTING `mu/tests/tools/test_executor_dispatch.py`):
   - (a) a LANE-bus launch invokes the monitor spawn (mock the subprocess; assert a `pipeline_monitor.sh ... --lane laneN ... start ... --detach` invocation);
   - (b) a DEFAULT/main `.agent_bus` launch does NOT spawn;
   - (c) wave-end cleanup for `laneN` selects the `--lane laneN __owner-loop` process + the `rcx-pipeline-laneN` session, but NEVER selects: (i) a MAIN no-`--lane` owner-loop, (ii) the bare `rcx-pipeline` session, NOR (iii) a prefix-colliding sibling lane -- assert a `lane1` cleanup does NOT select a `--lane lane10 __owner-loop` process (the token-boundary case for the Work item 3 defect).

## Constraints (NOT in scope)

- Do NOT modify `pipeline_monitor.sh` (invoke / process-match only).
- Do NOT create a new test file -- extend the existing `mu/tests/tools/test_executor_dispatch.py` (growth cap).
- Do NOT touch any runtime/substrate dir (e.g. `rcx_pi/selfhost/`, `mu/host/`, `mu/programs/`, seeds/registries). This is L4_ENABLER tooling only; touching a runtime dir would reclassify the wave.
- Do NOT auto-spawn or clean the default/main `.agent_bus` bus -- it is MAIN, not a lane; its monitor and bare `rcx-pipeline` session are off-limits.
- Do NOT split the three behaviors across waves (auto-spawn without auto-clean worsens the zombie problem).
- Do NOT use file:line citations in this plan -- cite code by function name only.
- Do NOT ship a substring/prefix lane match, even as a fallback (see Work item 3).

## Stop conditions

Halt and escalate (do NOT work around) if:
- The change cannot be confined to `executor_dispatch.py` + the existing `test_executor_dispatch.py` (e.g. `pipeline_monitor.sh` or a runtime dir would need editing).
- A new test file appears necessary (growth-cap violation).
- The exact-whole-token lane match cannot be implemented without a substring/prefix fallback.
- The validation gate fails after a best-effort fix -- diagnose; do not bypass gates or use `--no-verify` outside the bounded `commit_executor.py` Step 12 path.
- Any auto-clean path could reach the MAIN no-`--lane` owner-loop or the bare `rcx-pipeline` session.

## Acceptance criteria

- All required Phase A sections present (Scope, Work items, Constraints, Stop conditions, Acceptance criteria, Grounding/Authorization). Mechanical check: `rg -n 'FOUNDER_OVERRIDE|Authorization:|standing pipeline-bug-fix|TASKS[.]md|governing|Stop|Acceptance|Constraints|Work items' reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md` returns matches.
- evidence_command passes: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py -k "monitor or lane or spawn or cleanup"`.
- Regression test proves (a) lane-bus spawn, (b) main-bus no-spawn, and (c) cleanup selects the lane owner-loop + `rcx-pipeline-laneN` while EXCLUDING the MAIN no-`--lane` owner-loop, the bare `rcx-pipeline` session, AND a prefix-colliding sibling lane (a lane1 cleanup does not select `--lane lane10 __owner-loop`).
- Only `executor_dispatch.py` + the existing `test_executor_dispatch.py` changed; `pipeline_monitor.sh` and all runtime dirs untouched.
- No file:line citations in the plan (function-name citations only).

## Routed Request from Post-Merge Supervisor (provenance; refined by the Work items above)

PLAN CORRECTION: the binding lane match is the EXACT WHOLE-TOKEN argv match in Work item 3 (token-delimited; never a substring/prefix test, which would collide lane1/lane10). The routed text below has been refined accordingly; the Work items are authoritative.

Automate the per-lane tmux monitor LIFECYCLE in the dispatcher so a lane wave's 4-pane monitor is auto-spawned at launch AND its self-healing owner-loop + session are auto-cleaned at wave-end -- fixing the founder-observed 'lane N tmux opens for a few seconds then exits' zombie-monitor pain and 'where are the lane sessions'. ONLY mu/tools/executors/executor_dispatch.py is modified; tools/observability/pipeline_monitor.sh is INVOKED, NOT changed. READ FIRST: in executor_dispatch.py -- the dispatch-loop launch path (where it routes ROUTE_PHASE_A and launches the wave for the active bus_dir), how the lane name is derivable from bus_dir (`.agent_bus-<laneN>` has a lane suffix -> laneN; the default `.agent_bus` / no-suffix bus is MAIN, NOT a lane), `_cleanup_for_signal` and its `signal.signal(...)` registration, and the dispatch loop's normal-return/exit path; and in pipeline_monitor.sh -- `start [--detach]`, the `--lane <name>` handling, the `__owner-loop` spawn, and `kill-session` (these are INVOKE / process-match targets only). REQUIREMENT (ship ALL THREE together -- do NOT split; auto-spawn WITHOUT auto-clean would make the zombie problem WORSE because the owner-loop self-heals/recreates the session): (1) AUTO-SPAWN: when the dispatch loop launches a wave on a LANE bus (bus_dir has a `.agent_bus-<laneN>` lane suffix, NOT the default `.agent_bus` / main), spawn the lane monitor ONCE via a non-blocking subprocess `pipeline_monitor.sh --bus-dir <bus_dir> --lane <laneN> start --detach`. IDEMPOTENT: skip if the `rcx-pipeline-<laneN>` tmux session already exists. Do NOT spawn for the default/main bus (it already has its monitor). BEST-EFFORT: if the spawn errors, log and continue -- never block or fail the dispatch loop on a monitor-spawn error. (2) AUTO-CLEAN at wave-end: when the dispatch loop terminates for a LANE wave, on ALL exit paths -- normal completion/return, the `_cleanup_for_signal` signal path, AND an error/exception exit (wrap the loop body in try/finally so cleanup runs regardless, INCLUDING the non-fatal post-merge-verify `Status: error` exit) -- kill the lane's owner-loop process(es) (select by exact whole-token argv match -- a `--lane` token immediately followed by a token equal to exactly `<laneN>`, plus a `__owner-loop` token; never a substring/prefix test) and the `rcx-pipeline-<laneN>` session (`tmux kill-session -t rcx-pipeline-<laneN>`). Clean once, idempotently. (3) HARD SAFETY (non-negotiable): NEVER match or kill the MAIN no-`--lane` `__owner-loop` (it targets the main repo, has NO `--lane` token) or the `rcx-pipeline` session. The lane process-match MUST require an exact whole-token `--lane <laneN>` argv match (token-delimited; never a substring/prefix test) so that neither a no-`--lane` main owner-loop NOR a prefix-colliding sibling lane (e.g. lane10 for a lane1 cleanup) can ever match; the session kill MUST target only the exact `rcx-pipeline-<laneN>` name, never the bare `rcx-pipeline`. SCOPE: ONLY executor_dispatch.py + a regression test in the EXISTING mu/tests/tools/test_executor_dispatch.py (NO new test file -- growth cap). L4_ENABLER: tooling only, no runtime/substrate dir. Cite code by function name only; NO file:line in the plan. REGRESSION TEST (existing test_executor_dispatch.py): (a) a LANE-bus launch invokes the monitor spawn (mock the subprocess; assert a `pipeline_monitor.sh ... --lane laneN ... start ... --detach` invocation); (b) a DEFAULT/main bus launch does NOT spawn; (c) wave-end cleanup selects a `--lane laneN __owner-loop` process + the `rcx-pipeline-laneN` session for kill, but NEVER a MAIN no-`--lane` owner-loop, the bare `rcx-pipeline` session, NOR a prefix-colliding sibling lane (a lane1 cleanup must not select `--lane lane10 __owner-loop`).

Routed next-candidate:
lane-monitor-autospawn-cleanup-2026-06-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03`
- Active packet: `reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md`
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `lane-monitor-autospawn-cleanup-2026-06-03`
- Active packet: `reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5465dbec26230c4da75abf6f2dbd61fff3c9629adff9dd3054ad7b88a6d1d190`
- Indicator artifact: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `reports/control_plane/lane_monitor_autospawn_cleanup_2026-06-03.md`
  - `reports/deferred/non_blocking/lane-monitor-autospawn-cleanup-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/lane-monitor-autospawn-cleanup-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
