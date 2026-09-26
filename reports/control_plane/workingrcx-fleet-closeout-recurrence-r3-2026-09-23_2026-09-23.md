# Land preserved fleet closeout corrections with dispatcher integration tests

Date: 2026-09-23
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-fleet-closeout-recurrence-r3-2026-09-23
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: b3c385fe14db7cfe89b9a30f51bf093f19a55f44f92c23cb1cfa911607dedfc3
Purpose: Complete existing FLEET-NATIVE-LIFECYCLE-PREVENTION by reusing R2's native three-part preserve/sync/retire correction and the native dispatcher-fixture repair. R2 committed locally but broad pre-push exposed11 stale integration fixtures, then recovery's repair was outside its immutable allowlist. Admit only that demonstrated missing test file; no additional queue task, production feature, hypothetical hardening or gate bypass. Existing row38 remaining physical/useful-work/registration cleanup follows this correction before Mu.

## Scope

Fifteen exact paths: the same three tooling sources, five focused/integration test files, lifecycle documentation, tracker/governance and same-wave evidence. Only R2's missing dispatcher-test authority is added. No runtime/host semantics delta or new queue row.

Files and surfaces in scope:

- TASKS.md -- Preserve all268task IDs and39parked obligations; synchronize existing rows38/40, unfinished useful-work owners and the working to-do. R2 is stopped/nonmerged, not completed. Remaining actual fleet cleanup precedes Mu. Retain founder's immediate<=10% quota stop policy without publishing private usage.
- CHANGELOG.md -- Record only the three reproduced preservation/closeout corrections and actual validation.
- mu/tools/executors/commit_executor.py -- Preserve staged/index intent separately from worktree intent, and integrate the exact checked-out base-owner sync through existing safe transaction/landed authority as needed.
- mu/tools/executors/worktree_lifecycle.py -- Extend the existing landed-source native sync/terminal coordination only for the observed checked-out base owner and finished-reader release, keeping immutable ownership and finite completion claims.
- mu/tools/observability/pipeline_monitor.sh -- Release or redirect the raw-log follower away from completed carriers; keep active-lane logs visible and prevent terminal heartbeat/startup reacquisition.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py -- Real Git regressions for captured AD index/worktree preservation and automatic dirty/untracked checked-out base synchronization.
- mu/tests/tools/test_worktree_lifecycle.py -- Exercise landed-source automatic coordination and real finished-reader retirement without bypassing live-owner/open-writer holds or replay budgets.
- mu/tests/tools/test_pipeline_monitor_autofollow.py -- Real generated watcher regression for active-to-terminal release and terminal restart/heartbeat; preserve pinned/default monitor behavior.
- mu/docs/agents/WorktreeLifecycle.v0.md -- Document the implemented automatic preservation/sync/reader coordination and honest residual ownership only.
- reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md -- Native Phase A owns complete packet expansion; root supplies only external STUB.
- reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json -- Native indicator and candidate authority.
- reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_observed_blockers.json -- Native compact binding of the three existing source-backed blockers, exact predecessor evidence and proof limits; no new full-fleet census.
- reports/deferred/non_blocking/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_bridge_nonblockers.md -- Optional native nonblocking findings only.
- `mu/tests/tools/test_commit_executor_receipt.py`: authorize only the reproduced four TestDraftPRReadyBeforeMerge command-contract regressions caused by reading the fetched origin/dev merge tip; retain readiness/CI/merge ordering assertions.
- mu/tests/tools/test_executor_dispatch.py -- Reuse and validate the native repair of the11 demonstrated post-commit integration fixtures: fetched merge tip, safe checkout-sync handoff, separate staged/unstaged dirty inventory. Preserve review/CI/retry/ownership assertions and test the corrected command contracts before pre-push.
- TASKS.md -- tracker-sync authority. The 2026-09-23 tracker sync note for wave `workingrcx-fleet-closeout-recurrence-r3-2026-09-23` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Preserve and reuse R2 rather than redoing its implementation. Frozen source: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-closeout-recurrence-r2-evidence-2026-09-23/stopped_pre_push_candidate/manifest.json SHA256 2e583f29e8b0f5d5f6e3741b8abd37d49a734f278974b50be09ef9b1f48468df. R2 local commit9c82251a39e076bf0dbba67ede3f788f3568d73b is based on exact landed devd55d1ff7ec5009fc7884edd7f2ea57a143d18c54. Verify manifest hashes; reuse candidate/mu/ three tooling sources, four existing focused tests, the native test_executor_dispatch.py repair and lifecycle documentation. Only merge bounded relevant CHANGELOG/TASKS facts into current truth. Do not import old full packets, indicators, tracker notes, receipts, routing or authority; native Phase A/other producers must regenerate those. Preserve both old R1/R2 carriers, indices, histories and receipts unchanged.
2. Address the observed pre-push integration mismatch now included in scope. The eleven failing dispatcher post-commit fixtures expected the old HEAD/ff-only and HEAD-only dirty inventory commands. Current production correctly queries fetched origin/dev, delegates checkout synchronization to landed preservation, and reads index/worktree intent separately. The native repair adds distinct merge-tip assertions and separate dirty reads while preserving CI/review/lifecycle assertions. Review and validate that patch, repairing demonstrated in-file issues only; do not weaken correct production semantics to accommodate stale fixtures. One recovery validator hit its300second limit with discarded output; timing cause was not established. Use the declared full affected-file gate with per-test output/diagnostics if needed, not another unexplained timeout retry or timing increase. Run the complete affected dispatcher integration tests before expensive outer pre-push; do not claim native repair tests passed without results.
3. Bind the three captured defects to native compact evidence. Root already completed both PR1314 public pairs; do not run those or PR1313's consumed pairs again. All13orphan useful-work owners remain open despite11of13source folders relocating. Read source, journals and receipts rather than treating prior plans as success. No fresh fleet-wide census is needed for this code correction.
4. Finished reader: reproduce the generated raw-log watcher keeping or reacquiring a real tail on a terminal carrier within its one-hour recent-log window. Observe native terminal/ownership truth rather than classifying success from log text or PID absence alone. Release the reader promptly enough for native bounded closeout or redirect it to surviving evidence outside the target; keep last output available where practical and active-lane monitoring functional. Cover watcher heartbeat and cold restart on the same terminal lane. Do not whitelist all tails/readers in the generic safety guard, kill unrelated processes, modify historical receipts or increase/reset completion budgets. Historical rejecting PIDs are absent from native receipts; fresh matching-process evidence is corroboration, not a fabricated historical PID attribution.
5. Checked-out dev: reproduce the actual shape with PRIMARY on its founder feature branch and dev checked out in a separate linked sibling with retained untracked/dirty evidence. The current landed-source child always binds PRIMARY, while dirty verify-root handling skips the sibling. Automatically coordinate the exact base owner through existing landed-code, identity/lock-bound preservation transaction; never update a checked-out ref from another checkout, force/reset, drop unrelated stashes or overwrite WIP. Expose truthful per-owner success/HOLD so successful PRIMARY sync cannot conceal the still-behind base owner; uncertain/live/divergent owners remain preserved without reverting the merged PR.
6. AD inventory: reproduce the actual source84 path shape: HEAD absent, index contains added blob4c65aa2d6dd91f6dedd90ec79bbf90eb8c64f132, worktree absent; git status AD but HEAD-to-worktree diff empty. Include distinct index/worktree tracked intent in journal/stash preparation and exact restoration/HELD evidence. Exercise the observed transient deferred-report path plus ordinary mixed WIP through real Git and the shared native transaction/fleet admission. Do not edit Source84's existing PREPARED or HELD journals or infer missing code is covered. Original owner recovery remains consumed.
7. Use existing isolated fixture helpers and unique branch/process identities. Demonstrate each actual failure before correction, then the declared gate; preserve live-owner/open-writer, divergent checkout, changed identity, index/WIP and no-replay protections. Do not expand to hypothetical failure matrices or unrelated monitor/provider/refactoring changes.
8. Land through launch_wave.py/native Phase A/B/recovery/commit. Foreground verifies actual PRIMARY/separate-dev synchronization, protected WIP and carrier closeout after merge, then resumes existing row38 physical/useful-work/registration cleanup before Mu. Archived/moved is not integrated or fully deregistered. Never replay old public apply pairs, held journals or exhausted lifecycle claims.

## Constraints

- Root authors only this external STUB; native Phase A expands the full locked packet. All source/tests/staging/commit/push/merge are native-owned via launch_wave.py and dispatcher.
- All selected LLM roles Codex gpt-6-astra/max; commit providerless, pager Codex. Preserve polymorphic provider architecture; no Claude-owned edits.
- Preserve every historical operation/journal/status/budget/stash and all staged, unstaged, untracked, ignored and unmerged useful work. No replay, force/reset, bulk deletion or backup-only integration claim.
- Fifteen-file immutable allowlist and exact landed comparison commit. All same-wave evidence is regenerated; no root implementation, staging, commit, merge or gate bypass.
- At the first reported<=10% remaining quota, stop immediately even mid-wave. Do not finish tests/commit/merge/closeout. Preserve files/index/journals and do not automatically resume. Foreground checks each milestone; independent local watchdog remains required before launch.
- Preserve stopped Mu work and all unresolved useful-work owners. Remaining actual fleet cleanup precedes Mu; no new hypothetical prerequisite.

## Stop conditions

- Stop a particular mutation on identity/content/history/lock drift or live/uncertain ownership; preserve its precise owner/evidence, not reset/replay.
- If an observed correction truly requires another source boundary outside the frozen scope, report exact missing authority rather than patching outside it; do not manufacture hypothetical blockers.
- Do not relaunch or mutate stopped R1/R2 or import their review authority. Additional actual missing scope must be reported with exact evidence; no edits outside the allowlist or repeated knowingly unfixable passes.
- Immediate founder usage stop at<=10% remaining; no finish-current-step exception. Unknown quota pauses work.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_recovery_gate.py -k pipeline_monitor --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Real generated watcher releases a completed carrier and cannot immediately reattach through heartbeat/restart; active output remains functional and generic live-process/writer holds remain.
- Native landed-source postmerge path automatically reconciles the exact checked-out base owner as well as PRIMARY using safe transactions and exposes any remaining HOLD/behind state.
- Real AD index blob/worktree absence and mixed WIP survive native inventory, preparation and restore/HELD handling exactly; historical source/journal untouched.
- Required affected-file tests, fresh native review/CI/merge and actual preservation/sync/closeout evidence complete. All268task IDs/39parked obligations and immediate quota-stop policy remain; existing row38 remaining cleanup is next before Mu.
- The entire required test_commit_executor_receipt.py behavioral suite passes, with the four reproduced draft/readiness fixtures recognizing the actual fetched merge tip and all ordering assertions preserved. No receipt-chain scope exception, test skip or attestation bypass.
- The entire test_executor_dispatch.py integration suite passes with fetched-tip, landed-sync and separate index/worktree inventory semantics; retain CI/review/ownership safeguards. Do not hide the eleven actual regressions or claim an unproven timeout cause.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-fleet-closeout-recurrence-r3-2026-09-23`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`.
- TASKS.md authority: the 2026-09-23 tracker sync note for wave `workingrcx-fleet-closeout-recurrence-r3-2026-09-23` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-closeout-recurrence-r3-2026-09-23

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-closeout-recurrence-r3-2026-09-23`
- Active packet: `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/WorktreeLifecycle.v0.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tests/tools/test_worktree_lifecycle.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/worktree_lifecycle.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`
  - `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_observed_blockers.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-closeout-recurrence-r3-2026-09-23 --output reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_recovery_gate.py -k pipeline_monitor --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tests/tools/test_worktree_lifecycle.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/worktree_lifecycle.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`, `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_observed_blockers.json`, `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-closeout-recurrence-r3-2026-09-23.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-closeout-recurrence-r3-2026-09-23`
- Active packet: `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8f1a9066ef6986d79b761fdb6ff62dd28c851dbe8f646cdaa7c833a350b2b06c`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_recovery_gate.py -k pipeline_monitor --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tests/tools/test_worktree_lifecycle.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/worktree_lifecycle.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`, `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_observed_blockers.json`, `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`..
- Evidence handles:
  - `candidate_authority_receipt`: `.agent_bus-fleet-closeout-recurrence-r3-20260923/meta/candidate_authority_receipts/workingrcx-fleet-closeout-recurrence-r3-2026-09-23/commit-pre-supervisor.json`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_worktree_lifecycle.py`
  - `mu/tools/executors/worktree_lifecycle.py`
  - `reports/control_plane/workingrcx-fleet-closeout-recurrence-r3-2026-09-23_2026-09-23.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-closeout-recurrence-r3-2026-09-23.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
