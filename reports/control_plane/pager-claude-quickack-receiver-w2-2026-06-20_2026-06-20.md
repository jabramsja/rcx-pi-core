# NEXT-CODEX-POST-REDTEAM - PAGER-FIX wave 2: pager claude leg enqueues to the receiver (quick-ack), drop the blocking-turn timeout

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-claude-quickack-receiver-w2-2026-06-20
Phase-A-Lock: LOCKED
Purpose: PAGER-FIX wave 2 of 3, per the Wave 1 design packet reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md. Wave 1 landed the dormant claude_pager_receiver on dev. PROBLEM (verified): the pager claude leg _dispatch_claude runs a full claude turn (resume or fresh claude -p) under the ~10-20s pager ack budget and is killed every dispatch (live pager states: 0 claude delivered, error 'claude pager submission timed out'), so claude pages never deliver. FIX: re-point _dispatch_claude to ENQUEUE the event to the wave-1 claude_pager_receiver file-queue and return a fast accepted_async quick-ack (mirroring the codex app-server turn-accepted pattern), instead of blocking on a full turn. Two-phase state: enqueue marks accepted_async (the claude leg's quick-ack does NOT take the synchronous dispatch_result.acknowledged -> delivered[target]=ack write at the _dispatch loop ~L1904); delivered_targets[claude] is written ONLY when the async claude turn exits 0. Receipt bridge (the authority path -- this is the integration point the reviewer required naming): the wave-1 receiver already writes its success receipt to `.agent_bus/observability/claude_pager_receiver/delivered.jsonl` on exit 0 (schema `{event_id, transition_key, ack, recorded_at}`, no `target` field); the pager's `_reconcile_delivery_state` is extended to ALSO consume that receiver receipt file and map each exit-0 success to delivered_targets["claude"] (matched by event_id against the known event_map, tolerant of unknown/foreign entries -- skip, do NOT raise -- and idempotent). The receiver schema is consumed AS-IS; the receiver module is not modified (Option B: pager pulls, rather than the receiver writing into the pager's `pipeline_agent_delivery_receipts.jsonl`). Re-queue on failure (do not mark delivered on enqueue, or receipts would mask async failures on reconcile). Drop the monitor-resume + blocking-subprocess path from the claude leg entirely (the design's fresh-claude-p decision). Fail-open: if the receiver/queue is unavailable, leave the target pending (retryable), exactly as today (no regression). Leave the codex leg untouched; pager and autoping remain separate. Observability/control-surface only: no runtime/substrate/seed change.

## Scope

Re-point pager _dispatch_claude to enqueue to the wave-1 receiver + tests. No runtime/substrate change; codex leg untouched. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tools/observability/pipeline_agent_pager.py (MODIFY) -- (a) _dispatch_claude enqueues to the claude_pager_receiver file-queue and returns accepted_async quick-ack (and must NOT take the synchronous dispatch_result.acknowledged -> delivered[target]=ack path at ~L1904 for the claude leg); drop monitor-resume + blocking subprocess; (b) _reconcile_delivery_state (currently rebuilds delivered_targets only from pipeline_agent_delivery_receipts.jsonl) is extended to ALSO consume the receiver's claude_pager_receiver/delivered.jsonl and map each exit-0 success receipt to delivered_targets["claude"] (matched by event_id, tolerant of unknown entries, idempotent) -- this is the receipt bridge; fail-open if the receiver/queue is unavailable (leave pending).
- mu/tools/session/claude_pager_receiver.py (READ-ONLY this wave) -- its wave-1 delivered.jsonl success-receipt schema is consumed as-is by the pager reconcile bridge; NOT modified (the receiver does not gain a `target` field and does not write into the pager's receipt file).
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- regression tests: enqueue/accepted_async, no-delivered-on-enqueue, the reconcile receipt-bridge promotion (receiver delivered.jsonl exit-0 success -> delivered_targets[claude], matched by event_id, idempotent, tolerant of unknown entries), re-queue on failure, no-monitor-resume invariant, fail-open, codex leg unchanged.
- reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w2-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2-2026-06-20_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read the Wave 1 design packet reports/control_plane/pager-quickack-receiver-2026-06-17_2026-06-17.md, the wave-1 claude_pager_receiver module (mu/tools/session/claude_pager_receiver.py -- esp. _write_receipt and the delivered.jsonl path/schema), and the current pager _dispatch_claude + _reconcile_delivery_state + _load_delivery_receipts (delivered_targets/pending_targets/receipts) to wire the enqueue + two-phase semantics + receipt bridge against the real on-disk schemas.
2. Modify _dispatch_claude to enqueue the event (event_id/transition_key) to the receiver's per-bus file-queue and return accepted_async; remove the monitor-resume and blocking-subprocess full-turn path from the claude leg; ensure the accepted_async return does NOT flow into the synchronous dispatch_result.acknowledged -> delivered[target]=ack write (~L1904) for the claude leg (only the reconcile bridge in item 4 may set delivered_targets[claude]).
3. Implement the enqueue side of two-phase state: accepted_async on enqueue; do NOT mark delivered on enqueue; re-queue on failure; fail-open (leave pending) when the receiver/queue is unavailable.
4. Implement the receipt bridge (the integration point named by the reviewer): extend _reconcile_delivery_state to consume the receiver's claude_pager_receiver/delivered.jsonl and, for each exit-0 success receipt whose event_id matches a known pager event, set delivered_targets["claude"] = ack and refresh pending_targets. Match by event_id; be tolerant of unknown/foreign receiver entries (skip, do NOT raise like the pager-native receipt path does); be idempotent (re-reading the file across reconciles re-sets the same delivered[claude]); fail-open if the file is absent/unreadable. Do not modify the receiver's schema.
5. Add regression tests in test_pipeline_agent_pager.py for: enqueue/accepted_async; that the claude leg does NOT write delivered on enqueue; the reconcile bridge promoting a receiver delivered.jsonl exit-0 success to delivered_targets[claude] (matched by event_id, idempotent, tolerant of unknown entries); re-queue on failure; the no-monitor-resume invariant; fail-open when the receiver/queue is unavailable; and that the codex leg is unchanged (use a fake/stubbed receiver + fake claude; no real model call).
6. Run the evidence command and collect the indicator.

## Constraints

- Use the pipeline launcher and dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Observability/control-surface tooling only: no runtime (eval_seed), substrate, seed, projection, or JS change.
- Leave the CODEX leg of the pager untouched; pager and autoping remain SEPARATE; never resume the live orchestrator; use the existing _claude_dispatch_env clobber guard.
- Do NOT mark delivered on enqueue (receipts rebuild delivered_targets on reconcile -> that would mask async failures); the durable signal is the receiver's exit-0 delivered.jsonl receipt only.
- Authority path is Option B (pager pulls): the ONLY writer of delivered_targets[claude] for this leg is the reconcile bridge consuming the receiver's delivered.jsonl. Do NOT modify the receiver module/schema (no `target` field added; the receiver does not write into the pager's pipeline_agent_delivery_receipts.jsonl). The reconcile bridge must not raise on unknown/foreign receiver entries (the pager-native receipt path's hard-raise-on-unknown-event_id behavior does not apply to the receiver file).
- Fail-open: if the receiver is unavailable, leave the target pending/retryable (no regression vs today).
- Tests must use a fake claude binary / stubbed receiver; no real model invocation in the suite.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if the quick-ack enqueue OR the reconcile receipt bridge cannot preserve fail-open or the no-monitor-resume / pager!=autoping invariants -- e.g., if promoting claude into delivered_targets would require modifying the receiver schema/module or coupling to the codex leg (the chosen authority path is Option B: pager pulls the receiver's delivered.jsonl, receiver unchanged).
- If the change would require touching runtime or substrate files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- _dispatch_claude enqueues to the receiver and returns accepted_async within the budget; the accepted_async return does NOT take the synchronous acknowledged -> delivered write; the monitor-resume + blocking full-turn path is gone from the claude leg.
- The receipt bridge is wired: _reconcile_delivery_state consumes the receiver's claude_pager_receiver/delivered.jsonl and promotes claude to delivered_targets["claude"] on an exit-0 success matched by event_id; it is idempotent across reconciles and tolerant of unknown/foreign entries (no raise); the receiver schema/module is unchanged.
- delivered_targets[claude] is written ONLY by that reconcile bridge on async turn exit 0 (nothing else writes it for the claude leg); failures re-queue; receiver-unavailable/file-absent leaves the target pending (fail-open).
- The no-monitor-resume invariant and pager!=autoping separation hold; the codex leg is unchanged.
- test_pipeline_agent_pager.py + test_claude_pager_receiver.py pass.
- net host semantics delta 0 and the indicator artifact is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pager-claude-quickack-receiver-w2-2026-06-20`.
- Governing packet: this file, `reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w2-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder 2026-06-20: the CLAUDE pager must deliver (it currently times out every dispatch). Wave 2 of 3 from the founder-decided 2026-06-17 quick-ack design; depends on the wave-1 receiver landed on dev (5d2fc46d). This is the change that actually fixes delivery.

FOUNDER_OVERRIDE:pager-claude-quickack-receiver-w2-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pager-claude-quickack-receiver-w2-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-claude-quickack-receiver-w2-2026-06-20`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2-2026-06-20_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-claude-quickack-receiver-w2-2026-06-20 --output reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-claude-quickack-receiver-w2-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-claude-quickack-receiver-w2-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f33d3ded6b903a1685abf7b9458af3f855cedb95df629b0a34781872507304e2`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w2-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w2-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w2-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
