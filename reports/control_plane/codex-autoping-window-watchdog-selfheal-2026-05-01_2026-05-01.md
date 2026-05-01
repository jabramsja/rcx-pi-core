# Codex-Autoping-Window-Watchdog-Selfheal-2026-05-01

Date: 2026-05-01
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: codex-autoping-window-watchdog-selfheal-2026-05-01
Parent tracker reference: [PIPELINE-RECOVERY] is CLOSED and is reference-only for this packet.
Wave ID: codex-autoping-window-watchdog-selfheal-2026-05-01
Phase-A-Lock: LOCKED
Proof Class: L4_ENABLER
Lane: control-surface (Codex autoping window/watchdog liveness and tracker truth)
FOUNDER_OVERRIDE:codex-autoping-window-watchdog-selfheal-2026-05-01

Purpose: Create and lock a bounded Phase A packet for the
`codex-autoping-window-watchdog-selfheal-2026-05-01` wave. The immediate
control-surface problem is that an AUTO-PING tmux window can remain visible
while the Codex autoping watcher is dead and its durable state is stale.

## Scope

This rewrite scope is limited to this governing packet:

- `reports/control_plane/codex-autoping-window-watchdog-selfheal-2026-05-01_2026-05-01.md`

The downstream implementation wave is limited to these files/directories unless
Phase A review proves a narrower or split packet is required:

- `tools/session/codex_autoping_window.sh` - verify and, if needed, make the
  AUTO-PING window wrapper mechanically supervise/restart the watcher process.
- `tools/session/codex_autoping_watch.py` - touch only if required to preserve
  diagnostic-only watcher state semantics while the wrapper self-heals.
- `mu/tools/session/` - mirror any duplicated `tools/session` change only if
  the current repo convention requires a duplicate session-tool surface.
- Existing focused session/autoping regression test locations under `tests/`
  or `mu/tests/`; do not create broad integration coverage when a hermetic
  wrapper-level test can prove the restart contract.
- `TASKS.md` - bounded tracker cleanup only after current code truth is checked
  for the stale PR #851 / NEXT-CODEX-POST-REDTEAM claims named in this packet.

## Work Items

1. Treat `[PIPELINE-RECOVERY]` as a closed parent reference, not an open task
   authorization. This packet is the new bounded recovery-hardening wave
   required by `TASKS.md`.
2. Verify the cited autoping root-cause candidate before implementation:
   `tools/session/codex_autoping_window.sh` starts
   `codex_autoping_watch.py` once near the cited startup block and then only
   renders status in its loop, allowing the tmux window to survive after the
   watcher exits.
3. If the candidate is still true, update the window wrapper so it detects a
   missing/exited watcher, restarts it mechanically, and keeps the pane and
   durable autoping state current without requiring startup, manual preflight,
   or `founder_session_guard docs --run` to recover stale autoping.
4. Preserve diagnostic-only semantics for the autoping path. The watcher or
   wake path must not edit repo files, run git, run tests, launch broad
   preflight, apply structural fixes, or launch/relaunch executor processes.
5. Mirror the wrapper fix into `mu/tools/session/` only if a duplicate session
   tool exists there and repo convention requires the mirror. Do not create a
   new mirror path solely for this wave.
6. Add focused regression coverage proving the wrapper restarts a dead watcher
   and stale autoping can recover without startup/manual preflight. Prefer
   hermetic process or fixture tests over live tmux/operator-pipeline mutation.
7. After the autoping plan is reviewed, perform the bounded `TASKS.md`
   code-truth cleanup named by the supervisor request: update stale
   NEXT-CODEX-POST-REDTEAM claims after PR #851 only where current code evidence
   proves the rcx_engine_state / rcx_engine_scheduler seed, test, or parity
   status. Remove already-landed items from pending work and acceptance
   criteria instead of re-listing them as unresolved.

## Constraints

- Do not use the closed `[PIPELINE-RECOVERY]` parent lane as live
  authorization. It is historical context only.
- Do not widen this packet into general recovery-gate, dispatcher, runtime,
  seed, substrate, or scheduler implementation work.
- Do not touch runtime/seed/substrate semantics except documentation truth for
  already-landed seed work that current code evidence proves.
- Do not rely on manual startup, `codex-rcx-preflight`, or
  `founder_session_guard docs --run` as the autoping recovery mechanism.
- Do not let the autoping watcher or headless wake path run shell commands,
  git commands, broad preflight, docs consistency, pytest suites, repo edits,
  structural fixes, or executor restarts.
- Do not create new report packets or write outside this packet during this
  Phase A rewrite.
- Do not perform broad repo investigation while drafting this first real plan.
  The initial grounding is limited to this governing packet, the reviewer
  findings, and the exact `[PIPELINE-RECOVERY]` lines in `TASKS.md`.
- Treat `TASKS.md` as authorization for a new bounded wave, not as proof that
  every listed downstream work item is still unlanded. Current code truth wins
  when later implementation evidence conflicts with stale wording.

## Stop Conditions

- Stop and revise the packet if current code shows the watcher is already
  mechanically supervised/restarted by the wrapper.
- Stop and split the wave if the fix requires runtime, seed, substrate, or
  scheduler semantic changes rather than control-surface session tooling.
- Stop and narrow the test plan if proving restart behavior would require
  mutating a live operator tmux session, live bridge state, or live `.agent_bus`
  state instead of a hermetic fixture.
- Stop rather than creating `mu/tools/session/` files if no duplicate session
  tool exists or repo convention does not require a mirror.
- Stop and split tracker cleanup if PR #851 truth reconciliation requires a
  broad docs audit or unrelated tracker rewrite.
- Stop any commit or automation path that cannot derive the same-wave override
  from this packet's `FOUNDER_OVERRIDE` token.

## Acceptance Criteria

- This Phase A packet contains explicit scope, work items, constraints, stop
  conditions, acceptance criteria, and grounding/authorization sections.
- The packet identifies `[PIPELINE-RECOVERY]` as CLOSED reference-only context
  and carries `FOUNDER_OVERRIDE:codex-autoping-window-watchdog-selfheal-2026-05-01`
  for same-wave commit automation.
- The implementation packet or closeout must show the wrapper restarts a dead
  autoping watcher while the AUTO-PING pane remains alive.
- Autoping state and pane visibility must become current through wrapper
  self-heal, not through manual startup/preflight.
- Diagnostic-only semantics must remain intact: no repo edits, git, broad
  shell/preflight/test execution, structural fixes, or executor launch/relaunch
  from the autoping watcher or wake path.
- Focused regression tests must prove the dead-watcher restart path and the
  no-manual-preflight recovery path. The implementation closeout must include
  the exact validation commands and results.
- Any duplicated `tools/session` implementation must be mirrored only when the
  duplicate exists and repo convention requires it; otherwise the closeout must
  state why no mirror was changed.
- `TASKS.md` cleanup, if performed in the downstream wave, must be grounded in
  current code evidence and must not leave already-landed work listed as
  pending or unresolved.

## Dispatcher Chain Repair Addendum

Phase A converged this packet in bridge round 2, then the dispatcher failed
before Phase B with:

`validate_inputs fatal: Plan task_id codex-autoping-window-watchdog-selfheal-2026-05-01 does not match routing task_id [PIPELINE-RECOVERY]`

The root cause is in the Phase A -> Phase B chain, not in the packet: the
locked packet correctly uses this bounded same-wave task id while keeping
`[PIPELINE-RECOVERY]` as closed parent reference only. `phase_b_executor.py`
already has a guarded same-wave exception for this exact parent-to-wave
transition, but `executor_dispatch.py` rebuilt `next_candidates` with only
`tracked_packet`, dropping the `bounded: true` and `candidate` fields the
exception requires. This addendum authorizes the narrow dispatcher repair and
regression test needed to resume this already-reviewed packet through Phase B.

Additional in-scope files for this dispatcher-prerequisite repair:

- `mu/tools/executors/executor_dispatch.py`
- `mu/tests/tools/test_executor_dispatch.py`

No Phase B implementation work is authorized in those files beyond preserving
the complete same-wave tracked candidate tuple during the Phase A -> Phase B
chain.

## Grounding / Authorization

- Governing packet: this file,
  `reports/control_plane/codex-autoping-window-watchdog-selfheal-2026-05-01_2026-05-01.md`.
- TASKS grounding: `TASKS.md` lines 344-356 mark `[PIPELINE-RECOVERY]` CLOSED
  and state that future recovery hardening must be authorized as new bounded
  waves rather than implied by that landed parent lane.
- Authorization: this packet is the new bounded control-surface L4_ENABLER wave
  for the autoping window/watchdog self-heal.
- Same-wave override token:
  `FOUNDER_OVERRIDE:codex-autoping-window-watchdog-selfheal-2026-05-01`.
- Direct supervisor evidence to verify in Phase B: pane 4 before startup showed
  autoping state updated at 23:47:53, 11h48m old, with status
  `fresh_exec_ping_dispatched`; `founder_session_guard docs --run` restarted
  autoping and the pane became fresh; the cited root-cause candidate is that
  `tools/session/codex_autoping_window.sh` starts `codex_autoping_watch.py`
  once and then only renders status in the loop.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-autoping-window-watchdog-selfheal-2026-05-01`
- Active packet: `reports/control_plane/codex-autoping-window-watchdog-selfheal-2026-05-01_2026-05-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9b92de4654b2e58c8f14169ea74333f36d6c992c19d711f059d3fb9fab2c7d25`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-window-watchdog-selfheal-2026-05-01.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-05-01T17-21-52p00-00_5e766283.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_codex_autoping_watch.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/codex-autoping-window-watchdog-selfheal-2026-05-01_2026-05-01.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-05-01T17-21-52p00-00_5e766283.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/codex-autoping-window-watchdog-selfheal-2026-05-01.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-05-01T17-21-52p00-00_5e766283.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/session/codex_autoping_window.sh`
  - `reports/control_plane/codex-autoping-window-watchdog-selfheal-2026-05-01_2026-05-01.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/codex-autoping-window-watchdog-selfheal-2026-05-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
