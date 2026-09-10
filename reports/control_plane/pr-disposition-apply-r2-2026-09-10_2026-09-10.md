# PR Disposition Apply R2

Date: 2026-09-10
Status: Phase B (locked, implementing)
Task: [PR-DISPOSITION-APPLY]
Wave ID: pr-disposition-apply-r2-2026-09-10
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 1a8360e496e599dcd70b3f71c6bf47041645f8db96791d11af32cb2a7a202c71
Purpose: Use the reviewed fixed-set executor landed in PR #1280 to close exactly the eight governed stale PR objects, preserve every stale head and retained reconstruction obligation, retain durable no-replay intent evidence across carrier cleanup, emit eight semantic receipts, and make fleet cleanup next when no HOLD occurs.

## Scope

Apply the landed fixed-set executor, retain its common-git-dir intents, record eight exact receipts, synchronize TASKS, and otherwise change only this wave's authorized carrier branch/PR lifecycle; never mutate stale heads, fleet paths, or unrelated GitHub state.

Files and surfaces in scope:

- TASKS.md
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_2026-09-10.md
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1196.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1197.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1203.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1210.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1211.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1212.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1213.json
- reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1219.json
- reports/l4_wave_indicators/pr-disposition-apply-r2-2026-09-10.json
- reports/deferred/non_blocking/pr-disposition-apply-r2-2026-09-10_bridge_nonblockers.md (optional only for a genuine nonblocker)
- TASKS.md -- tracker-sync authority. The 2026-09-10 tracker sync note for wave `pr-disposition-apply-r2-2026-09-10` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Use the executor's fixed durable intent namespace under the repository common Git directory: rcx_pr_disposition_operations/pr-disposition-executor-enabler-r1-2026-09-09/pr-<number>.json. Retain those exclusive-created, fsynced intents across carrier commit, merge, and cleanup; do not delete them while any receipt or conditional reconciliation remains authoritative.
2. For the initial attempt run exactly: python3 mu/tools/executors/pr_disposition_executor.py apply --manifest reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json --comparison-commit 2b4218dc7c3e6f3e3d688dc6773d1777071529ee --repository jabramsja/rcx-pi-core --receipts-dir reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts --repo-root .
3. If and only if that process is interrupted, invoke the exact same public apply command as reconciliation entry. Existing intent/receipt authority must prevent another terminal callback: perform only fresh remote reads and emit CLOSED_RECONCILED when exact closed-not-merged/head-preserved proof exists, otherwise emit HOLD_ACTION_OR_POSTVERIFY or the executor's applicable HOLD. Never retry or replay a consumed or ambiguous close mutation.
4. Run the semantic verify evidence command and require the literal fixed set 1196, 1197, 1203, 1210, 1211, 1212, 1213, and 1219 exactly once each.
5. Synchronize TASKS to record PR #1280 merge 2b4218dc7c3e6f3e3d688dc6773d1777071529ee, preserved stopped Apply R1 packet SHA-256 9da030c442e6d1ff5201b13ae96b9648ca3cb782d410343b19909881e78bf754 with zero remote mutation, the exact R2 outcome, #1219 28081acd74c549a7afd4292351b214228d45f451 and #1203 4c466d1001b838e69ce141801fbbbe35f410d466 reconstruction evidence, #1211 10d157c4eb5b667b07006686fea86d88af268646 and #1210 b846d2e93be9ffbd3e25b30c1b7983ceb52c4ae7 supersession evidence, and either fleet builder NEXT on no-HOLD or reconciliation NEXT on a real HOLD.
6. After semantic verification, let the authorized providerless pipeline commit/push this R2 carrier branch, create and merge only this wave's PR, and remove only this R2 carrier. Land only TASKS, the generated packet, eight receipts, the indicator, and an optional genuine nonblocker report.

## Constraints

- The only external mutation against the eight stale targets is closePullRequest for their exact manifest node IDs; never merge/reopen/comment/edit/label/review/lock those PRs, or delete/rewrite/push their head/base refs, branches, commits, repositories, or associated worktrees.
- The normal providerless pipeline may commit and push only jabramsja/pr-disposition-apply-r2-2026-09-10, create and merge only its apply PR, and remove only its clean R2 carrier after merge. This authority never extends to a stale target head or fleet worktree.
- Common-git-dir intent files are durable operational evidence outside the staged candidate allowlist. Carrier cleanup must retain them; tracked semantic receipts and TASKS are the landed evidence surface.
- Use only the committed manifest and fixed executor in #1280 ancestry; do not edit source code, regenerate target authority, or mutate fleet paths.
- All model-bearing roles and pager remain Codex gpt-5.6-sol ultra; commit remains providerless.
- Do not investigate or fix nonoccurring edge cases or nonblockers.

## Stop conditions

- Stop the shared batch only when the executor emits an actual HOLD, contract failure, or remote drift. Preserve intents/receipts and route to reconciliation; never replay consumed or ambiguous authority.
- Stop if the pipeline attempts to remove durable common-git-dir intents, mutate a stale target head/ref/worktree, or use carrier lifecycle authority outside the R2 branch and R2 PR.
- Do not stop for style, optional-report absence, stale wording, or any nonblocking issue unrelated to the exact apply outcome.

## Validation gates

- evidence_command: `python3 mu/tools/executors/pr_disposition_executor.py verify --manifest reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json --comparison-commit 2b4218dc7c3e6f3e3d688dc6773d1777071529ee --repository jabramsja/rcx-pi-core --receipts-dir reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts`

## Acceptance criteria

- The apply and verify commands complete over exactly eight canonical receipts bound to the #1280 manifest/comparison commit, with durable fixed-namespace intents retained across carrier cleanup.
- Every CLOSED receipt proves closed-not-merged state and the exact original head repository/ref/SHA; interrupted execution reconciles without mutation replay, and any actual HOLD is preserved for the conditional lane.
- TASKS preserves exact #1219/#1203 reconstruction and #1211/#1210 supersession evidence and advances to fleet builder on all-complete/no-HOLD, or to conditional reconciliation only for a real HOLD.
- Independent review and pre-commit return GO/COMMIT_GO, the authorized R2 carrier alone completes providerless commit/push/PR merge/cleanup, and no stale target branch/ref/worktree or fleet path is changed.

## Grounding / Authorization

- Task: [PR-DISPOSITION-APPLY]; wave id `pr-disposition-apply-r2-2026-09-10`.
- Governing packet: this file, `reports/control_plane/pr-disposition-apply-r2-2026-09-10_2026-09-10.md`.
- TASKS.md authority: the 2026-09-10 tracker sync note for wave `pr-disposition-apply-r2-2026-09-10` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr-disposition-apply-r2-2026-09-10

## Non-normative review clarification

This clarification does not replace, reorder, or amend the native launcher contract above. It makes explicit the timing and receipt authority of the tracker-authorized `post_gate_contract_sweep` for existing Work items 1 and 6, Constraints 2 and 3, Stop condition 2, and Acceptance criteria 1 and 4.

The semantic verification required before Work item 6 is a pre-cleanup gate, not the terminal completion gate. After the authorized providerless pipeline has merged this wave's R2 PR and removed only the clean R2 carrier, it must perform the existing `post_gate_contract_sweep` from the landed revision. That post-cleanup sweep reruns the exact `evidence_command` from `## Validation gates` and again requires the literal fixed set 1196, 1197, 1203, 1210, 1211, 1212, 1213, and 1219 exactly once each.

Immediately before cleanup, the carrier-lifecycle record captures the resolved R2 carrier target and a SHA-256 digest for each of the eight exact fixed-namespace common-git-dir intent files. The post-cleanup sweep re-resolves the repository common Git directory, requires all eight intent files to remain present with identical digests and receipt bindings, and uses fresh read-only provider observations to require each canonical receipt's closed-not-merged state and exact original head repository/ref/SHA. Its cleanup observation must show that the removed branch/ref/worktree was only this wave's R2 carrier and that no stale-target ref, head, or associated worktree changed.

The authoritative terminal receipt is the durable `post_gate_contract_sweep` result in the providerless pipeline's existing terminal run record, bound to wave `pr-disposition-apply-r2-2026-09-10` and the merged R2 commit SHA; it records the second verifier result and fixed set, every intent's before/after digest and binding result, the fresh stale-target state/head tuples, and the resolved carrier cleanup target/result. This is process evidence, not a new tracked packet artifact. Wave completion and fleet-builder NEXT remain forbidden until that post-cleanup receipt is complete and passing. Any missing field, failed check, or mismatch is an actual HOLD under the existing contract: preserve intents and receipts, route to reconciliation, and never replay apply or advance fleet cleanup.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr-disposition-apply-r2-2026-09-10`
- Active packet: `reports/control_plane/pr-disposition-apply-r2-2026-09-10_2026-09-10.md`
- Indicator artifact: `reports/l4_wave_indicators/pr-disposition-apply-r2-2026-09-10.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_2026-09-10.md`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1196.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1197.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1203.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1210.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1211.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1212.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1213.json`
  - `reports/control_plane/pr-disposition-apply-r2-2026-09-10_receipts/pr-1219.json`
  - `reports/l4_wave_indicators/pr-disposition-apply-r2-2026-09-10.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
