# Verify historical local-review verdict consistency before fresh admission

Date: 2026-10-09
Status: Phase B (pre-supervisor pending, bridge-converged)
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-local-review-terminal-r4-2026-10-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: b0d72c3cd7cc240d2c07decd897defde5cf696d45352831d0528e46933109156
Purpose: Authorized same-owner control-surface L4_ENABLER. Preserve the tested PR1332 R2/R3 candidate, correct the reproduced native legacy receipt verdict inconsistency, and complete native landing.

## Scope

Bind compatible historical receipt outcome to retained native raw verdict and complete evidence before any fresh review; preserve all durable ownership and terminal recovery fences.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: correct legacy receipt/raw verdict consistency in _prior_local_review_stop before fresh reviewer admission. Retain canonical ownership, locking, all earlier terminal transport and compatible historical evidence.
- mu/tests/tools/test_commit_executor_local_review.py: actual historical native producer and public continuation regressions for receipt-only relabeling, missing/damaged/conflicting raw evidence and legitimate historical approval; preserve all existing test definitions and controls.
- mu/tools/executors/executor_dispatch.py, mu/tools/executors/recovery_gate.py and their two existing allowlisted tests: carry R2/R3 unchanged unless this exact producer-bound admission fix requires a narrowly justified adjustment. No unrelated recovery or budget changes.
- TASKS.md, CHANGELOG.md and own R4 packet/evidence/indicator/optional nonblocker. Carry all six existing R2/R3 packet/evidence/indicator files byte-exact as historical provenance. Existing growth-cap file only through native generation.
- reports/deferred/non_blocking/workingrcx-local-review-terminal-r4-2026-10-09_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r4-2026-10-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. This is an authorized control-surface L4_ENABLER. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR1332 at parentf36b982b8b45774cf68fc621acf0d9727d72e6d5. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r4-2026-10-09. Carry all14staged R2/R3 paths. Preserve exact existing PR branch and override forms for the native indexed reader, real Phase B selector and commit builder.
2. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r3-validation/root-legacy-negative-consistency-probe.py and its JSON result, /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r3-admission/terminal-review-evidence.json, and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r3-operator-hold.json. The BLOCKING operator finding is explicit admission input, not an optional appendix: no review or handoff may claim it resolved without reproducing and reporting its disposition against current source. R3 Phase B GO and3433tests did not clear this finding.
3. Reproduce the three cases first using the actual f36 _run_local_quota_review producer in isolated temporary Git/provider fixtures: relabel native-v1 ERROR/REQUEST_CHANGES receipt status and envelope to APPROVED/GO; additionally remove error; additionally relabel copied output. Leave original raw/prompt/diff artifacts unchanged. R3 source permits a second review with identical identity/request in all three cases. Preserve original test and diagnostic results. Do not edit real historical receipts or induce live provider failures.
4. Correct admission so compatible historical claimed approval must agree with retained native raw verdict and evidence provenance; receipt fields alone cannot erase a historical negative. Malformed, missing, conflicting, interrupted or damaged evidence must stop before another reviewer, generic recovery, learned remediation, backoff or merge. Use existing native parse/validation surfaces and bounded governed paths. Preserve the original bytes; do not manufacture fresh approval or rewrite old evidence.
5. Add meaningful production/public entry regressions for all three cases, raw verdict refusal/malformed/incomplete variants where applicable, and legacy-valid-approval positive control from the actual old producer. Preserve current-candidate identity, original evidence and zero added reviewer/recovery/remediation/merge calls for held cases. A genuinely corrected candidate must still receive a fresh review; unrelated identities and normal transients retain prior behavior. Do not solve the negative by rejecting every legitimate historical approval or weakening current canonical-owner checks.
6. Retain all R3 canonical ownership/serialization, symlink/path/storage hold, interrupted publication, cross-bus and empty-commit protections, original R2 terminal transport and every prior test definition. Preserve all six R2/R3 governance files exactly, Phase B source, adapter/model/hook settings, gate budgets/complete diagnostics, aggregate/queue/CI/ordered-parent/receipt/head/base guards and adjacent protected tests.
7. Run bounded focused serial controls before the full declared three-module gate. The full gate uses the supported four-worker worksteal runner and retains all three modules, selections and prior tests; record any failure honestly. Capture exact command/output/exit/timing and before/after hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r4-validation. Write own evidence at reports/control_plane/workingrcx-local-review-terminal-r4-2026-10-09_2026-10-09_implementation_evidence.json. Native actors own source/tests, generated caps/indicators, staging and landing; root does not self-stage or forge governance.
8. Early packet construction may be checked in a disposable index. The actual index is populated by the outer native pre-review preparation; verify the real indexed reader and builder after that stage and before handoff. Missing initial packet staging alone is not a reason to skip implementation or self-stage. Preserve same-PR target and comparison ancestry throughout.
9. Merge PRIMARY TASKS checkpoint SHA25667bb2913ea1e30f3eef718781723022daa0476c35cf7645725d5b630ec46003c into candidate history without losing either side. Preserve268canonical task IDs and44ordered owners. Row38 owns correction, landing, remaining PR/folder/useful-work and separate retention; row40 owns precise operator-finding delivery, envelope, branch admission, wait, delegation, lifecycle and postmerge automation follow-ups. R3 passed tests/review but was operator-held before commit; preserved work is not merged.
10. R3 execution owners are absent and lifecycle a33e5373 is ESCALATED with three completion attempts spent and source retained. Keep its available same-config continuation receipt unconsumed; it does not authorize resuming an unchanged candidate with a known defect. Never reset/replay old R2/R3 buses, checkpoints, raw verdicts, approvals, lifecycles or budgets. Use this fresh materially corrective packet and new native authority.
11. Retain the original complete-PR REQUEST_CHANGES evidence and three individually resolved Bot findings from f36; their disposition is not full-PR approval. Native authenticated current-request quota fallback remains subject to configured live roles, genuine corrected-head seven-check CI, read-only independent complete-PR review and exact aggregate/head/base identity. Provider refusal/unavailable capacity stops execution; no account/model switch, review-limit increase or capacity workaround.
12. Every reviewer emits exactly one final machine envelope with explicit disposition of the known legacy finding and direct source/command evidence. Preserve strict ambiguity rejection. Fresh exact final approvals precede commit, then fresh corrected-head CI and complete-PR review precede protected actual merge and separately verified PRIMARY sync.
13. After PR1332 actually lands and PRIMARY syncs, verify PR1331 state, PR1330 retained source/test coverage and native disposition, then useful PR1329 folder work. Deduplicated retention is a separate next wave on UUID93064AFA-816D-43E3-BCC9-8A514F8F3D7D. Preserve pausedPR1325, all recovery history and remaining physical/registration/useful-work owners. No old APPLY replay, archive purge, dev relocation or backup-setting change. If postmerge tooling lacks a same-wave apply_plan, report that routing HOLD separately; never fabricate a plan.

## Constraints

- Authorized control-surface L4_ENABLER under existing row38/row40. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r4-2026-10-09. One mutation lane; root owns configuration/tracking/recovery evidence and native actors own product source and landing.
- Keep exact parentf36b982b8b45774cf68fc621acf0d9727d72e6d5 and existing PR1332 branch. All six old R2/R3 governance files remain byte-exact. Do not broaden into runtime, seeds, hooks, adapters, launcher, model configuration or backup settings.
- Fresh correction addresses a reproduced source defect. Never relabel a negative verdict as approval, reuse consumed authority, blanket-resolve findings, suppress failing tests, use admin merge or create persistent internal recovery archives.

## Stop conditions

- Hold on wrong head/branch/base, concurrent mutation, undeclared change, unresolved known legacy evidence conflict, missing final indexed authority, refusal/capacity or quota stop, or exhausted recovery. Initial unstaged newly rendered packet is handled by outer pre-review staging as described above.
- If necessary source changes exceed this boundary, retain exact evidence and return required admission; do not silently widen scope or weaken safeguards.
- No commit without fresh exact approval and the correct existing PR target; no merge without corrected-head CI, independent complete-PR review and aggregate clearance. Preserve each original negative verdict and all outstanding owners.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py --tb=short`

## Acceptance criteria

- All three actual legacy-producer receipt-relabeling cases are reproduced before correction and stop before a second review afterward, including public continuation with unchanged raw negative evidence and identical candidate/request.
- Genuine historical approval and corrected-candidate positives work without laundering negative evidence; all existing ownership, transport, interruption, storage, identity and unrelated recovery controls remain. Full declared three-module gate and native checks pass.
- Known operator finding receives explicit source-bound review disposition. Actual indexed packet/builder preserve the existing PR branch, comparison ancestry and all six historical governance files. Fresh native approval, corrected-head CI and full-PR review precede actual merge and separately verified PRIMARY sync.
- TASKS and evidence preserve268task IDs/44ordered owners and distinguish preserved, tested, approved, committed, landed and retired. Folder/PR/retention and pausedMu obligations remain accurately open.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-local-review-terminal-r4-2026-10-09`.
- Governing packet: this file, `reports/control_plane/workingrcx-local-review-terminal-r4-2026-10-09_2026-10-09.md`.
- TASKS.md authority: the 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r4-2026-10-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r4-2026-10-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-local-review-terminal-r4-2026-10-09`
- Active packet: `reports/control_plane/workingrcx-local-review-terminal-r4-2026-10-09_2026-10-09.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-terminal-r4-2026-10-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09.md`
  - `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09_implementation_evidence.json`
  - `reports/control_plane/workingrcx-local-review-terminal-r3-2026-10-09_2026-10-09.md`
  - `reports/control_plane/workingrcx-local-review-terminal-r3-2026-10-09_2026-10-09_implementation_evidence.json`
  - `reports/control_plane/workingrcx-local-review-terminal-r4-2026-10-09_2026-10-09.md`
  - `reports/control_plane/workingrcx-local-review-terminal-r4-2026-10-09_2026-10-09_implementation_evidence.json`
  - `reports/deferred/non_blocking/workingrcx-local-review-terminal-r4-2026-10-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r2-2026-10-09.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r3-2026-10-09.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r4-2026-10-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->