# Land lifecycle prevention with live-dispatcher retry completion

Date: 2026-09-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-fleet-native-prevention-r8-2026-09-22
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 5a58cc2521571c0fa636f18a9040deae741672a26cc30448194044785ff2cd1b
Purpose: Finish existing row40 by carrying the preserved R7 lifecycle implementation and correcting its reproduced live-dispatcher failed-child/successful-child completion dependency. This is the same existing L4_ENABLER cleanup-prevention task, not a new numbered task, speculative guard or prerequisite.

## Scope

Same24exact paths and existing row40. Preserve the R7 useful implementation on unchanged landed PR1311 base; correct only the reproduced live-dispatcher commit-retry ownership dependency and its real composed regression. Native Phase A owns the full packet.

Files and surfaces in scope:

- TASKS.md -- Same row40; sync actual PR/fleet/next-owner facts, preserving268task IDs and39parked obligations.
- CHANGELOG.md -- Actual recurrence and demonstrated recovery repairs.
- mu/tools/executors/worktree_lifecycle.py -- Preserved bounded durable native completion owner, adapted to freshly landed transaction APIs/invariants.
- mu/tools/executors/launch_wave.py -- Native lifecycle integration and reproduced legitimate late-stage packet/tracker continuation mismatch only.
- mu/tools/executors/executor_dispatch.py -- Actual terminal success/stop/failure ownership handoff; preserve no-replay and pager authority.
- mu/tools/executors/commit_executor.py -- Reviewed sync/lifecycle controls and actual R3 loaded-source/transaction-owner/retirement ordering; retain PR1308 authority/budgets.
- mu/tools/executors/phase_b_executor.py -- Conditional producer/consumer dependency for actual latest late-supervisor findings and bounded native continuation; no unrelated phase redesign.
- mu/tools/executors/workingrcx_fleet_apply.py -- Lifecycle consumer dependency and actual source196 deletion intent; preserve current transaction/index/stash/native recovery invariants.
- mu/docs/agents/WorktreeLifecycle.v0.md -- Actual durable ownership, bounded retry/escalation, useful-work accounting and supported recovery commands.
- mu/tests/tools/test_worktree_lifecycle.py -- Real native successful/stopped/failure and same-HEAD stopped-to-merged regression proof.
- mu/tests/tools/test_launch_wave.py -- Exact legitimate late-stage native continuation acceptance and tamper/replay rejection.
- mu/tests/tools/test_executor_dispatch.py -- Actual completion handoff integration.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py -- Actual loaded-source/owner-safe sync and durable retirement-order regressions.
- mu/tests/tools/test_phase_b_executor.py -- Conditional actual latest-finding continuation dependency proof.
- mu/tests/tools/test_workingrcx_fleet_apply.py -- Current transaction regressions plus actual deleted-path stash/journal intent proof.
- mu/tests/tools/test_commit_executor_receipt.py -- Surviving receipt authority dependency.
- mu/tests/tools/test_commit_outcome_pager_lifetime.py -- Final pager must not recreate retired source.
- mu/tests/tools/test_pr_disposition_no_replay_finalization.py -- Preserved PR disposition ownership and no replay.
- mu/tests/docs/test_growth_caps.py -- Exact canonical generation for the demonstrated lifecycle helper/doc/test delta, preserving authority.
- reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md -- Native Phase A packet from fresh R8 STUB for the same queue owner.
- reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json -- Native indicator.
- mu/tools/executors/recovery_gate.py -- Preserve reviewed scratch authority; repair demonstrated loss of failing shell diagnostics between native recovery attempts.
- mu/tests/tools/test_recovery_gate.py -- Real failed-diagnostic feedback regression, retaining scratch and mutation protections.
- reports/deferred/non_blocking/workingrcx-fleet-native-prevention-r8-2026-09-22_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-09-22 tracker sync note for wave `workingrcx-fleet-native-prevention-r8-2026-09-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Root supplies this external STUB only; native Phase A owns the full packet and pipeline owns all source/test/staging/commit/push/merge. Continue existing [FLEET-NATIVE-LIFECYCLE-PREVENTION] row40. Read current PRIMARY TASKS and foreground checkpoint for queue truth. Preserve268unique task IDs and39parked obligations, unrelated PRIMARY WIP, and original held tracker journals/stashes. Current comparison commit3fe05fdf8a61ec7d40398175e161a73e0006b20a is verified local+remote; do not restore any older TASKS wholesale.
2. Use the latest preserved R7 candidate, not an older reconstruction: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-native-prevention-r7-evidence-2026-09-22/terminal_stopped_candidate/manifest.json SHA256391c47f4c04f4524e411f8a8fb3ed15d0dd30740e8628dd15baac7a7c64af65a. Verify all64manifest entries before carrying its source/test/lifecycle-doc hunks. That candidate shares this exact comparison base and includes R6 plus the R2 failed-closeout correction. Preserve R7/R6 carriers, indices, receipts, findings and history unchanged. Do not copy the old packet/indicator or stale current-state tracker text.
3. Start with the actually reproduced end-to-end lifecycle failure, before long gates: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-native-prevention-r7-evidence-2026-09-22/live_dispatcher_handoff_finding.json and preserved native_launch_terminal.log. worktree_lifecycle.start_completion deliberately defers while a dispatcher owner is alive, but _pre_merge_evidence demands completed evidence before unchanged-HEAD commit retry can publish fresh success. Prior R2 tests registered exited owners; they do not prove this live-parent composition. Build a real regression with a live dispatcher parent and sequential failed/successful commit children, reproduce the failure, then make the smallest coherent producer/consumer ownership correction. Preserve prior failed closeout and original finite attempt accounting; require fresh successful closeout; retain interrupted-mutation fail-closed protection. Prove eventual completion after actual owner exit, not just helper acceptance or mocked PID absence.
4. Retain every already-reviewed R7 behavior and landed PR1311 behavior: fresh final commit receipt after mechanical gates with exact staged-byte authority and real fixture repositories; native lifecycle ownership across success/stop/failure; durable closeout surviving retirement; loaded-source/original-transaction recovery; surviving-root coverage; source196 deletion intent; actual late-supervisor latest-finding handoff; failed-shell diagnostic feedback; exact optional same-wave report admission. Do not redesign or add hypothetical cases. The old running primary producer could not emit R7's newer sealed continuation identity; this is why a fresh STUB is necessary, not permission to forge/upgrade R7's terminal checkpoint.
5. Reconcile TASKS and CHANGELOG from current truth while preserving both landed history and R7's useful implementation evidence. Mark current R8, stopped/preserved R7, actual validation and cleanup/Mu order truthfully. Reuse preserved substantive source/test/doc deltas on the unchanged base; do not reimplement working R7 code. Derive exact growth caps only for the real current delta using the existing canonical producer; preserve authority limits, regressions, L4 proof and empty anti-theater exception registry.
6. After the real live-parent regression passes, verify collection, then run the exact anti-theater-first tools/growth chain and separate complete docs suite. Keep generated pytest/provider fixtures in default system temporary storage outside all checkouts; never set TMPDIR or --basetemp to checkout .scratch. Preserve native logs/receipts/provenance; no skips, fake exit-zero wrappers, cap padding, receipt resets or timeout bypass. Prior passing gates are historical, not approval of changed bytes.
7. All selected LLM roles remain Codex gpt-6-astra/max, commit providerless, pager Codex. Native review must assess actual composed parent/child lifecycle completion, not only helper-level tests. Native commit/CI/merge/PRIMARY sync must complete with durable closeout. Do not replay any of37consumed fleet operations or touch live source196 journal/stash during implementation. Existing next owner is fresh bounded eligible fleet cleanup/useful-work integration followed by Mu; individual evidenced HOLDs must not blanket-block safe peers.

## Constraints

- Existing row40 only and same24exact paths; no new numbered queue item, independent prerequisite or hypothetical hardening. Correct the reproduced live-parent lifecycle handoff while preserving prior useful implementation.
- Root supplies external STUB, bounded trackers/evidence and clean carrier only. Native builders/executors own full packet/source/tests/staging/review/commit/push/merge. Frozen R7/R6 authority, terminal receipts and claims remain unchanged.
- Preserve all unrelated WIP, stopped candidates, indices, local commits, journals, stashes, bundles and useful-work owners. No destructive reset, forced removal, old-operation replay or archive-only closure.
- Use real isolated repository/process fixtures outside checkouts. Live fleet claims/journals/operations remain read-only. No Claude/runtime/host/seed/parity semantics changes.
- Retain all native gates, exact chained evidence plus separate complete docs, current-base proof, receipt/index authority and finite original lifecycle budgets. Only reproduced mandatory out-of-scope dependencies justify stopping.
- Optional exact same-wave bridge_nonblockers path is admitted before lock, but do not create or require an absent report or widen authority.

## Stop conditions

- Stop before a reproduced required out-of-scope mutation; give exact evidence rather than silently widening a frozen packet.
- Do not mutate or synthesize R7 continuation state, receipt or findings to resume it. The native producer did not seal latest identity, and both supported read-only admission checks reject it.
- Keep unsafe live targets as individual evidenced HOLDs with owner/next action. Do not claim cleanup/useful-work landing from preservation, census, code or tests alone.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/docs/test_growth_caps.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Real live dispatcher parent with sequential failed and successful commit children at unchanged HEAD converges, records fresh successful closeout and eventual bounded completion; prior failures/attempts/interrupted-mutation protections are preserved.
- All missing R7 prevention hunks carried forward without losing landed PR1311 behavior; exact retained-source/evidence identity verified.
- Fresh exact tools/growth and separate full docs pass with real composed regression and no anti-theater exceptions, padded caps or weakened gates.
- All268task IDs/39parked obligations remain; native review/commit/CI/merge/PRIMARY sync and durable closeout verified. Existing physical cleanup/useful-work landing stays directly next, then Mu.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-fleet-native-prevention-r8-2026-09-22`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`.
- TASKS.md authority: the 2026-09-22 tracker sync note for wave `workingrcx-fleet-native-prevention-r8-2026-09-22` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-native-prevention-r8-2026-09-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-native-prevention-r8-2026-09-22`
- Active packet: `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/WorktreeLifecycle.v0.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tests/tools/test_worktree_lifecycle.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `mu/tools/executors/worktree_lifecycle.py`
  - `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-native-prevention-r8-2026-09-22 --output reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/docs/test_growth_caps.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md. (2) Final pytest gate covered 9 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/docs/test_growth_caps.py`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tests/tools/test_worktree_lifecycle.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `mu/tools/executors/worktree_lifecycle.py`, `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`, `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-native-prevention-r8-2026-09-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-fleet-native-prevention-r8-2026-09-22`
- Step-5e provenance: `bumped`
- Purpose: commit automation may bind the exact same-wave growth-cap governance file after Phase B review; first bumps require staged-index proof, while already-recorded reuse requires clean HEAD/index proof.
- Authorized generated governance path(s):
  - `mu/tests/docs/test_growth_caps.py`
- Scope binding: the path above is in scope only as the Step-5e same-wave growth-cap governance mutation or exact clean same-wave continuation evidence.
- Pre-review boundary: this block does not add the path to the locked Phase B/pre-review candidate allowlist and cannot authorize arbitrary implementation files.
- Acceptance binding: unsupported, malformed, outside-repo, dirty, wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free generated governance paths fail before supervisor.
<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-native-prevention-r8-2026-09-22`
- Active packet: `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c2a176d31fdfa50ed61923036cef51d00cb28c6f64d1935216736b887380ec22`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py mu/tests/docs/test_growth_caps.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md. (2) Final pytest gate covered 9 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/docs/test_growth_caps.py`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tests/tools/test_worktree_lifecycle.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `mu/tools/executors/worktree_lifecycle.py`, `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`, `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`..
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `candidate_authority_receipt`: `.agent_bus-fleet-native-prevention-r8-20260922/meta/candidate_authority_receipts/workingrcx-fleet-native-prevention-r8-2026-09-22/commit-pre-supervisor.json`
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/WorktreeLifecycle.v0.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tests/tools/test_worktree_lifecycle.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `mu/tools/executors/worktree_lifecycle.py`
  - `reports/control_plane/workingrcx-fleet-native-prevention-r8-2026-09-22_2026-09-22.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-native-prevention-r8-2026-09-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
