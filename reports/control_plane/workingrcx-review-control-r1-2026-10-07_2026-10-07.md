# Recognize real GitHub activity controls and preserve protected review transitions on PR1332

Date: 2026-10-07
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-review-control-r1-2026-10-07
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: cb39e8f49f6c3196fa984675aeaf6db02e12cd3948b9974048ce53afec4931cc
Purpose: Unblock existing PR1332 through a bounded, fail-closed review-control correction from the preserved CI-green b27d1d8 head, with fresh native approval and actual protected merge.

## Scope

Correct only Step15 recognition of authentic GitHub activity control payloads and the protected quota-history review transition, with behavioral tests and accurate native governance. Keep existing preserved test fixes unchanged.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: bounded standalone activity-control parsing and the adjacent quota-history Step15 review/merge transition needed to retain actual current-head clearance and protected exact-head merge.
- mu/tests/tools/test_commit_executor_local_review.py and mu/tests/tools/test_commit_executor_step14_autoresolve.py: real-payload regression controls through existing review/classification/CI/merge fixtures.
- reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md, reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json, reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json, TASKS.md, CHANGELOG.md, and optional own native nonblocker report.
- mu/tests/docs/test_growth_caps.py only if generated mechanically by native governance; never a manual cap increase.
- reports/deferred/non_blocking/workingrcx-review-control-r1-2026-10-07_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-07 tracker sync note for wave `workingrcx-review-control-r1-2026-10-07` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-r2-bot-review-diagnostic/diagnosis.json, pr-review-state.json and native-result.json, and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-r2-preserved/preservation.json. The saved actual service comment is the primary reproduction fixture, not an abbreviated synthetic replacement. Parent and remote PR1332 must both be b27d1d88616891ee1478bd8dc49b592ebd5f42a2 before launch. The old clean carrier, receipts and spent recovery state stay immutable.
2. Reproduce the recorded complete activity comment as a retained bot finding before changing code. The current standalone-control regex only matches abbreviated heading/rows; the real body also includes introductory text, table header/separator, emoji, bold label, relative-time HTML and standard details boilerplate. Native Step15 enables finding retention from the earlier genuine quota notice, so this metadata incorrectly blocks a current nonquota review. Retain the saved raw body byte-for-byte as an offline test fixture; never depend on live GitHub availability in tests.
3. Recognize complete, structurally known activity controls using bounded parsing with full-body consumption. Retain established compact controls. Treat Running and observed Completed activity as metadata only, never approval, quota eligibility, a finding disposition or current-head binding. Do not use a marker-prefix blanket exemption, broad prose wildcard, badge-only heuristic, stripping arbitrary HTML/prose, or ignores for unknown content.
4. Add meaningful regression controls with the complete recorded Running payload and an explicitly modeled Completed variant. Retain mixed/quoted/leading/trailing/cell/details payload findings, separate old and current findings, malformed/unknown rows and boilerplate, human unresolved threads, complete pagination and head identity. Exercise the existing real Step15 fixture at initial classification, after independent review, and after CI; assert full finding bodies and all prior receipt/continuation bytes remain intact at holds.
5. Inspect the adjacent quota-history-to-cloud-clearance path. commit_executor.py preserves quota-history findings but currently sends local_review=None to merge_pr.sh, which invokes --admin. For this same quota-history lane, retain a protected --match-head-commit merge after genuine current-head GitHub clearance, using existing protected merge/postmerge mechanisms and rechecking live head, required CI and all retained findings. A known activity table, stale quota notice, running/pending review or timeout alone must never authorize that merge or an independent quota review. Scope this to the quota-history lane; leave unrelated legacy PR behavior alone. Do not change branch protections or erase/resolve review threads. Add direct command-boundary controls proving no administrative merge, no merge for pending/stale/wrong-head review, and protection against findings/head changes during CI. If this requires any surface outside the allowlist, stop with concrete evidence rather than expanding scope.
6. Keep the already committed bootstrap isolation and prompt-checkout tests byte-identical to parent. Preserve source hashes: mu/tests/engine/test_mu_type.py 7e18fdba00fa23fdcbd2a0556ef77d34e40ad1f8301dde2854863843454d07da; mu/tests/l4_gates/test_stage0_vm_cutover.py 32c3349b6837ad90491cc0643a1393a49d3c202fc9551a6560839e83514b353f; mu/tests/tools/test_agent_prompt_contract_injection.py 51c8c2eebc8796f372e34188c86172de919db747e19f009f38879aac8861f0e8. No runtime, loader/template, seed, recovery-agent policy, launcher, dispatcher transport, CI snapshot fixture, model or hook edit.
7. Run the declared two-module gate after the native repair and save the exact command, exit status, summary and source hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/review-control-r1-validation. Demonstrate a focused regression fails against the parent and passes with the corrected source, plus the finding-retention negative controls. Use an isolated temporary copy/subprocess for the pre-fix replay rather than overwriting the active candidate during review. Retain all original assertions and skips.
8. Write reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json as phase-scoped implementation evidence. Source/test observations bind the execution phase; implementation-time TASKS/packet/tracker/indicator hashes are not final staged-candidate claims. Fresh native final approval and candidate receipts bind later generated governance. No self-hash or circular post-review rewriting. Native Phase A owns the packet and native governance owns tracker/indicator/caps.
9. Update existing row38 with actual CI-green-but-review-held status and this bounded same-owner continuation. Keep row40 as the existing automation owner for pending out-of-allowlist recovery admission, structured terminal transport/raw stream retention, governance phase binding, maintenance.lock snapshot fixture and task-ID-only postmerge APPLY routing. This wave repairs only the observed activity-control and protected review transition; no new numbered prerequisite.
10. Authorized control-surface L4_ENABLER under founder standing pipeline-bug-fix authorization. Use the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for existing PR #1332 only. Require fresh native Phase A/B and final staged-candidate approval, normal hooks, fresh required CI and actual protected exact-head merge. No replacement PR, receipt transfer, recovery-budget reset, force push or administrative merge.
11. Development remains local. Recovery evidence belongs on UUID-verified RCX Recovery 93064AFA-816D-43E3-BCC9-8A514F8F3D7D under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z; the Crucial Time Machine volume is separate. Preserve PRIMARY WIP and existing manifest mappings. Pipeline producer deduplicated-store integration remains separately owned, not claimed complete.
12. This auxiliary review repair creates no physical APPLY plan and replays no old retirement actions. Keep PR1331/1330/1329 and paused PR1325 useful-work/disposition obligations open. If native postmerge task-ID routing requests a physical APPLY plan, report it separately from proven merge and PRIMARY sync; never manufacture a plan or patch unrelated closeout machinery.

## Constraints

- Authorized control-surface L4_ENABLER; founder standing pipeline-bug-fix authorization and autonomous continuation apply. The existing PR branch is jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR #1332. FOUNDER_OVERRIDE:workingrcx-review-control-r1-2026-10-07.
- Root authors config/tracking/diagnostics; configured native actors own implementation, review, staging, commit, push, merge and conflict resolution. One mutation lane with Codex implementer/reviewer and providerless commit.
- Fresh same-owner wave from preserved CI-green b27d1d88616891ee1478bd8dc49b592ebd5f42a2. No old packet rewrite, lifecycle retirement claim, prior receipt reuse, recovery reset or branch replacement.
- Do not weaken finding retention, pagination, current-head binding, review requirements, protected merge, candidate integrity, tests or hook policy. Activity metadata alone grants no execution/merge authority.
- Keep all runtime/host/seed surfaces and previously committed test fixes unchanged. Recovery evidence external, active development local.
- No new numbered prerequisite, no blanket cleanup completion and no paused PR1325 resumption.

## Stop conditions

- Stop on head/branch/PR identity mismatch, active concurrent ownership, changed preserved source hashes, incomplete review evidence, exhausted recovery or an out-of-allowlist repair.
- Preserve any native hold without forged approvals, old-budget reset, review clearance fabrication or administrative merge.
- Do not claim merge, PRIMARY synchronization, retirement, all useful work reconciled or automatic dedup integration without actual evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`

## Acceptance criteria

- The exact saved GitHub activity body reproduces the original false finding; complete known controls are recognized after repair, with real-flow regression coverage.
- Activity metadata never clears real findings or permits merge by itself; mixed, malformed, quoted and separate findings remain blocking with complete body and identity.
- The quota-history lane handles a later genuine current-head GitHub clearance using protected exact-head merge, with required CI, live evidence refresh and no thread resolution or administrative override.
- The two-module gate passes freshly; original assertions remain, and all three preserved test hashes match parent.
- Only the declared executor/test/governance scope changes; implementation evidence is phase-scoped and final native candidate receipts remain authoritative.
- Existing PR1332 lands through fresh native approval/hooks/CI/protected merge, with truthful PRIMARY sync and remaining cleanup status.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-review-control-r1-2026-10-07`.
- Governing packet: this file, `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`.
- TASKS.md authority: the 2026-10-07 tracker sync note for wave `workingrcx-review-control-r1-2026-10-07` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-review-control-r1-2026-10-07

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-review-control-r1-2026-10-07`
- Active packet: `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`
  - `reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-review-control-r1-2026-10-07 --output reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`, `reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-review-control-r1-2026-10-07.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-review-control-r1-2026-10-07`
- Active packet: `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f710b97478c861af91110d573bf8e3086d933a87e887e002ec06b01cf1c95120`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`, `reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-review-control-r1-2026-10-07_2026-10-07.md`
  - `reports/control_plane/workingrcx-review-control-r1-2026-10-07_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-review-control-r1-2026-10-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
