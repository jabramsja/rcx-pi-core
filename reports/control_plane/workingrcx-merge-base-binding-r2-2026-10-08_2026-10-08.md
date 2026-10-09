# Restore the verified reviewed-base fix with explicit existing PR branch authority

Date: 2026-10-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-merge-base-binding-r2-2026-10-08
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 37074ed48b09ae90b7772abef8e6e5858c5821507fbdf3d5c88140cae61d9ed9
Purpose: Recover the approved R1 reviewed-base implementation unchanged and bind native handoff/commit entry to the existing PR branch for PR1332; preserve stopped R1 without replay.

## Scope

Only the protected merge review/base binding and its queue/resume/landing verification in commit_executor.py, existing two behavioral test modules and own governance. Preserve the existing durable at-most-one-request/held output and all prior review-retention semantics.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: preserve admitted review identity/base OID through protected intent and resume; verify exact base while OPEN and actual landed merge parents before completion. Keep helper/query changes narrowly necessary to that boundary.
- mu/tests/tools/test_commit_executor_local_review.py and mu/tests/tools/test_commit_executor_step14_autoresolve.py: existing actual production/native continuation/CLI tests, real disposable Git merge graphs and fake remote/model I/O. No new test module or broad glob gate.
- reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md, reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json, reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json, TASKS.md, CHANGELOG.md and own optional native nonblocker report.
- mu/tests/docs/test_growth_caps.py only for mechanical native generation, never manual cap changes.
- reports/deferred/non_blocking/workingrcx-merge-base-binding-r2-2026-10-08_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-08 tracker sync note for wave `workingrcx-merge-base-binding-r2-2026-10-08` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Use /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r1-approved-preserved/preservation.json and its restored tree as source authority. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r1-stopped-preserved/preservation.json and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r1-terminal-transport-diagnostic/branch-binding-diagnosis.json. Preserve all R1 state, indexes, handoffs, approvals, recovery and lifecycle budgets. Do not resume R1 or adopt its receipts.
2. Restore ONLY the three declared implementation files from the verified pre-entry R1 restored tree under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r1-approved-preserved/restored/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.scratch/worktrees/merge-base-binding-r1-20261008. Required SHA256: commit_executor.py eb7246db0cca9fd7eead9215f38da05ba0ccc4e61cf7336c239de1d70c7b043a; test_commit_executor_local_review.py 4f2503e7b89948ce04de3f4971f0f1673e20c5f6b88d5242e12f5d659334eacd; test_commit_executor_step14_autoresolve.py e2ae8196ddf3b5e1957d714df8d42cd2dc0e695fc826ccfc9c6d3ecf5792fd3b. Retain their bytes. This is preserved-source recovery with fresh review, not implementation reinvention.
3. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR #1332. Preserve that exact case-sensitive phrase existing PR branch in the canonical packet. FOUNDER_OVERRIDE:workingrcx-merge-base-binding-r2-2026-10-08. R1 described PR1332 but omitted the machine-required literal. Actual phase_b_executor._phase_b_target_branch_for_current_worktree must return the existing branch for this packet; a missing/mismatched actual handoff target_branch is a hold before commit. Never create a new wave branch from dev for this PR repair, rebind the comparison commit, or relax the allowlist.
4. Keep complete original review identity in version2 protected intent, OPEN base checks, actual ordered merge parents, local receipt/source/artifact checks, current-head cloud clearance, legacy/malformed evidence holds, actual native continuation and at-most-one request/completion behavior. R1 before evidence eight drift failures/859 controls and corrected952pass are historical, with all intermediate failures retained; do not label them fresh R2 results.
5. Run the declared existing two-module gate on the recovered candidate and save command/output/exit/timing/exact hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r2-validation. Hash the three files before and after. Prior952pass and R1 approvals do not approve this R2 candidate. Use the existing meaningful production/native reload/CLI/lifecycle regressions; no new test module, broad glob, checker changes or ANTICHEAT_OK additions.
6. Write own phase-scoped implementation evidence at reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json. Update existing rows38/40 and own CHANGELOG/packet/indicator only. Preserve the launcher's canonical normative packet and use its reserved clarification lane for observations; do not add arbitrary H2 sections or replace original authorization. Native indicator/cap generation and final staged approval remain outer owners. Avoid governance self-hash/final-byte claims from implementation time.
7. Preserve both unresolved Bot threads exactly: old queue thread PRRT_kwDOQvy8bs6qI-5e / comment PRRC_kwDOQvy8bs77IAg6 bodySHAff2c6b22b5f36ec3b2347da074a3be12739fe0643a6748f3cffb1fc883860fbc, and new base-binding thread PRRT_kwDOQvy8bs6qMIWE / comment PRRC_kwDOQvy8bs77NDtC bodySHAc161930ad5ed0dede0fa2aabca3885d88af3712087ef6828783c99c77f39b078. Their full one-comment Bot-only snapshots are in the saved040945Z payload. Native implementation performs no GitHub action. Conditional operator/pipeline disposition requires actual fixes/before-after proof, fresh final native approval, all required CI on the corrected head, and independent authenticated current-head GitHub clearance while the old addressed threads remain unresolved. Only then may these exact unchanged addressed threads be resolved individually; re-fetch complete evidence and require aggregate clearance before merge. Added/changed comments or findings require renewed assessment; no human action, blanket resolution, dismissal or deletion.
8. Retain the three earlier repaired test files byte-identical to678ca40: mu/tests/engine/test_mu_type.py SHA7e18fdba00fa23fdcbd2a0556ef77d34e40ad1f8301dde2854863843454d07da; mu/tests/l4_gates/test_stage0_vm_cutover.py SHA32c3349b6837ad90491cc0643a1393a49d3c202fc9551a6560839e83514b353f; mu/tests/tools/test_agent_prompt_contract_injection.py SHA51c8c2eebc8796f372e34188c86172de919db747e19f009f38879aac8861f0e8. Runtime, hosts, seeds, dispatcher, recovery_gate, lifecycle, launcher, hooks, role/config surfaces and the CI fixture remain read-only.
9. Keep the exact executor/two-test scope; launcher, dispatcher, Phase B, recovery, lifecycle, hooks, config, runtime, hosts, seeds and CI teardown fixtures remain read-only. Carry the precise row40 obligations for structured terminal transport/raw child-stream retention and branch selection: semantic existing-PR intent must be typed/bound rather than substring-dependent; admission must prove target branch and comparison HEAD before branch mutation. R1 root admission omitted that check. No guard or receipt reset is permitted.
10. Run launcher/dispatcher from this candidate checkout. At the commit boundary require actual handoff target_branch equal to the existing PR branch, HEAD descended from678ca40, exact allowed staged inventory and native current receipt. If automatic structured chaining stops after a valid final handoff, preserve raw result and all authority; any supported explicit commit entry retains fresh approvals/hooks and must first meet the branch check. Never re-run setup over a completed packet.
11. Preserve the CI fixture issue separately: R3 attempt1 passed13489tests but teardown of a disposable remote.git raised ENOTEMPTY; identical-head attempt2 passed all7checks. Surviving entry/writer was unobserved and fixture code was unchanged. No fixture suppression, repeated retry-until-green or out-of-scope test repair belongs here.
12. PR1331/1330/1329 and pausedPR1325/useful-work remain open. No physical APPLY plan or retired-folder replay, no new numbered prerequisite, no producer deduplicated-store integration claim. Report any postmerge routing hold separately from verified landing and PRIMARY sync.

## Constraints

- Authorized control-surface L4_ENABLER. Founder autonomous continuation and standing pipeline repair authorization apply. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR #1332. FOUNDER_OVERRIDE:workingrcx-merge-base-binding-r2-2026-10-08.
- Root authors config/tracking/diagnostics; native actors own source restoration, implementation, staging, commit, push, merge and conflict resolution. One mutation lane.
- Fresh native authority on original committed678ca40 using only the three verified R1 implementation files. Preserve both stopped R1 carriers/receipts/budgets without transfer or rearm.
- Exact case-sensitive existing PR branch intent must remain visible to the native selector. Verify actual generated handoff target and original comparison ancestry before any commit-entry branch step.
- Only the exact three source/test files and declared own governance may change. All adjacent executor/recovery/lifecycle/hook/config/runtime/host/seed surfaces stay read-only.
- Durable intent permits at most one protected merge mutation. Base drift and uncertain/incomplete evidence retain the original intent and native owner with genuine held output; no automatic rebinding or false completion.
- Only the two named unchanged addressed Bot findings have conditional proof-backed disposition after new-head independent clearance. New/changed findings need renewed assessment.
- No new numbered prerequisite, pausedPR1325 resumption, physical APPLY replay or broad cleanup completion claim.

## Stop conditions

- Stop on branch/PR/head mismatch, concurrent ownership, undeclared changes, altered preserved-test hashes, missing evidence or exhausted native recovery.
- Stop if safe reviewed-base/parent verification cannot fit the exact executor/two-test scope. Provide concrete evidence rather than broadening file globs or weakening authority.
- Retain holds without forged approvals, old packet/prompt/receipt rewrites, budget resets, finding suppression or administrative merge.
- No landing, PRIMARY sync, thread disposition, retirement, useful-work completion or producer integration claim without actual evidence.
- Hold before commit if the actual handoff omits or changes target_branch, or the candidate HEAD loses the reviewed678ca40 ancestry. Do not admit a new wave branch from dev.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`

## Acceptance criteria

- Before/after production proof demonstrates the reviewed-base drift defect in both review lanes and its correction with passing stable-base controls.
- The original admitted base survives durable intent and actual native continuation reload; changed or unavailable authority holds without re-request or completion.
- Actual merge-commit parent evidence binds completion to the reviewed base and exact head while allowing the moving post-merge base ref; unsupported evidence holds.
- Local receipts, cloud clearance, retained findings, bounded queue observation, native held output and at-most-once request/completion invariants remain intact.
- Final declared two-module gate passes; prior three repaired tests and all adjacent read-only surfaces retain their hashes.
- Fresh native approvals/hooks/CI/current-head independent review and exact addressed-thread disposition gate the same existing PR1332 landing.
- PRIMARY sync and subsequent PR/cleanup obligations receive separate truthful evidence.
- Recovered three source/test files match the verified R1 hashes; fresh R2 gate and native approvals bind current candidate.
- Actual handoff and commit entry preserve the existing PR1332 branch and reviewed parent before any branch mutation.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-merge-base-binding-r2-2026-10-08`.
- Governing packet: this file, `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`.
- TASKS.md authority: the 2026-10-08 tracker sync note for wave `workingrcx-merge-base-binding-r2-2026-10-08` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-merge-base-binding-r2-2026-10-08

## Non-normative review clarification

- Phase B restored only the three declared source/test files from the verified
  approved pre-entry R1 tree. All required SHA256 values match before and after
  the fresh R2 gate: **952 passed in 427.65s, exit 0** (429.436s wall time).
  The gate used the exact declared two-module command. Its command, output,
  timing and hashes are saved under
  `/Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/merge-base-binding-r2-validation`.
  Phase-scoped observations are in
  `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json`.
- The actual read-only call to
  `phase_b_executor._phase_b_target_branch_for_current_worktree` returns the
  existing PR branch `jabramsja/workingrcx-local-review-quota-r3-2026-10-05`.
  Local HEAD and comparison authority are
  `678ca40cfa00643a377a0902756540972738118a`; the ancestry check passes.
  The actual native handoff is still outer-owned and must carry that exact
  `target_branch` before commit entry. This observation does not approve a
  handoff, staged candidate, branch mutation or commit.
- Both preserved R1 manifests were verified offline: 97 approved and 118
  stopped restored entries. R1's eight drift failures/859 passing controls,
  intermediate failures, 952-pass final result and approvals remain historical.
  No old receipt, index, handoff, guard or recovery/lifecycle budget is adopted
  or reset. The three earlier committed test hashes are retained.
- The complete saved 040945Z Bot-only snapshots match both required comment
  body hashes. No GitHub action occurred. Fresh final native approval, required
  corrected-head CI and independent authenticated current-head clearance must
  precede conditional individual disposition of these exact unchanged findings;
  complete re-fetched aggregate clearance remains required before merge.
- Existing row40 retains typed existing-PR branch authority, admission before
  branch mutation, structured terminal transport/raw child-stream retention,
  and the separate unchanged CI fixture ENOTEMPTY observation. Native indicator
  and cap generation, final staged approval, hooks, landing and PRIMARY sync
  remain outer-owned. Other PR/useful-work obligations remain open; no physical
  APPLY, retirement, producer integration or broad cleanup completion is claimed.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-merge-base-binding-r2-2026-10-08`
- Active packet: `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`
  - `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-merge-base-binding-r2-2026-10-08 --output reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`, `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-merge-base-binding-r2-2026-10-08.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-merge-base-binding-r2-2026-10-08`
- Active packet: `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4017d0bab96729322066560d0ea6bbe69ea5ae25c5106f88eada11048283d86a`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`, `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08.md`
  - `reports/control_plane/workingrcx-merge-base-binding-r2-2026-10-08_2026-10-08_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-merge-base-binding-r2-2026-10-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
