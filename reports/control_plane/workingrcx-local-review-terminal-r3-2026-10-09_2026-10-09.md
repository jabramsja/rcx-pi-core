# Keep native local-review stops bound across governed bus changes

Date: 2026-10-09
Status: Phase B (locked, implementing)
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-local-review-terminal-r3-2026-10-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: d95a430c11f033bb3f3d638e35028f163c74d19bcc172428f57d4a918de05358
Purpose: Authorized control-surface L4_ENABLER under founder autonomous cleanup and landing direction. Carry the reviewed PR1332 local-review terminal candidate and fix its reproduced active-bus admission gap, then complete native landing.

## Scope

Durable failed-candidate local-review admission across governed bus changes, preserving the retained terminal transport and recovery fences, with production-boundary regression coverage and own governance.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: retain R2 local-review terminal transport and fix failed-candidate admission so selecting another governed bus cannot grant a new review for the same failed identity. Use canonical durable native evidence and bounded lookup; keep original negative receipts immutable and do not reuse them as approval.
- mu/tools/executors/executor_dispatch.py and mu/tools/executors/recovery_gate.py: retained R2 producer-bound terminal/retry fences. Further changes only if needed for this same admission boundary. Preserve all unrelated transient behavior and the existing strict Phase B terminal parser.
- The three existing allowlisted test modules: production/public reentry, direct/surface/chained retry controls and actual configured adapter fixtures. Add the bus-change regression and corrected-candidate/foreign-identity/tamper/interruption controls needed for the chosen durable binding; preserve all existing tests.
- TASKS.md, CHANGELOG.md and own R3 packet/evidence/indicator/optional nonblocker. Carry the three existing R2 packet/evidence/indicator files byte-for-byte as historical candidate provenance. Existing growth-cap file only through native generation.
- reports/deferred/non_blocking/workingrcx-local-review-terminal-r3-2026-10-09_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r3-2026-10-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. This is an authorized control-surface L4_ENABLER. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR1332 at parentf36b982b8b45774cf68fc621acf0d9727d72e6d5. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r3-2026-10-09. Retain the complete staged R2 candidate; do not discard, unstitch or replace its tested behavior. Preserve these exact existing PR branch and override forms in the indexed packet. Check the actual indexed reader, real Phase B branch selector and commit builder before expensive gates and after final reporting changes.
2. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r3-admission/terminal-review-evidence.json and cross-bus-negative-reproduction.json. Exact source boundaries, supervisor raw/prompt hashes, two advisory negative messages and an independent isolated reproduction are retained there. The parser correctly refused differing envelopes, so they are evidence rather than an accepted supervisor receipt. Do not edit or pick one of those messages to create authority.
3. Reproduce the precise gap first with a bounded targeted fixture/probe, using the actual native local-review producer and production/public continuation: same-bus resume stops, but another active bus returns no prior stop and invokes the reviewer again for the same head/base/diff/repository/PR/request. Root proof shows review_calls2, identity/request/original-evidence unchanged and zero merge/remediation calls. Initial reproduction need not rerun unrelated full modules; the full declared gate is required after correction.
4. Make failed-candidate admission survive governed bus changes before provider entry, generic recovery, learned remediation, backoff or merge. Bind the stop to the complete native candidate/request identity using durable canonical ownership rather than the selected namespace alone. Retain original evidence, including existing compatible receipts and interrupted STARTED attempts. Historical negative evidence can enforce a stop; it cannot supply fresh approval. Keep the design bounded and inside the declared source boundary; no new remediation subsystem or broad filesystem trust.
5. Prove zero additional reviewer/recovery/remediation/merge calls for same failed input when switching to a fresh governed bus, including negative findings and configured refusal/capacity/malformed/incomplete outcomes as appropriate. Preserve ordinary unrelated transient recovery and exact corrected-candidate positive control with fresh review. Cover foreign identities, damaged evidence and interruption/concurrency where required by the chosen persistence boundary. Isolate provider/GitHub/process effects, use temporary Git fixtures and existing native writers; no live provider failure induction or test-only production bypass.
6. Preserve the R2 complete terminal transport and its3,327passing tests, provider provenance, native CLI and direct/surface/chained dispatcher controls, evidence hashes, empty-commit stop, and protected-merge continuation behavior. Keep pytest gate budgets/diagnostics, Phase B source, original gate/receipt/identity/aggregate/queue/ordered-parent/CI guards and all adjacent protected tests unchanged outside this exact admission fix.
7. Run the declared full three-module gate and all required native checks after correction. Capture exact command/output/exit/timing and before/after source hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r3-validation. Write own implementation evidence at reports/control_plane/workingrcx-local-review-terminal-r3-2026-10-09_2026-10-09_implementation_evidence.json. Distinguish implementation-time snapshots from subsequent generated governance; do not present historical tracker/packet hashes as final staged authority. Native actors own source/tests, staging, generated caps/indicators, supervisor receipts, commit/push/merge/conflicts.
8. Synchronize the updated PRIMARY TASKS checkpoint SHA256bbdfc59052379befdcdd956f97b3bdef4029c2fd894247b509a13e6499bc87a6 into candidate history without erasing either side. Preserve268canonical task IDs and44ordered queue owners. Row38 owns this correction, landing, remaining PR/folder work and retention; row40 owns recorded output-envelope, branch/packet admission, wait/adjudication, delegation feedback, lifecycle/checkpoint and postmerge routing followups. R2 passed tests and Phase B review but stopped before commit. Keep its three historical governance files byte-for-byte and retain all stopped raw output/buses/receipts/budgets.
9. Retain the original full-PR REQUEST_CHANGES receipt in .agent_bus-targeted-gate-budget-r2-20261009 and all three individually resolved Bot findings. Their original independent adjudication and exact comment bodies remain preserved; those resolutions are not complete-PR approval. Existing native authenticated current-request code-review quota fallback remains authorized with configured Codex/gpt-6-astra/max read-only review, all7fresh CI checks and exact full-PR/head/base identity. No fabricated clearance or approval receipt.
10. Every reviewer must emit exactly one final machine envelope, with preliminary commentary outside envelope markers and direct file/function/command-output support for causal claims. Preserve strict differing-envelope rejection; do not change adapters, prompts, hooks or model settings to accept ambiguity. A returned negative result remains negative and must be addressed through native governance.
11. After actual PR1332 landing and PRIMARY sync, verify PR1331 disposition and PR1330 landed source/test coverage plus native disposition, then complete useful PR1329 folder-enabler work through fresh authority. Deduplicated recovery retention remains a separate next scope using UUID93064AFA-816D-43E3-BCC9-8A514F8F3D7D. Preserve pausedPR1325 and all physical/registration/useful-work obligations; no historical APPLY replay, live archive purge, dev relocation or backup-setting changes.
12. R2 execution owners are absent and lifecycle f471c43a is ESCALATED with source retained and three consumed completion attempts. Never replay/reset the stopped R2 bus, checkpoint, receipt or lifecycle. Use only this fresh packet and current generated authority. If postmerge tooling demands a same-wave apply_plan, record its routing HOLD separately from actual merge/sync; never fabricate a plan.

## Constraints

- Authorized control-surface L4_ENABLER under existing row38/row40. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r3-2026-10-09. One mutation lane; root owns configuration/tracking/recovery evidence, native actors own product source and landing.
- Keep parentf36b982b8b45774cf68fc621acf0d9727d72e6d5 and the existing PR1332 branch. Carry all eleven staged R2 paths; the three old R2 governance files are historical and remain byte-exact. Do not broaden into hooks, adapters, launcher, models, runtimes, seeds or backup configuration.
- Fresh correction is authorized for the reproduced code finding. Provider refusal/unavailable capacity still stops execution; no rephrasing a refused request, account/model switching, review-limit increase or provider-capacity retry.
- Keep all gate/receipt/source/index/head/base/CI/aggregate/queue/ordered-parent protections. No blanket thread resolution, admin merge, failing-test suppression, stale approval reuse, old-bus replay, consumed-budget reset or persistent internal full recovery archive.

## Stop conditions

- Hold on mismatched head/branch/base, concurrent mutation, undeclared changes, missing indexed packet/builder authority, provider refusal/unavailable capacity, quota stop threshold, or exhausted native recovery.
- If a necessary source change lies outside the declared boundary, preserve evidence and return exact required admission; do not widen scope or silence the gate.
- No commit without the new exact receipt and correct existing PR target. No merge without fresh corrected-head CI, independent complete-PR review and aggregate clearance. Retain every negative verdict and unresolved finding.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py --tb=short`

## Acceptance criteria

- The same failed native candidate/request cannot obtain another review through a governed bus change. Meaningful production/public fixture controls prove zero added reviewer/recovery/remediation/merge calls and preserve complete negative/interrupted evidence.
- Fresh genuinely corrected input still requires a new native review and existing successful-path protections. Unrelated transient behavior and the full retained R2 test coverage remain intact; the declared full three-module gate and native checks pass.
- The actual indexed packet/builder retain PR1332 branch and comparison ancestry. All retained historical R2 governance bytes stay unchanged. Fresh exact native approvals, corrected-head CI and independent complete-PR review precede actual merge and separately verified PRIMARY sync.
- TASKS preserves268IDs/44ordered owners and accurately distinguishes preserved, validated, committed, approved and landed work. Remaining PR/folder/retention obligations stay explicit without new numbered prerequisites.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-local-review-terminal-r3-2026-10-09`.
- Governing packet: this file, `reports/control_plane/workingrcx-local-review-terminal-r3-2026-10-09_2026-10-09.md`.
- TASKS.md authority: the 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r3-2026-10-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r3-2026-10-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-local-review-terminal-r3-2026-10-09`
- Active packet: `reports/control_plane/workingrcx-local-review-terminal-r3-2026-10-09_2026-10-09.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-terminal-r3-2026-10-09.json`
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
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r2-2026-10-09.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r3-2026-10-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
