# NEXT-CODEX-POST-REDTEAM - PAGER-FIX wave 2b: self-sufficient claude pager delivery (enqueue guarantees drain), addresses PR #1137 P1+P2

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-claude-quickack-receiver-w2b-2026-06-20
Phase-A-Lock: LOCKED
Purpose: PAGER-FIX (re-scoped wave 2), per the founder-decided 2026-06-17 quick-ack design packet reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md, the wave-1 packet reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md, and the codex bot review of the stranded PR #1137. Wave 1 landed the dormant claude_pager_receiver on dev. The first wave-2 attempt made _dispatch_claude ENQUEUE to the receiver and return, but the codex bot correctly flagged P1: nothing starts or drains the receiver (that was deferred to a separate wave 3), so with the committed route=both, claude events queue forever and no claude -p is ever run -- a REGRESSION vs the old direct delivery attempt (which at least retried). FIX (this wave): make the claude pager SELF-SUFFICIENT -- the enqueue path itself GUARANTEES the queued event will be drained, with NO never-drained-queue window. Preferred mechanism: on enqueue, ensure the receiver drain is running via a MINIMAL idempotent singleton (a pidfile/lock-guarded lazy-start of the wave-1 receiver drain, or an equivalently simple detached per-event drain) -- choose the SIMPLEST mechanism that guarantees drain and does NOT introduce an open-ended daemon-lifecycle surface (no owner-loop / session-rebuild / restart-supervision; just start-if-not-running + the existing reaper). Also fix P2: the receiver dedups on BOTH event_id and transition_key, dropping distinct events that share a transition_key -- dedup on event_id ONLY (transition_key is not a unique event identity). Keep two-phase state (accepted_async on enqueue; durable delivered_targets[claude] only on the async claude turn exit 0; re-queue on failure) and FAIL-OPEN: if the drain cannot be ensured, leave the target pending/retryable -- never mark accepted for a queue that will not drain. Leave the codex leg untouched; pager and autoping stay separate; never resume the live orchestrator (use _claude_dispatch_env). Observability/control-surface only: no runtime/substrate/seed change. This single wave replaces the old wave 2 + wave 3.

## Scope

Self-sufficient claude pager: _dispatch_claude ensures-drain + enqueues; receiver dedups on event_id only; + tests. No runtime/substrate change; codex leg untouched. TASKS.md is tracker-sync authority. Replaces old wave 2 + wave 3.

Files and surfaces in scope:

- mu/tools/observability/pipeline_agent_pager.py (MODIFY) -- _dispatch_claude ensures the receiver drain is running (minimal idempotent singleton, no open-ended lifecycle) then enqueues + accepted_async; two-phase durable receipt on exit 0; fail-open (leave pending) if drain cannot be ensured; never a never-drained queue.
- mu/tools/session/claude_pager_receiver.py (MODIFY) -- dedup on event_id ONLY (drop transition_key from the dedup key so distinct events are not lost); expose a minimal idempotent start-if-not-running entry for the pager to call.
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- enqueue-ensures-drain, no-never-drained-queue, fail-open-when-drain-unavailable, no-monitor-resume, codex-leg-unchanged.
- mu/tests/tools/test_claude_pager_receiver.py (MODIFY) -- event_id-only dedup keeps distinct same-transition_key events; idempotent start-if-not-running.
- reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w2b-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2b-2026-06-20_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read the 2026-06-17 quick-ack design packet reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md and the wave-1 packet reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md (which landed/hardened the dormant claude_pager_receiver), the stranded wave-2 _dispatch_claude change (`git show origin/jabramsja/pager-claude-quickack-receiver-w2-2026-06-20`, resolves to 62b3393ad42ece0db4877c099fc05467d6d53be9), and the codex P1+P2 on PR #1137, to ground the self-sufficient re-scope.
2. Modify _dispatch_claude to ensure the receiver drain is running (minimal idempotent singleton start-if-not-running; reuse the wave-1 reaper; NO owner-loop/session-rebuild/restart-supervision) BEFORE/AT enqueue, so an enqueued event is always drained; return accepted_async.
3. Fix the receiver dedup to key on event_id only (not transition_key) so distinct events sharing a transition_key are not dropped; add the minimal start-if-not-running entry.
4. Preserve two-phase (durable delivered_targets[claude] only on async turn exit 0; re-queue on failure) and fail-open (if drain cannot be ensured, leave the target pending/retryable; never mark accepted for an undrainable queue).
5. Add/adjust regression tests for: enqueue-ensures-drain, no never-drained queue, event_id-only dedup, fail-open, no-monitor-resume, codex leg unchanged (fake claude binary / stubbed drain; no real model call).
6. Run the evidence command and collect the indicator.

## Constraints

- Use the pipeline launcher and dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Observability/control-surface tooling only: no runtime (eval_seed), substrate, seed, projection, or JS change.
- Leave the CODEX leg untouched; pager and autoping stay SEPARATE; never resume the live orchestrator (use _claude_dispatch_env); never clobber orchestrator_session_id / claude_monitor_session_id.
- Do NOT introduce an open-ended daemon-lifecycle surface (no owner-loop, session-rebuild, restart-supervision, autofollow) -- keep the drain-ensure to a minimal idempotent start-if-not-running + the existing wave-1 reaper. This is the #59 open-ended-surface divergence guard.
- Do NOT mark a target accepted/delivered for a queue that will not drain; durable receipt only on async turn exit 0; fail-open leaves pending.
- Tests must use a fake claude binary / stubbed drain; no real model invocation in the suite.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if drain cannot be guaranteed without either a never-drained-queue window or an open-ended daemon lifecycle.
- If the change would require touching runtime or substrate files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- _dispatch_claude ensures the receiver drain is running then enqueues; there is no never-drained-queue window even with route=both (the P1 regression is gone).
- Receiver dedups on event_id only; distinct events sharing a transition_key are delivered (P2 fixed).
- Two-phase durable-receipt-on-exit-0 + re-queue on failure + fail-open (leave pending if drain unavailable) hold; no open-ended daemon lifecycle added.
- no-monitor-resume + pager!=autoping invariants hold; codex leg unchanged.
- test_pipeline_agent_pager.py + test_claude_pager_receiver.py pass; net host semantics delta 0; indicator collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pager-claude-quickack-receiver-w2b-2026-06-20`.
- Governing packet: this file, `reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w2b-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder 2026-06-20: the CLAUDE pager must deliver. The codex bot correctly flagged that the first wave-2 (PR #1137) regressed the claude leg to a never-drained queue (P1) -- a true finding, not deferred. This re-scope makes wave 2 self-sufficient (folds in the receiver drain-start) + fixes P2, per the manual-unblock-then-structural-fix directive. Depends on the wave-1 receiver on dev (5d2fc46d).

FOUNDER_OVERRIDE:pager-claude-quickack-receiver-w2b-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pager-claude-quickack-receiver-w2b-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2b-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-claude-quickack-receiver-w2b-2026-06-20`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2b-2026-06-20_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-claude-quickack-receiver-w2b-2026-06-20 --output reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-claude-quickack-receiver-w2b-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-claude-quickack-receiver-w2b-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `88c273f1a8b92441a6231a8c83ad331fc655d5ebead0f7dbd7a36b6d801ed12d`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w2b-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2b-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2b-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
