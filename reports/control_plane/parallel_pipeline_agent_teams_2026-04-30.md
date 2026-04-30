# Parallel Pipeline Agent Teams

Date: 2026-04-30
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PARALLEL-PIPELINE]
Wave ID: parallel-pipeline-agent-teams
Phase-A-Lock: LOCKED
Wave: PARALLEL-PIPELINE-AGENT-TEAMS-2026-04-30
Lane: control-surface (pipeline scaling)
Classification: L4_ENABLER
FOUNDER_OVERRIDE:PARALLEL-PIPELINE-AGENT-TEAMS-2026-04-30
Authorization: TASKS.md `[PARALLEL-PIPELINE]` item 4 is founder-authorized as the remaining open teammate worktree integration wave.
Purpose: Plan `[PARALLEL-PIPELINE]` item 4 only: agent teams integration where teammates auto-create git worktrees with namespaced agent buses. Items 1, 2, and 3 are not pending work in this packet: TASKS.md records bus namespacing landed in PR #833, per-worktree dashboard/tmux identity landed in PR #836, and Tier 2 transient-kill retry satisfied by existing recovery code.

## Scope

This packet governs the first implementation plan for `[PARALLEL-PIPELINE]` item 4: teammate worktree integration with namespaced buses.

Files and directories in scope for the follow-on implementation wave:

- `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md` as the governing Phase A packet.
- `mu/tools/executors/executor_dispatch.py` as the explicit teammate/agent-team launcher control surface for this wave. The bounded implementation area is the modular `phase-a` surface, Phase A routing record creation, recoverable surface-chain execution, and Phase A -> Phase B -> commit handoff path that already propagates `--bus-dir`.
- `mu/tools/executors/executor_common.py` for existing agent-bus namespace validation and any shared dirty-worktree/worktree-root guard needed by the dispatcher integration. Edits here are limited to reusable validation consumed by `executor_dispatch.py`.
- `mu/tools/observability/pipeline_monitor_identity.py` for consuming an already-selected teammate lane, bus root, dashboard port, and tmux session identity. Edits here are limited to rejecting ambiguous or colliding lane identity; no identity-model redesign is in scope.
- `mu/tools/observability/pipeline_monitor.sh` for passing the selected teammate bus and lane identity into monitor startup without falling back to the default `.agent_bus` or shared tmux session.
- `mu/tools/observability/pipeline_dashboard_web.py` for serving the selected teammate lane from the configured active bus root without dashboard port collision.
- `mu/tests/tools/test_executor_dispatch.py` for dispatcher, routing-record, worktree create/select, namespaced bus handoff, and failure-mode regression coverage for item 4.
- `mu/tests/tools/test_agent_bus_namespacing.py` for non-regression coverage of already-landed item 1 bus namespacing when teammate worktree startup consumes a namespaced bus.
- `mu/tests/tools/` for a narrowly named new test file only if the follow-on implementation cannot keep focused item 4 coverage in the two existing test files above.

## Work Items

1. Implement item 4 through `mu/tools/executors/executor_dispatch.py`: before dispatching a teammate/agent-team lane through the `phase-a` control surface, deterministically create or select the lane's git worktree and bind that lane to a namespaced agent bus.
2. Keep worktree create/select idempotent for an existing matching teammate lane, and fail closed when the requested lane would share the caller's dirty worktree, the default `.agent_bus`, a shared lock root, a tmux session, or a dashboard port.
3. Wire the selected bus directory, lane, dashboard port, and tmux session identity through the already-landed bus and monitor identity surfaces: `executor_common.py`, `pipeline_monitor_identity.py`, `pipeline_monitor.sh`, and `pipeline_dashboard_web.py`. The implementation must consume those surfaces rather than redesigning the namespace regex, default bus behavior, dashboard identity model, or Tier 2 retry policy.
4. Add operator-facing rejection messages for the failure modes TASKS.md says this wave solves: dirty-worktree scope creep, stale bridge retries from shared state, shared lock contention, and dashboard port collisions.
5. Add focused tests in `mu/tests/tools/test_executor_dispatch.py` and `mu/tests/tools/test_agent_bus_namespacing.py`, or a narrowly named new file under `mu/tests/tools/` if required, proving teammate worktree create/select, namespaced bus handoff, monitor/dashboard identity routing, collision rejection, and non-regression of already-landed bus namespacing.

## Constraints

- Do not reopen `[PARALLEL-PIPELINE]` items 1, 2, or 3. TASKS.md records item 1 bus namespacing and item 2 per-worktree dashboard/tmux identity as landed, and item 3 Tier 2 transient-kill retry as satisfied.
- Do not inspect or rewrite downstream implementation in this Phase A packet rewrite. This packet was rebuilt from the governing packet stub, the bridge blocking findings, cited TASKS.md `[PARALLEL-PIPELINE]` lines, and the minimum scoped dispatcher/test line evidence needed to replace the unnamed launcher entrypoint.
- Do not broaden into runtime/substrate semantics, parity work, recovery-gate policy changes, dashboard redesign, or general docs/tracker cleanup.
- Do not write outside `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md` while fixing this bridge REQUEST_CHANGES packet.
- Do not add or edit an unnamed teammate launcher outside the explicit scope list. If item 4 cannot be implemented through the scoped dispatcher/control surfaces, the implementation wave must stop for a bridge-reviewed packet amendment.
- Do not create a new agent bus namespace scheme. Reuse the already-landed namespaced bus behavior described by TASKS.md.
- Do not treat TASKS.md authorization as proof that every possible teammate integration gap is still unlanded. If implementation evidence later proves item 4 is already complete, stop and update the packet/status rather than duplicating work.

## Stop Conditions

- Stop if TASKS.md no longer marks `[PARALLEL-PIPELINE]` item 4 as the current open residue.
- Stop if current implementation evidence proves item 4 is already complete; update packet/status instead of creating duplicate teammate worktree logic.
- Stop if the implementation requires edits outside the explicit scoped files/directories and no bridge-reviewed packet amendment exists.
- Stop if worktree creation would operate on or hide a dirty worktree, a shared default `.agent_bus`, a shared lock, or a conflicting monitor/dashboard identity.
- Stop if the change would alter landed bus namespacing, per-worktree monitor identity, or Tier 2 retry semantics instead of only consuming those surfaces.
- Stop if focused tests cannot distinguish teammate-created worktree lanes from the existing default lane.

## Acceptance Criteria

- The Phase A packet contains `Scope`, `Work Items`, `Constraints`, `Stop Conditions`, `Acceptance Criteria`, and `Grounding / Authorization` sections, plus a same-wave `FOUNDER_OVERRIDE` line for the control-surface L4_ENABLER wave.
- Pending work is limited to `[PARALLEL-PIPELINE]` item 4. Items 1, 2, and 3 are described only as landed/satisfied grounding, not as unresolved implementation work.
- Scope explicitly lists every file or directory authorized for the follow-on implementation wave, including `mu/tools/executors/executor_dispatch.py` as the teammate/agent-team launcher control surface. No unnamed future entrypoint-identification task remains.
- The implementation plan names bounded control-surface areas for worktree creation, bus/session identity handoff, dispatcher/monitor startup, and focused tests.
- Follow-on implementation, when authorized, auto-creates or selects a teammate git worktree with a namespaced bus and does not silently fall back to the caller's dirty worktree or default bus.
- Follow-on implementation, when authorized, preserves existing bus namespacing, monitor identity, dashboard lane identity, and Tier 2 retry behavior.
- Focused tests cover teammate worktree creation/selection, namespaced bus handoff, monitor/dashboard identity routing, collision rejection, and non-regression for the already-landed item 1 and item 2 behavior.
- Validation commands for the packet rewrite pass:
  - `nl -ba reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md | sed -n '1,220p'`
  - `rg -n "^(## (Scope|Work Items|Constraints|Stop Conditions|Acceptance Criteria|Grounding / Authorization)|FOUNDER_OVERRIDE|Authorization:|Phase-A-Lock|Status:|Purpose:)" reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`
  - `nl -ba TASKS.md | sed -n '360,366p'`

## Grounding / Authorization

- TASKS.md lines 359-365 mark `[PARALLEL-PIPELINE]` as `OPEN / PARTIAL` and founder-authorized, with item 4 as the remaining open work: "Agent teams integration -- teammates auto-create worktrees with namespaced buses (open)."
- TASKS.md lines 360-362 authorize the wave goal: enable parallel pipelines across git worktrees with agent teams, after `[PIPELINE-RECOVERY]` Phase 1 and agent bus namespacing have landed.
- TASKS.md lines 362-363 record current code truth for completed/satisfied prerequisites: item 1 bus namespacing landed in PR #833, item 2 per-worktree dashboard/tmux identity landed in PR #836, and item 3 Tier 2 transient-kill retry is satisfied by existing recovery code.
- TASKS.md line 364 states the target failure modes this wave should solve: dirty worktree scope creep, stale bridge retries after state changes, shared lock contention, and dashboard port collisions.
- TASKS.md line 365 places the wave in the control-surface pipeline scaling lane.
- `mu/tools/executors/executor_dispatch.py` is the scoped launcher/control entrypoint for item 4 because its modular `phase-a` surface builds Phase A executor commands (`mu/tools/executors/executor_dispatch.py:514-532`, `mu/tools/executors/executor_dispatch.py:581-591`), routing records (`mu/tools/executors/executor_dispatch.py:407-431`), recoverable surface-chain execution (`mu/tools/executors/executor_dispatch.py:761-815`), and Phase A -> Phase B -> commit handoff while propagating `--bus-dir` (`mu/tools/executors/executor_dispatch.py:1262-1310`).
- `mu/tests/tools/test_executor_dispatch.py` already contains explicit `parallel_pipeline_agent_teams` routing-record and phase-chain regression coverage for the dispatcher surface (`mu/tests/tools/test_executor_dispatch.py:6574-6615`, `mu/tests/tools/test_executor_dispatch.py:7192-7253`), making it the focused test home for the item 4 launcher/control changes.
- This file, `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`, is the governing Phase A packet for the wave. This rewrite fixes the packet-level blocking finding by replacing unnamed teammate launcher scope with an explicit file/directory list and bounded dispatcher entrypoint.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `parallel-pipeline-agent-teams`
- Active packet: `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7296b7bf4ed838cbc7a9b2b5253d6cd3a95b2c4c6a566b601addab2a2d0e796a`
- Indicator artifact: `reports/l4_wave_indicators/parallel-pipeline-agent-teams.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T15-54-56p00-00_66d35b3b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bus_namespacing.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T15-54-56p00-00_66d35b3b.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/parallel-pipeline-agent-teams.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-30T15-54-56p00-00_66d35b3b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bus_namespacing.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/observability/pipeline_dashboard_web.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `mu/tools/observability/pipeline_monitor_identity.py`
  - `reports/control_plane/parallel_pipeline_agent_teams_2026-04-30.md`
  - `reports/deferred/non_blocking/parallel-pipeline-agent-teams_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parallel-pipeline-agent-teams.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->