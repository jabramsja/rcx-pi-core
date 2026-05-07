# Shared Pipeline Agent Pager

Date: 2026-04-16
Status: Phase B (implementation-complete, bridge-converged)
Task: [PIPELINE-AGENT-PAGER]
Wave ID: pipeline-agent-pager-2026-04-16
Phase-A-Lock: LOCKED
Wave class: MAINTENANCE
Target gate: G8
Governing packet: `reports/control_plane/pipeline_agent_pager_2026-04-16.md`
Depends on: merge of the active [PIPELINE-RECOVERY] wave tracked at `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`
## Grounding / Authorization

- `TASKS.md:177-183` explicitly authorizes `[PIPELINE-AGENT-PAGER]` as a
  founder-directed queued post-merge follow-up.
- The same `TASKS.md:177-183` block makes this the first queued follow-up after
  the active `[PIPELINE-RECOVERY]` wave lands, forbids implementation inside
  the live in-flight recovery worktree, and names this packet as the tracked
  plan artifact.
- The same `TASKS.md:177-183` block also authorizes the 2026-04-17 fold-in:
  catch hybrid targeted-validator `TimeoutExpired` inside recovery Tier 3, and
  tolerate prior `.scratch/recovery_agent_<token>.txt` prompt artifacts without
  relaxing the fail-closed audit for unrelated descendants.
- The same `TASKS.md:177-183` block also authorizes a narrow 2026-04-17
  docs-governance adjacency if this packet's one new pager test and one new
  pager tool exceed the repo growth-cap gate: update
  `mu/tests/docs/test_growth_caps.py` only far enough to acknowledge those two
  wave-owned additions before rerunning the blocked commit path.
- Founder explicitly authorized in-session on 2026-04-17 the bounded
  governance override now recorded in `TASKS.md:178-184`: use
  `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` to bypass the
  non-structural adjacency and rolling-window caps for this MAINTENANCE
  landing. The justification is limited to this pager slice: authoritative
  transition paging is required before unattended recovery and later structural
  follow-up waves can be observed mechanically.
- Governing packet authority for Phase A is this file. The locked sections below
  define the admitted scope, work items, constraints, stop conditions, and
  acceptance contract for the wave.
- This rewrite is grounded only in this governing packet, the bridge-review
  blocking findings, `TASKS.md:177-183`, and the timeout surface already cited
  in `mu/tools/executors/executor_config.json:14-35`. It does not claim a fresh
  audit of downstream implementation files beyond that evidence set.

## Purpose

Give the pipeline a mechanically reliable way to wake Codex and/or Claude Code
when important control-plane transitions happen, without continuous manual
watching and without introducing passive always-on model observers.

The first slice remains intentionally narrow:

1. authoritative transition events are emitted at the executor paths where the
   transition actually occurs
2. one neutral repo-local pager consumes those events and applies configured
   routing
3. Codex and Claude Code are adapter targets, not separate watcher systems
4. rollout stays default-off until manually enabled after the current
   `[PIPELINE-RECOVERY]` wave lands

## Canonical rollout order

1. ~~Merge the active `[PIPELINE-RECOVERY]` wave and route the first queued
   bounded follow-up~~ **(done — merged PR `#778` produced the post-merge
   package that routed `[PIPELINE-AGENT-PAGER]`)**.
2. ~~Converge Phase A and lock this pager packet~~ **(done — Phase A review job
   `phase-a-r2-822df6a2` returned `GO`, and this packet header is now
   `Phase-A-Lock: LOCKED`)**.
3. Current routable step: implement Phase B on this locked packet inside the
   admitted scope. That includes authoritative transition emission, the shared
   repo-local pager, Codex / Claude adapters, default-off executor config
   budgets, and the two bounded `recovery_gate.py` follow-through items already
   authorized in `TASKS.md`.
4. Standing invariant: rollout remains default-off until explicit config
   enablement after this wave lands.
5. After Phase B converges, route the resulting commit-capable handoff through
   the normal pre-commit receipt + commit-executor path. Do not bypass the
   canonical routing chain with ad hoc manual staging.

## Scope

This packet is limited to the control-plane files required to emit, route, and
prove the shared pager:

1. `mu/tools/executors/executor_common.py`
2. `mu/tools/executors/phase_b_executor.py`
3. `mu/tools/executors/recovery_gate.py`
4. `mu/tools/executors/commit_executor.py`
5. `mu/tools/executors/executor_config.json`
6. `mu/tools/observability/pipeline_agent_pager.py`
7. `mu/tests/tools/test_phase_b_executor.py`
8. `mu/tests/tools/test_recovery_gate.py`
9. `mu/tests/tools/test_commit_executor_receipt.py`
10. `mu/tests/tools/test_pipeline_agent_pager.py`
11. `mu/tests/docs/test_growth_caps.py`
12. `TASKS.md`
13. `reports/control_plane/pipeline_agent_pager_2026-04-16.md`

## Architecture Decision (Locked For Phase A)

This wave defines the pager as:

- executor-owned transition emission from authoritative code paths
- one neutral pager queue and dispatcher
- adapter routing to `codex`, `claude`, `both`, or `notify-only`
- local-machine only for the first slice
- default-off behind executor config
- persisted delivery state with explicit per-target retry semantics

The delivery, identity, and acknowledgement contract is locked as follows:

1. `event_id` identifies the logical transition event and must be derived as
   `sha256` over canonical JSON built only from immutable authoritative
   transition facts.
2. The required Phase A identity tuple is `task_id`, `wave_id`, `event_type`,
   `plan_path` when applicable, `phase`, `state`, and a stable
   executor-supplied `transition_key`.
3. `transition_key` must remain stable across retry, overlapping invocations,
   and crash replay, and must come from authoritative transition facts already
   known to the emitting executor, such as attempt lineage, a receipt path, or
   an equivalent executor-owned transition discriminator.
4. `timestamp`, route, delivery state, retry counters, process ids, and random
   UUIDs are not identity inputs.
5. Delivery dedupe is evaluated per requested target, not as a single global
   delivered bit.
6. Pager state advances for a target only after that target's adapter returns
   the explicit acknowledgement defined in Adapter Contract.
7. A failed, interrupted, timed-out, or otherwise indeterminate adapter attempt
   must leave that target retryable. It may not consume the dedupe key for that
   target.
8. Route `both` must fan out independently. If one adapter succeeds and the
   other fails, persisted state must preserve the successful target and leave
   the failed target pending for retry. The implementation may not mark the
   whole event complete or silently drop the failed wakeup.
9. Route `notify-only` is a distinct terminal path. It may record completion
   after the notify-only action is durably written, but it must not be
   conflated with successful agent delivery to `codex` or `claude`.

This wave does not define the pager as:

- tmux-pane parsing
- shell-log scraping as the source of truth
- a second parallel watcher stack owned by Claude Code
- a generic always-on model session that watches the pipeline
- a remote Codex service exposed beyond loopback
- automatic activation inside the currently running `[PIPELINE-RECOVERY]` wave

## Initial Event Contract

The event envelope should be normalized and append-only. The exact file path is
implementation-owned, but the first slice is expected to write deterministic
JSON records under `.agent_bus/observability/` with a small pager state file
for routing and delivery state. `event_id` must be reproducible from the same
canonical identity tuple on first append, retry, overlapping invocation, and
crash replay; Phase A may not generate a fresh UUID or nonce per append.

Each event must include enough context to wake an agent without re-scraping the
repo:

- `event_id`
- `event_type`
- `wave_id`
- `task_id`
- `plan_path` when applicable
- `phase`
- `state`
- `transition_key`
- `reason` or `summary`
- relevant artifact paths already known to the executor
- timestamp

The `event_id` contract is locked as follows:

1. `event_id` must be derived as `sha256` over canonical JSON with stable key
   ordering for the Phase A identity tuple:
   `task_id`, `wave_id`, `event_type`, `plan_path` when applicable, `phase`,
   `state`, and `transition_key`.
2. `transition_key` is the stable executor-owned discriminator that
   distinguishes otherwise similar logical transitions within the same wave. It
   must come from authoritative transition facts already known to the emitting
   path, such as a bridge job id, recovery invocation lineage, receipt path, or
   commit handoff path.
3. Retrying, replaying, or re-dispatching the same authoritative transition
   must reuse the same `event_id`.
4. A distinct authoritative transition must change at least one identity input
   in that tuple, so two different transitions cannot silently collide on the
   same dedupe key.
5. `timestamp`, retry counters, route, delivery state, process ids, and fresh
   UUIDs may appear in payload metadata, but they may not be the primary
   `event_id` or the thing dedupe depends on.

The first admitted user-facing event types are:

1. `phase_b_reviewer_started`
2. `recovery_started`
3. `recovery_state_changed`
4. `recovery_failed`
5. `pipeline_hard_fail`
6. `commit_ready`

If implementation needs more internal event labels for normalization, they may
exist internally, but the six user-facing outcomes above are the Phase A
contract that must be emitted, routed, and tested.

## Trigger / Durability Contract

The first-slice trigger path is locked as follows:

1. The same authoritative executor path that durably records a transition event
   must also trigger pager handling automatically before it returns success for
   that transition. The trigger may be an in-process call or a bounded local
   child-process invocation of the pager entrypoint, but it may not be a manual
   operator step.
2. Correctness may not depend on cron, tmux watching, a detached daemon, or a
   second model session polling for new events. The emit-to-dispatch path must
   be mechanically connected inside the admitted executor / observability
   surfaces.
3. The first slice must define one explicit single-dispatcher ownership model
   per repo worktree. Concurrent writers may not race unsafely on the append
   log or delivery-state file.
4. Event append and delivery-state mutation must be crash-safe. The exact
   primitive is implementation-owned, but the packet requires an atomic or
   equivalently fail-closed write path plus restart replay rules for any
   durable event that was appended before target success was fully recorded.
5. If a process dies after durable event append but before all requested target
   outcomes are durably recorded, the pending target set must remain replayable
   on the next bounded pager invocation. The design may not silently lose the
   wakeup or double-consume it as already delivered.
6. The admitted `mu/tools/executors/executor_config.json` surface must define
   explicit pager budgets. At minimum this slice must add:
   `timeouts.pipeline_agent_pager_trigger` for the synchronous emit-to-dispatch
   path, `timeouts.pipeline_agent_pager_codex_ack` for one Codex accepted-turn
   window, and `timeouts.pipeline_agent_pager_claude_ack` for one Claude
   non-interactive submission / ACK window.
7. Budget exhaustion must fail closed: the executor may record the event as
   pending / dispatch-failed and leave it replayable, but it may not hang
   indefinitely or mark the target delivered without a qualifying ACK.
8. If the inline trigger budget expires after durable event append, the
   authoritative transition may return success only after the still-pending
   targets are durably recorded as pending / replayable. If that pending-state
   write fails, the transition may not return success.

## Adapter Contract

Phase A adapter success means the target control surface accepted the wakeup
request into its own execution context. It does not mean the downstream agent
already completed the follow-on task.

### Codex

The Codex adapter must use the local App Server interface, not ad-hoc shell
re-entry into a long interactive session.

First-slice constraints:

1. local loopback only
2. persistent thread id stored in repo-local pager state
3. each dispatched event resumes or starts that thread and sends a bounded turn
   under `timeouts.pipeline_agent_pager_codex_ack`
4. no remote listener exposure and no non-loopback auth setup in this slice
5. pager delivery for `codex` counts as success only after the App Server
   accepts the wakeup turn for the target thread and returns a concrete thread /
   turn handle or equivalent accepted-turn response. TCP connect, thread lookup,
   or process spawn alone is not a delivery ACK.
6. a timeout, transport error, or missing / ambiguous accepted-turn response is
   indeterminate and must leave the `codex` target pending for retry

### Claude Code

The Claude adapter must use the existing CLI surface instead of requiring a
Claude-specific watcher stack.

First-slice constraints:

1. use `claude -p` for fresh event tasks or `claude -c -p` if continuity is
   desired
2. keep prompts bounded to the event context and authoritative artifact paths
3. run the non-interactive submission under
   `timeouts.pipeline_agent_pager_claude_ack`
4. treat token or auth setup as operator configuration, not pipeline logic
5. pager delivery for `claude` counts as success only after the non-interactive
   CLI invocation receives the prompt payload and exits zero. Process spawn
   without a zero-exit completion is not a delivery ACK.
6. a non-zero exit, timeout, or interrupted child process is indeterminate and
   must leave the `claude` target pending for retry

## Work Items

### A. Add authoritative transition emission

Emit normalized events directly from the executor paths that already know the
transition is real:

- Phase B when reviewer starts after implementer completion
- recovery when it begins
- recovery when its state changes or becomes terminal
- commit path when a commit-ready receipt is emitted
- pipeline hard-fail paths already inside admitted executor scope
- derive `event_id` from the locked canonical identity tuple plus stable
  `transition_key`, not from per-append UUIDs or process-local state

### B. Add the shared pager queue and dispatcher

Implement one repo-local pager entrypoint that:

- reads the normalized event stream
- is triggered automatically by the same authoritative executor path that
  appends the event; no manual pager run is allowed for correctness
- applies target routing from config
- consumes explicit pager budgets from `executor_config.json` for the trigger
  path plus separate Codex and Claude acknowledgement windows
- runs under one explicit single-dispatcher ownership model per repo worktree
- persists delivery state with per-target dedupe semantics
- writes event-log and delivery-state updates through an atomic or equivalently
  fail-closed path
- retries only the targets that have not yet recorded success
- keeps `notify-only` distinct from agent-delivered success
- replays durable pending events after restart or interrupted dispatch instead
  of silently dropping them
- records timeout / ACK-failure attempts as pending or dispatch-failed without
  consuming the target's dedupe state

### C. Add the Codex App Server adapter

Implement a bounded local adapter that:

- connects to a loopback App Server endpoint
- resumes or creates the pager thread
- sends a bounded turn containing the event plus authoritative artifact paths
- records `codex` success only after the accepted-turn acknowledgement required
  by Adapter Contract

### D. Add the Claude CLI adapter

Implement a bounded local adapter that:

- launches Claude Code non-interactively
- passes the same normalized event payload
- records `claude` success only after the zero-exit acknowledgement required by
  Adapter Contract
- does not require a second watcher stack

### E. Keep rollout default-off

Land the first slice behind executor config so merge does not immediately change
behavior for active pipeline runs. The same config change must add the explicit
default-off enable switch, route selection, inline trigger timeout, and
per-target acknowledgement budgets required by this packet.

### F. Land the bounded recovery fold-in already authorized in `TASKS.md`

Use the already-admitted `recovery_gate.py` and `test_recovery_gate.py` scope
to:

- convert hybrid targeted-validator timeouts into structured failed validation
  results that recovery can record and handle without crashing
- admit prior recovery prompt artifacts for the same fail-closed `.scratch`
  contract without allowing unrelated descendants through the audit

### G. Record the narrow growth-cap exception only if the wave needs it

If this packet's one new pager test and one new pager tool push the repo over
the current docs growth-cap gate, update `mu/tests/docs/test_growth_caps.py`
only far enough to acknowledge those two wave-owned additions.

## Constraints

1. Do not implement this packet inside the live in-flight `[PIPELINE-RECOVERY]`
   worktree.
2. Do not couple agent wakeups to tmux panes, shell-log scraping, or passive
   model watch loops.
3. Do not expose Codex App Server beyond loopback in the first slice.
4. Do not require Claude Code to grow a separate watcher infrastructure.
5. Keep the wave inside the control-surface files listed in Scope; no
   runtime/substrate/seed files are admitted here.
6. Do not collapse delivery state into one global success bit that can mark a
   `both` route complete after only partial success.
7. Do not make correctness depend on manual pager invocation, cron, tmux
   watching, or a detached always-on daemon.
8. Do not rely on multi-writer best-effort event/state mutation without an
   explicit single-dispatcher or equivalent fail-closed concurrency contract.
9. Do not derive `event_id` from timestamps, retry counters, process ids, or
   random UUIDs.
10. Do not mark delivery successful on process spawn, socket reachability, HTTP
    transport acceptance, stdin write success, or any other transport-only
    signal that does not satisfy the Adapter Contract acknowledgement.
11. Do not let inline pager handling wait without the explicit config-backed
    trigger and per-target acknowledgement budgets locked above.
12. Do not widen docs-governance edits beyond `mu/tests/docs/test_growth_caps.py`.

## Stop Conditions

1. Stop if the active `[PIPELINE-RECOVERY]` wave has not yet merged or if work
   would need to occur inside the live in-flight recovery worktree.
2. Stop and spin a separate packet if authoritative event emission or pager
   routing requires files outside the Scope section above.
3. Stop and spin a separate packet if implementation would require dispatcher,
   Phase A, dashboard, tmux-monitor, or remote-service surfaces not already
   admitted here.
4. Stop if correct delivery would require tmux scraping, shell-log scraping, a
   passive watcher, or non-loopback Codex exposure.
5. Stop and split the work if the folded recovery items require files beyond
   `mu/tools/executors/recovery_gate.py` and
   `mu/tests/tools/test_recovery_gate.py`.
6. Stop and spin a separate packet if automatic emit-to-dispatch triggering
   requires a new scheduler, daemon supervisor, or service manager surface not
   already inside the admitted files.
7. Stop and split the work if correctness requires unconstrained multi-writer
   queue/state mutation that cannot be bounded by a single-dispatcher or
   equivalently fail-closed atomicity model inside the existing scope.
8. Stop and spin a separate packet if correct pager behavior requires budget or
   timeout surfaces outside the admitted `executor_config.json` file.
9. Stop and spin a separate packet if the admitted Codex App Server or Claude
   CLI surface cannot provide the explicit acceptance signal required by
   Adapter Contract.

## Acceptance Criteria

1. A real executor-side transition appends exactly one normalized event record
   for that transition with the required event-envelope fields, including a
   stable `transition_key`, and the same authoritative control path
   automatically triggers pager handling without a manual operator step.
2. Pager routing can target `codex`, `claude`, `both`, or `notify-only`.
3. `event_id` is computed as `sha256` over the locked canonical identity tuple
   and remains stable across retry, replay, overlapping invocation, and crash
   recovery of the same logical transition.
4. Pager dedupe is enforced per requested target, so the same `event_id` is not
   redelivered to a target after that target has recorded success.
5. Pager delivery state advances only after the explicit target acknowledgement
   defined in Adapter Contract.
6. Failed, interrupted, timed-out, or otherwise indeterminate adapter attempts
   remain retryable and do not consume the dedupe state for that target.
7. For route `both`, one adapter succeeding and the other failing leaves only
   the failed target pending for retry; the implementation may not mark the
   whole event complete or silently drop the failed wakeup.
8. `notify-only` remains a distinct terminal route and is not treated as agent
   delivery to `codex` or `claude`.
9. Codex adapter uses App Server thread control, not tmux attachment or chat
   scraping, and marks success only on the accepted-turn acknowledgement bound
   to the intended thread.
10. Claude adapter uses existing CLI non-interactive execution and marks
    success only on zero-exit completion of the prompt-submission path, not on
    process spawn or stdin acceptance.
11. `executor_config.json` defines explicit pager budgets for the synchronous
    trigger path, the Codex accepted-turn window, and the Claude
    non-interactive submission / ACK window.
12. If the inline trigger budget expires after durable event append, the
    still-pending targets are durably recorded as pending / replayable before
    the authoritative transition returns success; if that state write fails, the
    transition does not return success.
13. Rollout is disabled by default and requires explicit config enablement.
14. Pager event-log and delivery-state writes run under an explicit
    single-dispatcher or equivalently fail-closed atomicity contract, with
    tests that prove no lost or duplicate wakeups across overlapping
    invocations.
15. If a process dies after durable event append but before all requested
    target outcomes are durably recorded, the next bounded pager invocation
    replays the still-pending targets instead of losing or double-consuming the
    wakeup.
16. Recovery Tier 3 converts hybrid targeted-validator timeouts into
    structured failed validation results instead of letting `TimeoutExpired`
    escape.
17. Recovery scratch auditing admits prior
    `.scratch/recovery_agent_<token>.txt` artifacts for the same attempt
    lineage while still rejecting unrelated descendants fail-closed.
18. Tests prove the admitted transition set, the automatic trigger path, the
    event-id identity contract, the explicit budget / failure policy, the
    adapter-ACK contract, and the dedupe / partial-failure / restart semantics
    above without depending on live tmux panes. Some timeout-budget regressions
    intentionally use bounded `time.sleep()` probes in
    `mu/tests/tools/test_pipeline_agent_pager.py`; they are not live-pane
    dependencies.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_pipeline_agent_pager.py`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged`
- `bash tools/checks/check_docs_consistency.sh`

## Exit Condition

This packet is ready to route only after the active
`hybrid_recovery_agent_2026-04-16` wave merges and pager work begins from a
clean post-merge worktree.
