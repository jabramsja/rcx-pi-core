# Complete local quota review and preserve native continuation authority

Date: 2026-10-05
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-local-review-quota-r3-2026-10-05
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 0ecf6b57215eb894f90b8b721e238c96248b910c4c84ef3051af418dc6b194a7
Purpose: Finish the approved local quota-review fallback from preserved R2 sources and correct only the two reproduced blockers: truncated review history and text/JSON continuation falling through to stale commit handoff. Same cleanup row38, no new numbered prerequisite.

## Scope

Complete the preserved local quota review feature; one demonstrated review-evidence integrity correction and its observed native continuation transport correction, with focused regressions in existing modules.

Files and surfaces in scope:

- TASKS.md
- CHANGELOG.md
- reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md
- reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_implementation_evidence.json
- reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json
- reports/deferred/non_blocking/workingrcx-local-review-quota-r3-2026-10-05_bridge_nonblockers.md
- mu/tools/executors/commit_executor.py
- mu/tools/executors/executor_config.json
- mu/tests/tools/test_commit_executor_local_review.py
- mu/tests/docs/test_growth_caps.py
- mu/tools/executors/launch_wave.py
- mu/tools/executors/executor_dispatch.py
- mu/tests/tools/test_launch_wave.py
- mu/tests/tools/test_executor_dispatch.py
- TASKS.md -- tracker-sync authority. The 2026-10-05 tracker sync note for wave `workingrcx-local-review-quota-r3-2026-10-05` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Preserve R2 read-only at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-local-review-quota-r2-20261005. Verify manifest /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/local_review_r2_stale_handoff_preservation_20261005.json and feature patch /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/local_review_r2_stale_handoff_feature_candidate_20261005.patch sha256 d1a5006ff05bb12ec0fbdcbbd5323ea8d677de448131d703d8d8e507ae7d9146. R2 HEAD244b09db076754ccb0489aaab30ca03d054f52d6,9staged/0unstaged; do not edit its files/index/checkpoints/receipts/counters, restore its old packet, reseal its identity, replay it or treat old review as approval.
2. Native implementer must import exactly these three preserved R2 feature sources before bounded repair: mu/tests/tools/test_commit_executor_local_review.py sha256 9a534517c772afd178644a8ccbda31e1dea89a2fc9bf0455b86f76d9e40ed2c6; mu/tools/executors/commit_executor.py sha256 82726a06fda24e4349cafa4837dffe8a8cc4d612877b5c429aee10f528aed9a3; mu/tools/executors/executor_config.json sha256 7ce648118c7423f9c0136eaaa4cebdd0c5e6352c9843bc13e2f146474aacd9bd. Do not recreate them or import donor TASKS/CHANGELOG/packet/indicator/growth-cap output as fresh authority. Native builders and commit own this carrier's governance.
3. Reproduce the latest supervisor defect using existing Carrier/production Step15: complete history has an unresolved connector issue finding, an authentic quota notice, and later standalone clear. Complete history blocks; newest30of31comments with comments.pageInfo.hasPreviousPage=true currently hides the finding and mock-merges with zero local reviews. Require complete review evidence before initial finding/route classification and before merge, independent of local-review eligibility. Reuse the existing completeness contract and fail closed on known-incomplete data; do not build a new pagination subsystem or bypass findings. Include truncation arriving during CI and preserve complete-history controls.
4. Reproduce the observed native continuation transport defect: launch_wave.py build_phase_b_dispatch_command creates explicit phase-b argv without--json; executor_dispatch.py _surface command construction forwards that flag only when requested; _continue_successful_executor_chain only recognizes structured continue_phase_b and otherwise can select an old phase_b_handoff.json. Ensure native machine continuation requests structured results, and make the dispatcher reject or safely honor nonterminal output before any stale handoff can start commit preparation. Missing/malformed/nonterminal output must not be treated as commit-ready merely because an old handoff exists. Do not reset attempt budgets, invent checkpoint authority or relaunch old R2. Keep routing/task/bus/script-owner identity.
5. Add bounded regressions to the existing local-review, launch-wave and dispatcher test modules. Test the real producer/consumer boundary with an old handoff present and assert no commit command or packet/index mutation for rejected/nonterminal output. Test valid structured continuation through its existing byte-bound checkpoint path. Retain all prior479local/Step14cases; no new test file, disabled checks, weaker assertions, skipped tests, manual cap edits, fabricated comments or force merge.
6. Preserve actual GitHub quota-notice compatibility, finding retention for earlier/unbadged/mixed-control/formal/thread/sweep cases, exact-head/diff/model-bound local review receipts, CI and protected sync. Current-request quota eligibility remains separate from clearance. Platform safety refusals are not eligible. Preserve the native Step5e generated-governance/candidate-authority integration and allow only its proven single-test growth-cap increment.
7. Refresh fresh source-bound implementation evidence with both failing reproductions, passing full declared gate, hashes, exact limits and donor preservation checks. Native PhaseA owns the full packet; root supplies this STUB only. No unrelated summary-only feedback, bridge-history note, path-alias diagnostics, provider defaults, runtime/host semantics or safety-control changes.
8. This carrier starts at unchanged PR1331 HEAD244b09db076754ccb0489aaab30ca03d054f52d6, preserving its monitor fix. Use this carrier's native launch_wave.py/dispatcher and let reviewed implementation load at its native entry. Do not copy candidate code into PRIMARY, patch running processes or manually stage/commit/push/merge.
9. After actual native landing/protected sync, verify PR1331 disposition and continue preservedPR1330 bring-current/CI/review/merge, PR1329 corrective continuation, first-five APPLY/independent VERIFY, ALL remaining obsolete folders/useful-work owners and PR1325 disposition, then existing Mu owner. Preserve268taskIDs/44queue rows. All18preexisting top-level folders plus this one temporary carrier remain accounted for; this is not physical cleanup completion. Native lifecycle must reconcile both preserved local-review donors and this carrier.

## Constraints

- Root authors STUB/config/tracking/diagnostics only. Native builder/PhaseA authors packet; native actors own implementation/staging/commit/push/merge/conflict resolution and retirement. One mutation lane; all model roles Codex gpt-6-astra/max; commit providerless.
- Only the two reproduced blockers above may expand the preserved feature. No hypothetical hardening, new provider/defaults, runtime/substrate/host semantics or new numbered queue prerequisite.
- Preserve every older donor, receipt, checkpoint and bounded budget unchanged. No authority resealing, reset, synthetic approval or replay of an invalid continuation.
- Only authentic current-head/request-bound GitHub code-review quota refusal can select independent local review. Never waive actionable findings, CI, supervisor approval, branch protections or protected synchronization. Platform safety refusal remains a stop; the separately paused runtime investigation remains paused.
- Native generated governance owns cap changes. Do not import old cap outputs or alter provenance validation.
- At explicit founder stop or observed quota<=10percent stop immediately without finishing; no watchdog/latch. Keep account quota details private.

## Stop conditions

- Stop on source changes outside declared candidate allowlist, donor hash mismatch, missing exact donor source or unproven preservation; report exact evidence rather than widening scope silently.
- Stop on protected native authority/safety rejection, exhausted bounded recovery or ambiguous ownership; never reset/reseal/replay oldR2 or force merge.
- Stop immediately on explicit founder stop or observed general quota<=10percent.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py`

## Acceptance criteria

- Preserved R2 three-file implementation reused byte-exactly before bounded repair, and no donor/index/checkpoint/receipt/budget changed.
- Both actual reproductions fail before and pass after repair: known-truncated finding evidence cannot merge, and nonterminal text/structured continuation cannot consume a stale handoff or mutate commit preparation.
- Declared four-module gate, fresh native supervisor/CI/review/merge/protected sync pass with command and source-bound evidence; historical tests or receipts are not current approval.
- Unchanged PR1331 monitor history plus completed fallback actually land before preservedPR1330/1329 and all physical cleanup;268taskIDs/44queue rows retained and no folder-cleanup overclaim.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-local-review-quota-r3-2026-10-05`.
- Governing packet: this file, `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`.
- TASKS.md authority: the 2026-10-05 tracker sync note for wave `workingrcx-local-review-quota-r3-2026-10-05` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-local-review-quota-r3-2026-10-05

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-local-review-quota-r3-2026-10-05`
- Active packet: `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`
  - `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-local-review-quota-r3-2026-10-05 --output reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_config.json`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`, `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-local-review-quota-r3-2026-10-05.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-local-review-quota-r3-2026-10-05`
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

- Refresh wave: `workingrcx-local-review-quota-r3-2026-10-05`
- Active packet: `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `35797e646f35c1b075f76b4ac454b8107a62cc19d876924248f0960efe057f9a`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_commit_executor_step14_autoresolve.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_local_review.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_config.json`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`, `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_2026-10-05.md`
  - `reports/control_plane/workingrcx-local-review-quota-r3-2026-10-05_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-quota-r3-2026-10-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
