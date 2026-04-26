# Pager Lifecycle Event Coverage

Date: 2026-04-23
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-AGENT-PAGER]
Wave ID: pager-lifecycle-event-coverage-2026-04-23
Phase-A-Lock: LOCKED
Wave class: L4_ENABLER
Target gate: G8

## Purpose

Close the next bounded `[PIPELINE-AGENT-PAGER]` sub-wave that is still open after
the first pager, route-flip, Codex App Server, and post-reentry notification
truth work: the pager must cover the pipeline lifecycle transitions the founder
keeps needing to observe without manual pane watching.

This packet also admits the newly reproduced commit-path governance
mechanization gap from PR #823: standalone/ad hoc commit waves can reach
supervisor Step 6 with an empty `founder_override_token` even when the active
control-surface lane already carries founder authorization. That belongs in the
same agent-pager/control-plane lane because it is part of making unattended
pipeline routing observable, bounded, and mechanically recoverable.

## Grounding / Authorization

- `TASKS.md` keeps `[PIPELINE-AGENT-PAGER]` in `IN PROGRESS` and names this file
  as the next bounded packet for lifecycle widening.
- `TASKS.md` also records the 2026-04-25/2026-04-26 mechanization follow-on:
  standalone `commit_executor` can regenerate tracker-note truth from the
  routing record and lose the manually staged `FOUNDER_OVERRIDE` before
  pre-push.
- `reports/control_plane/pager_route_flip_2026-04-18.md:121-130` explicitly
  defers Phase A transitions/convergence, Phase B implementer transitions, and
  broader failure paging to later `[PIPELINE-AGENT-PAGER]` sub-waves.
- `reports/control_plane/pager_route_flip_2026-04-18.md:392-438` repeats that
  those founder-named lifecycle pings remain residual deliverables after the
  route-flip wave.
- Current code truth: `mu/tools/observability/pipeline_agent_pager.py:60-70`
  admits only these event types: `phase_b_reviewer_started`,
  `phase_b_bridge_completed`, `phase_b_final_pytest_started`,
  `phase_b_final_pytest_passed`, `recovery_started`,
  `recovery_state_changed`, `recovery_failed`, `pipeline_hard_fail`, and
  `commit_ready`.
- Current emitter truth: current `dev` emits pager events from Phase B,
  recovery, and commit paths, but no Phase A lifecycle events and no
  pre-commit / commit fail-or-success lifecycle events are emitted.
- `TASKS.md:225` identifies `mu/tools/executors/recovery_gate.py` as an active
  pager emitter; recovery escalation/return/success lifecycle coverage therefore
  remains in this packet and admits the recovery executor instead of splitting
  recovery work out of scope.
- Founder-override root-cause evidence is code-local:
  `mu/tools/executors/commit_executor.py:350-364` extracts `FOUNDER_OVERRIDE`
  only from routing-record `tracker_note_text`, embedded handoff
  `tracker_note_text`, or tracked-packet text;
  `mu/tools/executors/commit_executor.py:936-955` appends an override only when
  `founder_override_token` is supplied; and
  `mu/tools/executors/commit_executor.py:3378-3390` defaults that builder input
  to `None`.

## Scope

Admitted files and directories:

1. `TASKS.md`
2. `reports/control_plane/pager_lifecycle_event_coverage_2026-04-23.md`
3. `mu/tools/observability/pipeline_agent_pager.py`
4. `mu/tools/executors/phase_a_executor.py`
5. `mu/tools/executors/phase_b_executor.py`
6. `mu/tools/executors/commit_executor.py`
7. `mu/tools/executors/recovery_gate.py`
8. `mu/tools/executors/executor_dispatch.py`
9. `mu/tools/agents/meta_bridge_supervisor.py`
10. `mu/tests/tools/test_pipeline_agent_pager.py`
11. `mu/tests/tools/test_phase_a_executor.py`
12. `mu/tests/tools/test_phase_b_executor.py`
13. `mu/tests/tools/test_recovery_gate.py`
14. `mu/tests/tools/test_executor_dispatch.py`
15. `mu/tests/tools/test_meta_bridge_supervisor.py`
16. `mu/tests/tools/test_commit_executor_receipt.py`
17. `mu/tests/docs/test_growth_caps.py`
18. `reports/deferred/non_blocking/pager-lifecycle-event-coverage-2026-04-23_bridge_nonblockers.md`
19. `reports/l4_wave_indicators/pager-lifecycle-event-coverage-2026-04-23.json`

## Work Items

1. Widen the pager lifecycle event contract with executor-owned event names for
   Phase A entered, Phase A reviewer/implementer transitions, Phase A GO /
   NO_GO / QUESTION outcomes, Phase B implementer transitions, Phase B final
   verdicts, pre-commit supervisor lifecycle, commit executor started/succeeded
   / failed/held outcomes, recovery escalation/return/success pages, and
   executor hard-failure coverage.
2. Add authoritative emitter call sites at the executor paths that own those
   transitions, including `mu/tools/executors/recovery_gate.py` for recovery
   escalation/return/success pages. Emit from durable transition facts already
   known to the executor; do not infer lifecycle state from tmux text, shell
   logs, or dashboard rendering.
3. Keep pager event identity deterministic: new events must continue using a
   stable `transition_key` derived from authoritative executor facts, and must
   preserve per-target retry semantics.
4. Extend pager tests so unsupported event types still fail closed while each
   newly admitted lifecycle event type is accepted, persisted, deduped, and
   routed according to the existing target contract.
5. Add executor tests proving each newly covered lifecycle surface emits or
   suppresses pager events at the correct boundary.
6. Mechanize the PR #823 founder-override recurrence before the next standalone
   / ad hoc commit wave: `build_commit_handoff` / routing-record preparation
   must either derive the standing pipeline-bug-fix override token for
   authorized control-surface L4_ENABLER waves, or fail closed before Step 6
   with a targeted message naming the missing token and expected source.
7. Update `TASKS.md` and this packet as the wave source of truth when the
   automated pipeline changes the implementation, validation, or commit-ready
   scope.

## Constraints

- Do not introduce a second passive watcher stack, cron poller, or tmux parser
  as the authority for lifecycle truth.
- Do not collapse Codex pager and Codex autoping into one channel. The pager is
  event-driven pipeline notification; autoping is diagnostic watchdog wakeup.
- Do not edit Claude-local surfaces for this wave unless Phase A produces an
  explicit blocking finding proving a pager adapter parity defect that cannot be
  fixed from repo-owned control-plane code.
- Do not widen runtime, substrate, Mu semantics, Stage0 semantics, or L4
  bootstrap authority.
- Do not auto-append `FOUNDER_OVERRIDE` tokens for arbitrary waves. Any derived
  override must be limited to authorized control-surface L4_ENABLER waves, or
  the path must fail closed with a specific missing-token diagnostic.

## Stop Conditions

1. Stop and split if lifecycle coverage requires per-worktree bus namespacing,
   independent tmux session naming, or dashboard port allocation. That belongs
   under `[PARALLEL-PIPELINE]`.
2. Stop and split if a new event cannot be emitted from authoritative executor
   state and would require scraping a pane or log to infer truth.
3. Stop and split if the founder-override fix requires weakening Gate 8,
   disabling L4 checks, or bypassing `enforce_l4_execution_contract.py`.
4. Stop and ask for founder direction if Phase A bridge review concludes the
   lifecycle widening and founder-override mechanization are too large for one
   same-lane packet.

## Acceptance Criteria

1. `ALLOWED_EVENT_TYPES` and tests cover the newly admitted lifecycle event
   types, and unsupported event types still fail closed.
2. Phase A emits start/progress/verdict pager events from Phase A executor state,
   including GO, NO_GO, and QUESTION/fail-closed outcomes.
3. Phase B emits implementer and final-verdict lifecycle events from Phase B
   executor state, not from bridge transcript scraping.
4. Pre-commit and commit paths emit started/succeeded/failed/held lifecycle
   events where those outcomes are decided.
5. `mu/tools/executors/recovery_gate.py` emits recovery escalation, return, and
   success lifecycle events without replacing the existing `recovery_started`,
   `recovery_state_changed`, `recovery_failed`, and `pipeline_hard_fail` events.
6. The founder-override recurrence has regression coverage proving authorized
   control-surface L4_ENABLER waves do not reach Step 6 with an empty override,
   and unauthorized waves fail closed before Step 6 with a targeted diagnostic.
7. `TASKS.md`, this packet, and any L4 indicator artifact agree on changed
   files, wave class, target gate, validation commands, and residual risks
   before commit.

## Phase B Implementation Update (2026-04-26)

- Pager event contract now admits the lifecycle event families named in this
  packet: Phase A entered/reviewer/implementer/verdict transitions, Phase B
  implementer/final-verdict transitions, pre-commit supervisor lifecycle,
  commit started/succeeded/failed/held outcomes, recovery escalation/return/
  success events, and dispatcher-owned executor hard-failure events.
- Emitters were added only at executor-owned decision points:
  `phase_a_executor.py`, `phase_b_executor.py`, `commit_executor.py`,
  `recovery_gate.py`, `executor_dispatch.py`, and
  `meta_bridge_supervisor.py`.
- Standalone L4 commit handoff preparation now derives
  `FOUNDER_OVERRIDE:<wave_id>` only for authorized control-surface
  L4_ENABLER routing records, and fails closed before supervisor Step 6 for
  unauthorized L4 standalone paths with a targeted missing-token diagnostic.
- Focused tests were added or extended across pager, Phase A, Phase B,
  recovery, dispatcher/commit-handoff, and meta-bridge supervisor surfaces.
- The staged L4 check requires a committed indicator artifact, so this packet
  now includes `reports/l4_wave_indicators/pager-lifecycle-event-coverage-2026-04-23.json`.

## Bridge Round 1 Remediation Update (2026-04-26)

- Standalone founder-override derivation no longer treats a
  `reports/control_plane/*` packet path as authorization by itself. Generic
  L4 routing records with control-plane packets now fail closed before
  supervisor Step 6 unless the record or packet proves control-surface
  pipeline authorization for the same wave.
- The `commit_executor.py` structured `run_meta_bridge_package()` Step 6 path
  now emits `pre_commit_supervisor_started` and
  `pre_commit_supervisor_completed` from the same package facts used by the
  supervisor, so it no longer depends on the CLI-only
  `meta_bridge_supervisor.py` main path for pre-commit lifecycle pages.
- `mu/tests/tools/test_executor_dispatch.py` now includes regressions for the
  generic control-plane packet denial and for structured pre-commit supervisor
  lifecycle emission.

## Bridge Round 2 Remediation Update (2026-04-26)

- Standalone L4 founder-override derivation no longer trusts caller-controlled
  `task_id`, `lane`, or `supervisor_lane` routing metadata as authorization.
  Derived `FOUNDER_OVERRIDE:<wave_id>` is now limited to explicit token sources
  or same-wave `reports/control_plane/*` packet text that declares
  control-surface / standing pipeline-bug-fix authorization.
- Phase B re-entry implementer pager transition keys now include the
  executor-owned invocation source: `supervisor` for the initial re-entry
  implementer and the triggering bridge job id for same-round
  REQUEST_CHANGES/NO_GO reinvocations. Distinct same-round implementer starts
  therefore produce distinct pager event identities instead of being deduped.
- `mu/tests/tools/test_executor_dispatch.py` now covers the task-id-only and
  lane-only unauthorized L4 standalone paths. `mu/tests/tools/test_phase_b_executor.py`
  now proves same-round re-entry implementer-start transition keys are unique.

## Bridge Round 3 Remediation Update (2026-04-26)

- Standalone L4 founder-override derivation now requires same-wave
  control-surface packet authorization to come from a Git-indexed
  tracked/staged packet. Untracked or unstaged control-plane packet text can no
  longer derive `FOUNDER_OVERRIDE:<wave_id>` for standalone handoff generation.
- The CLI pre-commit supervisor now writes the receipt before emitting
  `pre_commit_supervisor_completed=success`; if receipt writing fails and voids
  `COMMIT_GO`, it emits a completed error lifecycle event instead.
- Phase B final pytest failures now emit both `phase_b_final_verdict` and
  `pipeline_hard_fail` lifecycle pages on the initial and re-entry pytest-gate
  exits before returning the existing error result.
- Focused regressions were added to `mu/tests/tools/test_executor_dispatch.py`,
  `mu/tests/tools/test_meta_bridge_supervisor.py`, and
  `mu/tests/tools/test_phase_b_executor.py` for the three Bridge Round 3
  blockers.

## Bridge Round 4 Remediation Update (2026-04-26)

- Standalone L4 founder-override derivation now reads authorizing
  control-plane packet content from the Git index blob, not from the mutable
  working tree. A tracked packet whose unstaged working-tree text adds
  authorization can no longer derive `FOUNDER_OVERRIDE:<wave_id>`.
- Same-wave control-surface authorization now requires exact parsed `Wave ID:`
  metadata equality after normalization. A packet for `unrelated-test-wave`
  no longer authorizes standalone wave `test` through substring matching.
- `mu/tests/tools/test_executor_dispatch.py` now includes regressions for the
  unstaged packet authorization and substring wave-id authorization blockers
  from Bridge Round 4.

## Closeout Receipt-Chain Repair Update (2026-04-26)

- Gate 10 closeout attestation failed on
  `validation: receipt_chain: phase_b_to_commit_executor` after Bridge Round 5
  because `mu/tests/tools/test_commit_executor_receipt.py` still assumed the
  old single commit-ready pager event order and pre-mechanization standalone L4
  founder-override behavior.
- `mu/tests/tools/test_commit_executor_receipt.py` now treats
  `pre_commit_supervisor_started` as the expected first lifecycle event and
  asserts against the later `commit_ready` event explicitly.
- The receipt-chain tests now seed authorizing packet text through Git-indexed
  content or explicit founder-override builder inputs, matching the fail-closed
  standalone L4 authority model implemented in this wave.

## Implementation-Agent Bridge Round 1 NO_GO Remediation Update (2026-04-26)

- `commit_executor.py` now applies the review-mode guard before emitting
  `commit_started` or any commit outcome lifecycle page, so review-mode probes
  cannot create live pager events before the executor fails closed.
- `meta_bridge_supervisor.py` now applies the same review-mode guard before the
  CLI pre-commit lifecycle start/completion pages. Its receipt writer also
  writes the per-invocation receipt before the canonical hook receipt, so a
  failed exact receipt write cannot leave a canonical `COMMIT_GO` receipt after
  the decision is voided.
- The Phase B pytest-fix implementer path now emits
  `phase_b_implementer_started` and `phase_b_implementer_completed` from the
  same executor-owned bridge-round facts as the surrounding bridge-fix
  implementer path.
- Focused regressions were added to
  `mu/tests/tools/test_commit_executor_receipt.py`,
  `mu/tests/tools/test_meta_bridge_supervisor.py`, and
  `mu/tests/tools/test_phase_b_executor.py`.

## Implementation-Agent Bridge Round 2 NO_GO Remediation Update (2026-04-26)

- `build_commit_handoff()` now resolves an explicit
  `FOUNDER_OVERRIDE:<token>` already present in string `tracker_note_text`
  before applying the standalone L4 fail-closed Step 6 guard.
- The builder still fails closed when standalone L4 handoffs lack an explicit
  token source or same-wave authorized control-surface packet text; this repair
  only restores the explicit tracker-note source named in the missing-token
  diagnostic.
- `mu/tests/tools/test_executor_dispatch.py` now covers the standalone L4
  explicit-tracker-note override path.

## Pre-Commit Recovery Update (2026-04-26)

- Pre-commit doc governance failed at
  `mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap`
  because the test count was 307 and the configured limit was 306. The packet
  now includes `mu/tests/docs/test_growth_caps.py` and records the founder-signed
  +1 test-file cap for `mu/tests/tools/test_phase_a_executor.py`.
- `mu/tools/executors/recovery_gate.py` now treats a confirmed `index.lock`
  failure whose lock file has already disappeared by recovery time as a
  transient self-cleared lock and grants one retry without deleting `.git`
  internals. Existing `.git/index.lock` files still fail closed.
- The commit handoff uses the tracked path `mu/tests/docs/test_growth_caps.py`.
  The symlink path `tests/docs/test_growth_caps.py` was rejected by `git add`
  with `pathspec ... is beyond a symbolic link`.
- `recovery_gate.py` now recognizes embedded JSON `stage_files` / `git add`
  errors as staging failures before generic test-failure detection, so paths
  containing `test` do not misclassify staging errors.

## Validation

Expected focused validation after Phase B implementation:

- `PYTHONHASHSEED=0 pytest mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap -q --tb=long`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_a_executor.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'pager or founder_override or commit_handoff or routing_record'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_meta_bridge_supervisor.py -k 'pager or lifecycle or routing'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-lifecycle-event-coverage-2026-04-23`
- `./tools/checks/check_docs_consistency.sh`

Observed Phase B-local validation (2026-04-26):

- `PYTHONHASHSEED=0 pytest mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap -q --tb=long` — 1 passed after pre-commit growth-cap repair.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py` — 49 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_a_executor.py` — 3 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py` — 301 passed after Implementation-Agent Bridge Round 1 NO_GO remediation.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py` — 939 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'pager or founder_override or commit_handoff or routing_record'` — 24 passed, 371 deselected after Implementation-Agent Bridge Round 2 NO_GO remediation.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_meta_bridge_supervisor.py -k 'pager or lifecycle or routing'` — 24 passed, 109 deselected after Implementation-Agent Bridge Round 1 NO_GO remediation.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short` — 54 passed after Implementation-Agent Bridge Round 1 NO_GO remediation.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'index_lock or embedded_stage_files'` — 4 passed, 937 deselected after self-cleared `index.lock` retry repair and embedded stage-files classifier repair.
- Handoff dry-run staging via `git add --dry-run -- <19 handoff files>` — passed with `mu/tests/docs/test_growth_caps.py` and no symlink pathspec error.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id pager-lifecycle-event-coverage-2026-04-23` — passed as L4_ENABLER compliant with the staged changed-file set, 0 runtime files, and active `FOUNDER_OVERRIDE`.
- `./tools/checks/check_docs_consistency.sh` — passed; it retained the pre-existing STATUS.md freshness warning for 2026-04-08.

## Closeout Notes

This packet is not a claim that all lifecycle pings are already present. It is
the bounded automated-pipeline package to make the missing lifecycle pings and
the PR #823 founder-override recurrence part of the same active
`[PIPELINE-AGENT-PAGER]` wave.
