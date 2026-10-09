# Review and land the preserved protected-merge continuation repair on PR1332

Date: 2026-10-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-merge-queue-review-r3-2026-10-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 67fcb30101030279c9fced10344a267b976d2164d8e89ec0e8bd5d7b80a39997
Purpose: Recover the exact tested R2 source under fresh native review after a terminal staged-review inventory failure; complete existing PR1332 without replaying an unprepared checkpoint.

## Scope

Protected Step15 queue observation, durable merge-request intent and native held/resume output within commit_executor.py, exact formal-review metadata, the two existing behavioral test modules and fresh governance. Adjacent dispatcher/recovery/lifecycle surfaces are read-only proof inputs.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: bounded protected-merge observation, its durable continuation/intent and narrowly necessary native held/output/resume behavior, plus the preserved exact formal-review wrapper classification. No unrelated executor refactor.
- mu/tests/tools/test_commit_executor_local_review.py and mu/tests/tools/test_commit_executor_step14_autoresolve.py: actual existing modules for deterministic multi-invocation/CLI-dispatch boundary proofs, queue and finding controls. No new test module or glob gate.
- reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md, reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json, reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json, TASKS.md, CHANGELOG.md, and own optional native nonblocker report.
- mu/tests/docs/test_growth_caps.py only for mechanical native generation, never a manual cap increase.
- reports/deferred/non_blocking/workingrcx-merge-queue-review-r3-2026-10-08_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-08 tracker sync note for wave `workingrcx-merge-queue-review-r3-2026-10-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r2-stopped-preserved/preservation.json and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r2-checkpoint-diagnostic/checkpoint-reproduction.json. Read the restored R2 implementation evidence and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r2-validation/private-attr-repair-20261008T013405Z/gate.json. Snapshot337faf8fc20d6d0b4493d4c31e49c2f1302157b122b2b37b7c1eb10c5ea0cd4d restores113files. All prior packets, phase approvals, native state, terminal receipts, indexes and budgets remain historical and unchanged. Parent and remote PR1332 must remain bb837 before launch.
2. Native implementation recovers ONLY mu/tools/executors/commit_executor.py, mu/tests/tools/test_commit_executor_local_review.py and mu/tests/tools/test_commit_executor_step14_autoresolve.py from /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r2-stopped-preserved/restore-verify with their original absolute-path hierarchy. Expected SHA256 respectively58ed6299ec30ccbe6d7852ba9550ba5f43f47c86bda4da014579fb0dfd0bf596, de154df8a86a55699f1989a627c62ee8b2c83609dccc4a7d85d378e197eceb4c, ce96be34c45be313898e4cbc8cc8eab9209df65d2e633cb5d9cfdd13618f9e7e. Verify before applying; preserve valid guarded public handoff_sha and write_continuation_record seams and all original assertions. The recovered implementation already contains the full repair; avoid unnecessary source churn. Generate fresh R3 governance; never copy an old approval, packet, tracker note, indicator or current-authority claim.
3. Inspect preserved before/after evidence in /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r2-validation: parent-original-defects.json proves original parent7failed2passed with passing immediate-merge controls; r1-before-intent-integration.json proves repeated requests across real R1 continuation reload; candidate-held-native-command-final-3.json and operator-durable-continuation-check.json prove real held/CLI/dispatcher behavior at their recorded source versions. Label their historical source hashes accurately. Verify the final recovered source retains these behaviors, and rerun the declared gate on the fresh candidate. Reproduce additional focused cases only if reconciliation or review reveals a new concern; fake I/O proofs do not claim live GitHub actions.
4. Persist a minimal, durable, identity-bound protected merge intent in the valid native continuation before the merge side effect, using existing atomic/continuation helpers as appropriate. Bind the exact owner/wave/handoff, repository/PR, head, source branch and target base. Preserve all existing receipt, request and continuation authority. Only the initiating invocation may issue the one protected merge request. A subsequent invocation or interruption with an uncertain request outcome must observe the same exact PR or hold; never send another merge automatically. Failure to durably record intent prevents mutation. Invalid/corrupt or mismatched intent fails closed without inherited merge/cleanup authority. Do not fabricate approval records or change an old native wave.
5. An unresolved accepted/uncertain merge observation must return a real native held result through the public commit output contract, with exit/status/decision accurately preserved by the unchanged dispatcher. Existing commit main and _classify_commit_executor_result support held; prove the actual JSON and normal output paths including possible diagnostic prefixes. No generic status error that enters recovery, no prose-only no-retry promise and no success/COMMIT_GO collapse. Scope any necessary output adjustment to this hold behavior. Test that neither standalone recovery nor dispatcher recovery/remediation is invoked for it. Adjacent dispatcher, recovery_gate and worktree_lifecycle are read-only; inspect their actual code to prove carrier/continuation preservation and resumed completion. Stop with concrete evidence if the exact scope cannot safely express this.
6. Exercise resume through actual continuation write/read/load and production post-commit flow in a new invocation/result, not only two calls retaining an in-memory observation dictionary. Test queue-to-held-to-landed with exactly one total merge mutation and one verified completion; repeated holds; interruptions before and after the side effect or uncertain command outcome; write failure; corrupt/mismatched intent; changed head/branch/base/repository; terminal closed state; transient/persistent query failures; deadline; native held output classification and no recovery. Use deterministic clocks and fake remote/model I/O. Existing receipt and review authority must survive semantically, while the native continuation gains only the justified new state. Preserve unrelated negative controls and original assertions; update the old byte-unchanged continuation assertion only where the authorized durable intent now requires it.
7. Retain and validate the R1 bounded exact-head polling, immediate and queued success, identity/complete-review guards and exactly-once post-merge completion, including closeout-exception behavior. Retain the exact complete known connector/Bot COMMENTED formal wrapper as metadata bound to its own reviewed commit. Unknown/mixed/quoted/badge prose, invalid author/state, substantive bodies and real threads remain blocking. Metadata never approves a head or resolves a finding. CHANGES_REQUESTED, humans, incomplete pages and stale/wrong-head clearance remain blocked. Use the actual saved bb837 review/thread payload, not an abbreviated invented wrapper.
8. The P1 thread PRRT_kwDOQvy8bs6qI-5e / comment PRRC_kwDOQvy8bs77IAg6 remains unresolved and blocking. Read its full saved body in /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/review-control-r1-review-wait-diagnostic/review-state-235009Z.json. The conditional post-validation sequence is explicit: first verify the actual fix, before/after proof, fresh native final approval, current-head CI and an independent authenticated GitHub review signal on the corrected head while the old thread remains unresolved; that independent signal is distinct from aggregate clearance and cannot be wrapper metadata. Then the operator/pipeline may resolve only this exact unchanged Bot-only addressed thread. Finally re-fetch complete review/thread evidence and require aggregate current-head clearance before protected merge. Any added/changed body/comment/finding requires renewed assessment. No blanket resolution, human-thread action, review dismissal or deletion. Native implementation performs no GitHub action; if native disposition is unavailable, retain the hold and report the exact existing row40 automation obligation.
9. Keep the three previously repaired test modules byte-identical to bb837: mu/tests/engine/test_mu_type.py SHA2567e18fdba00fa23fdcbd2a0556ef77d34e40ad1f8301dde2854863843454d07da; mu/tests/l4_gates/test_stage0_vm_cutover.py SHA25632c3349b6837ad90491cc0643a1393a49d3c202fc9551a6560839e83514b353f; mu/tests/tools/test_agent_prompt_contract_injection.py SHA25651c8c2eebc8796f372e34188c86172de919db747e19f009f38879aac8861f0e8. Runtime, hosts, seeds, loader/templates, recovery_gate, dispatcher, lifecycle, launcher, hooks, configs and CI snapshot fixture remain unchanged.
10. Run the declared two-module gate on final R3 source, including public-seam integrity and the continuation/CLI boundary controls already in those modules. Preserve exact commands, output, status and source hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-queue-review-r3-validation. The 855passing R2 gate is historical evidence, not a new R3 receipt. No checker changes, allowlist expansion, ANTICHEAT_OK additions or hook bypass.
11. Write reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json as phase-scoped observations. Generate honest R3 tracker/packet/indicator content without binding implementation-time governance hashes as final authority. Fresh native receipts must bind later staged governance. Record the stopped R2 checkpoint failure and this exact recovery. Update existing row38 and row40; no new numbered prerequisite. Pending-review re-request/no_action, recovery feedback/scope, broad structured transport, CI snapshot quiescence, conditional finding disposition, task-ID-only APPLY routing and producer dedup integration remain separately owned where unresolved.
12. The new checkpoint defect is read-only context: the Phase B pre-review package preparer retains supplied candidate paths, staging can remove an added-then-deleted optional nonblocker report, and the private-attribute index snapshot then refuses that absent path; run_phase_b refuses unprepared resume. Existing row40 must own a precise future correction to reconcile actual staged inventory after native preparation while preserving real staged deletions, exact scope, index/worktree identity, prepared-authority binding and fresh review. Include generated add/delete report, genuine tracked deletion, unstaged/out-of-scope drift and interrupted-preparation tests. This wave does not edit Phase B/launcher code, delete state, manufacture prepared authority, consume the old terminal receipt or bypass owed review.
13. This auxiliary repair creates no physical APPLY plan and replays no retired-folder action. PR1331/1330/1329 and paused PR1325/useful-work obligations remain open until proven. Report any actual postmerge APPLY routing hold separately from landing and PRIMARY sync; never manufacture a cleanup plan. Preservation-producer dedup integration remains separately owned.

## Constraints

- Authorized control-surface L4_ENABLER; founder autonomous continuation and standing pipeline-bug-fix authorization apply. The existing PR branch is jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR #1332. FOUNDER_OVERRIDE:workingrcx-merge-queue-review-r3-2026-10-08.
- Root authors config/tracking/diagnostics; configured native actors own source/test implementation, review, staging, commits, push, merge and conflicts. One mutation lane with current live roles.
- Fresh exact-scope wave from CI-green bb837; preserve stopped R1 and R2 candidates, checkpoints and phase approvals as historical evidence only. No receipt transfer, budget reset or old-state rearm.
- Only the exact three source/test paths plus declared native governance may change. Adjacent dispatcher/recovery/lifecycle code is read-only. Stop if safe held/resume semantics require broader authority.
- At most one protected merge mutation per bound intent across continuation/interruption. A queue hold retains the carrier, never grants remediation or claims landing; native held status must survive actual output/dispatcher boundaries.
- Only the named unchanged addressed P1 may receive conditional proof-backed operator/pipeline disposition after independent current-head review. Native implementation performs no GitHub mutation.
- No runtime/host/seed change, new numbered prerequisite, paused PR1325 resumption, broad cleanup claim or physical APPLY replay.

## Stop conditions

- Stop on branch/PR/head mismatch, concurrent ownership, undeclared source edits, altered preserved-test hashes, missing evidence or exhausted native recovery.
- Stop if the durable intent/held output/resume invariant cannot be safely expressed inside commit_executor.py and the two existing test modules; provide actual code/reproduction evidence instead of broadening a glob.
- Retain every native hold without forged approvals, locked packet/prompt rewrites, budget resets, finding suppression or administrative merge.
- Do not claim landing, PRIMARY sync, thread disposition, retirement, useful-work completion or producer dedup integration without actual evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`

## Acceptance criteria

- Native implementation recovers the exact three tested R2 source/test files from verified snapshot337faf8f under fresh authority; old R1/R2 carriers, indexes, checkpoints and approvals stay unchanged.
- Historical isolated before/after proof for both original queue/formal-wrapper defects and repeated held requests remains hash-bound and correctly labeled; fresh current-candidate tests verify retained behavior.
- Durable identity-bound intent prevents repeated merge mutations across real continuation reload and interruption; finite holds preserve the carrier and explicit review authority.
- Actual commit output is classified held/COMMIT_HELD with a successful hold exit, never recovery or a false merge success; standalone and dispatcher boundaries are exercised.
- Exact-head landing enters completion once; all terminal/mismatched/corrupt/timeout/retained-finding controls hold without premature cleanup.
- Exact formal-wrapper metadata grants no approval; real findings remain blocking until explicitly verified and disposed.
- Final declared two-module gate passes, prior three repaired tests remain byte-identical, and only exact allowed files change.
- Existing PR1332 lands only after fresh native approvals/hooks/CI/current-head review and exact finding disposition, with truthful PRIMARY sync and remaining obligations.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-merge-queue-review-r3-2026-10-08`.
- Governing packet: this file, `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`.
- TASKS.md authority: the 2026-10-08 tracker sync note for wave `workingrcx-merge-queue-review-r3-2026-10-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-merge-queue-review-r3-2026-10-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-merge-queue-review-r3-2026-10-08`
- Active packet: `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`
  - `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-merge-queue-review-r3-2026-10-08 --output reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`, `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-merge-queue-review-r3-2026-10-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-merge-queue-review-r3-2026-10-08`
- Active packet: `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6085aa7cc79445735b74f80713f95081a3427319b773a5125bc4f6b812d2d670`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`, `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08.md`
  - `reports/control_plane/workingrcx-merge-queue-review-r3-2026-10-08_2026-10-08_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-merge-queue-review-r3-2026-10-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
