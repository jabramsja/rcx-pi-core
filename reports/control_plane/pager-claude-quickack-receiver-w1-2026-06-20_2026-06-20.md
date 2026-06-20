# NEXT-CODEX-POST-REDTEAM - PAGER-FIX wave 1: dormant claude_pager_receiver file-queue drain + fresh claude -p delivery (no pager change)

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pager-claude-quickack-receiver-w1-2026-06-20
Phase-A-Lock: LOCKED
Purpose: PAGER-FIX wave 1 of 3. PROBLEM (verified in the live pager state): the pipeline pager claude leg runs a FULL claude turn under the ~10-20s ack budget, so it is killed every dispatch (the lane pager states show delivered_targets empty across events with last_error 'claude pager submission timed out'), while the codex leg delivers via its persistent app-server daemon. So the pager does NOT reliably notify the Claude side. PROVENANCE (bridge round 1, DOC_ACCURACY): the dormant receiver module tools/session/claude_pager_receiver.py and its unit test mu/tests/tools/test_claude_pager_receiver.py were ORIGINALLY delivered by the prior wave `pager-quickack-receiver-2026-06-17` (commit f3243a1c) and are in origin/dev; this wave did NOT create them from scratch. They implement the founder-decided 2026-06-17 quick-ack design: a per-bus file-queue drain loop that delivers each queued event via a FRESH direct claude -p subprocess (NOT a monitor-resume), serialized one turn at a time, with a generous per-delivery timeout (about 120s), start_new_session plus terminate-process-group reaper so a hung turn cannot wedge the daemon, the _claude_dispatch_env (RCX_PIPELINE_SESSION=1, RCX_CLAUDE_MONITOR unset) so delivery never clobbers the orchestrator or monitor session id files, an outcome record (exit 0 means success, else re-queue), and idempotency by event_id then transition_key. ROUND-2 HARDENING (this wave): bridge round 2 found a persistent-failure tight-loop in the already-landed drain/poll loop, so this wave MODIFIES the module (65 insertions / 17 deletions vs origin/dev) and its test (67 insertions vs origin/dev): deliver_once gains a skip_keys guard that returns `exhausted` instead of re-delivering an event already attempted this drain pass; run_until_empty attempts each failing event at most once per call by idempotency key-set; run_forever uses an interruptible backoff (stop_event.wait) so a poison event can never tight-loop the daemon; and the test adds 2 regression tests for that hardening. This wave's net diff is therefore the module hardening + the 2 regression tests + this wave's L4 indicator + this corrected tracker-sync governance note; the evidence gate is green at 22 passed. The pager itself is NOT changed in this wave (that is wave 2); the receiver is dormant until wired. Observability/control-surface only: no runtime, substrate, seed, projection, or JS change. Pager and autoping remain SEPARATE processes.

## Scope

The dormant tools/session/claude_pager_receiver.py + its unit test (originally delivered by pager-quickack-receiver-2026-06-17 / commit f3243a1c, in origin/dev) are HARDENED this wave for a bridge round-2 persistent-failure tight-loop and BOUND to this wave's L4 indicator. The module is modified (65 insertions / 17 deletions vs origin/dev) and the test gains 2 regression tests (67 insertions vs origin/dev); both remain dormant (pager unchanged, nothing wires them). No pager change and no runtime/substrate change. Uses TASKS.md as tracker-sync authority.

Files and surfaces in scope:

- tools/session/claude_pager_receiver.py (originally landed in f3243a1c, in origin/dev; HARDENED this wave) -- per-bus file-queue drain + fresh claude -p serialized delivery + reaper + outcome record + idempotency. Modified this wave (65 insertions / 17 deletions vs origin/dev): round-2 tight-loop hardening (skip_keys/`exhausted` guard, per-call at-most-once drain, interruptible run_forever backoff). Stays dormant.
- mu/tests/tools/test_claude_pager_receiver.py (originally landed in f3243a1c, in origin/dev; EXTENDED this wave) -- unit tests for enqueue/drain/outcome/idempotency/reaper using a fake claude binary. Modified this wave (67 insertions vs origin/dev): +2 regression tests for the round-2 tight-loop hardening. Green at 22 passed.
- reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json (GENERATED this wave) -- L4 indicator binding; net_host_semantic_delta 0.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w1-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pager-claude-quickack-receiver-w1-2026-06-20_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Confirm the dormant receiver + test were originally delivered by pager-quickack-receiver-2026-06-17 (commit f3243a1c) and are in origin/dev; this wave further MODIFIES them (module 65 insertions / 17 deletions, test 67 insertions vs origin/dev) for the round-2 tight-loop hardening rather than re-creating them.
2. Re-read tools/session/claude_pager_receiver.py to confirm it still implements the seven locked behaviors: per-bus file-queue drain; fresh claude -p (never --resume); ~120s per-delivery timeout + start_new_session/terminate-process-group reaper; _claude_dispatch_env so session-id files are never clobbered; exit-0->durable-receipt else fail-open re-queue; event_id/transition_key idempotency; fail-open on missing inputs.
3. Confirm the module is DORMANT: nothing in the tree imports/wires/starts it, and pipeline_agent_pager.py is unchanged in this wave.
4. Run the evidence command (test suite) and confirm green (22 passed, including the 2 round-2 regression tests).
5. Collect the L4 indicator artifact and confirm net_host_semantic_delta 0.
6. Keep this packet and the TASKS.md tracker note accurate: record BOTH the receiver/test provenance (originally f3243a1c, in origin/dev) AND the round-2 tight-loop hardening this wave applies to them (module + test diffs vs origin/dev), so neither falsely claims the wave creates the files from scratch nor that they are byte-identical/unmodified.

## Constraints

- Use the pipeline launcher and dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Observability/control-surface tooling only: no runtime (eval_seed), substrate, seed, projection, or JS change.
- Do NOT modify pipeline_agent_pager.py or the codex leg in this wave; the receiver stays dormant until wave 2.
- Pager and autoping remain SEPARATE processes; never resume the live orchestrator; never clobber orchestrator_session_id / claude_monitor_session_id (use _claude_dispatch_env).
- Tests must use a fake claude binary; no real model invocation in the test suite.
- Durable success only on turn exit 0; fail-open (leave pending/re-queue) on receiver error.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if the dormant receiver cannot be built without modifying the pager or sharing the autoping monitor session.
- If the module would require touching runtime or substrate files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`

## Acceptance criteria

- tools/session/claude_pager_receiver.py exists, is dormant (pager unchanged), and drains a file-queue delivering via fresh claude -p with a reaper and outcome record.
- Idempotency by event_id then transition_key; exit-0 success else re-queue; fail-open on missing inputs.
- mu/tests/tools/test_claude_pager_receiver.py passes using a fake claude binary.
- pipeline_agent_pager.py is unchanged in this wave; pager and autoping stay separate.
- net host semantics delta 0 and the indicator artifact is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pager-claude-quickack-receiver-w1-2026-06-20`.
- Governing packet: this file, `reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `pager-claude-quickack-receiver-w1-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder 2026-06-20: the pager is not paging the Claude side (verified: claude leg times out every dispatch). Standing directive to land the structural fix. This is wave 1 of 3 from the founder-decided 2026-06-17 quick-ack design. Runs parallel to Stage 4 design and PIPELINE-FIX-33 (non-overlapping files).

FOUNDER_OVERRIDE:pager-claude-quickack-receiver-w1-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pager-claude-quickack-receiver-w1-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w1-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pager-claude-quickack-receiver-w1-2026-06-20`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w1-2026-06-20_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-claude-quickack-receiver-w1-2026-06-20 --output reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pager-claude-quickack-receiver-w1-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-claude-quickack-receiver-w1-2026-06-20`
- Active packet: `reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7ae60ef2e0cec4641f5ce9fb4c76e6939e128e08d4f844ee7565eb718a303921`
- Indicator artifact: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_claude_pager_receiver.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_claude_pager_receiver.py`
  - `mu/tools/session/claude_pager_receiver.py`
  - `reports/control_plane/pager-claude-quickack-receiver-w1-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pager-claude-quickack-receiver-w1-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pager-claude-quickack-receiver-w1-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
