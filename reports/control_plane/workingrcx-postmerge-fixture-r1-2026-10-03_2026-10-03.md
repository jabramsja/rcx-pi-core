# Land preserved cleanup repair with complete postmerge test fixtures

Date: 2026-10-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-postmerge-fixture-r1-2026-10-03
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 19f27b4dbc5a8484cb61484d65373d7bf537deb1ffa26eb884e1646c86d2de23
Purpose: Finish the existing cleanup enabler from its saved native commit, adopting only the native postmerge fixture repair excluded by R2's frozen scope. Same task and queue position; no new numbered prerequisite. After actual landing resume the preserved original folder-cleanup wave.

## Scope

One new test-fixture repair plus ordinary wave metadata; inherited R2 implementation and historical evidence are explicitly included in the full dev-based candidate authority, not hidden by using the unmerged parent as comparison base.

Files and surfaces in scope:

- CHANGELOG.md -- Record observed fixture integration and carried-forward unmerged implementation honestly.
- TASKS.md -- Synchronize existing cleanup owner and queue truth; preserve268task IDs and44numbered rows.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py -- Adopt the hash-bound native R2 fixture repair and retain all existing assertions plus incomplete-evidence regressions.
- mu/tests/tools/test_launch_wave.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- mu/tests/tools/test_phase_b_executor.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- mu/tests/tools/test_workingrcx_fleet_apply.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- mu/tests/tools/test_worktree_lifecycle.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- mu/tools/executors/launch_wave.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- mu/tools/executors/phase_b_executor.py -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- reports/control_plane/workingrcx-commit-ready-resume-r2-2026-10-03_2026-10-03.md -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- reports/control_plane/workingrcx-commit-ready-resume-r2-2026-10-03_implementation_evidence.json -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md -- Native wave-owned packet/evidence/indicator/nonblocker output; no premature landing claim.
- reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_implementation_evidence.json -- Native wave-owned packet/evidence/indicator/nonblocker output; no premature landing claim.
- reports/deferred/non_blocking/workingrcx-commit-ready-resume-r2-2026-10-03_bridge_nonblockers.md -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- reports/deferred/non_blocking/workingrcx-postmerge-fixture-r1-2026-10-03_bridge_nonblockers.md -- Native wave-owned packet/evidence/indicator/nonblocker output; no premature landing claim.
- reports/l4_wave_indicators/workingrcx-commit-ready-resume-r2-2026-10-03.json -- Inherited from saved native R2 commit; include in fresh full-candidate review and preserve exact bytes, not new implementation scope.
- reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json -- Native wave-owned packet/evidence/indicator/nonblocker output; no premature landing claim.
- TASKS.md -- tracker-sync authority. The 2026-10-03 tracker sync note for wave `workingrcx-postmerge-fixture-r1-2026-10-03` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Verify the read-only preserved R2 inventory /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/commit_ready_r2_preserved_sources_20261003.json, independent patch /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/commit_ready_r2_native_postmerge_fixture_repair_20261003.patch, and full-test result /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/commit_ready_r2_repaired_full_pytest_validation_20261003.json. Verify every source/evidence/Git binding before adoption and after validation. Source root is /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-commit-ready-resume-r2-20261003; do not mutate it.
2. Confirm carrier HEAD begins at local native commit8e26fd566bc188ea8d5b468ae6f6b9bbb578e40d and dev comparison remains146ca4955dca1c56111fc482876290ee1c0b12e2. The parent is NOT merged. Fresh candidate/reviewer authority must inventory the complete diff against that dev commit, including every inherited path; do not substitute the unmerged parent as comparison base or reuse R2 approval receipts.
3. Adopt only mu/tests/tools/test_commit_executor_post_merge_cleanup.py from the bound repaired source. Preserve its existing assertions, controlled disposable lsof fixture usage and two uncertain-evidence HOLD regressions. Production process/lifecycle guards remain unchanged. Preserve the six inherited implementation/test files exactly as committed in8e26fd56; do not redesign or replay their implementation.
4. Read native R2 failure capture .scratch/recovery_agent_workingrcx-commit-ready-resume-r2-2026-10-03-run-pre-push-script-1.txt and recovery/recovery_status.json under its recorded bus. The full before/after diagnostic sweep already exists. Run this wave's declared focused-module/linter/docs gates, fresh native reviews and all mandatory full-candidate commit/pre-push/CI gates; cite exact exits/counts and distinguish prior evidence from new validation. Never bypass a hook.
5. Update TASKS.md from current PRIMARY tracker truth without losing268task IDs,44queue rows, PR1325 exact-coverage hold, original cleanup follow-through, all useful-work owners, held PRIMARY transaction/stash, and unresolved/platform-paused Mu finding. This successor replaces R2 under the same row38 owner. No added numbered prerequisite; stopped/new carrier retirement remains in existing lifecycle cleanup.
6. After actual merge and PRIMARY synchronization, record the existing public original-cleanup continuation through PRIMARY launch_wave.py with original config /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/control_plane/workingrcx-fleet-residual-pr-folders-r1-2026-10-03_wave_config.json, repo-root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-fleet-residual-pr-folders-r1-20261003 and bus .agent_bus-fleet-residual-pr-folders-r1-20261003. The outer operator runs it only after preserved-state and focused post-hook checks. Physical cleanup requires complete fresh process evidence; missing SMB lsof evidence is still a real hold, not cured by fixture tests.

## Constraints

- External STUB only. Native PhaseA authors the full packet; native actors own source adoption, staging, approvals, commit, push and merge.
- One observed blocker only. Do not add recovery-framework hardening, hypothetical cases, model/access/safety changes, timeout/retry budget changes or new numbered tasks.
- All original/R1/R2 stopped worktrees, indexes/configs/packets/receipts/budgets are read-only. Inherited R2 historical metadata comes from commit8e26fd56, not its later staged retry metadata. Preserve parent historical evidence bytes.
- Codex roles use existing gpt-6-astra/max. No runtime investigation, Daybreak retry, mount action, fleet APPLY, folder deletion, PR1325 closure, production lifecycle/process changes, test-integrity exemptions or private helper access.
- The seventeen-path dev-based fence includes cumulative inherited changes for fresh review; only the one fixture file, TASKS/CHANGELOG and new-wave metadata may be changed. No old approval becomes fresh authority. Skips prove no physical-retirement readiness.

## Stop conditions

- Stop on preserved hash/Git drift, unexpected parent/dev lineage, candidate paths outside the declared fence, or ambiguous ownership. Report the exact evidence; do not expand a sealed packet.
- Stop on explicit founder stop or observed quota<=10%, without finishing work or recreating a watchdog. Do not reset spent claims, consume stopped receipts, or relaunch failed scopes.

## Validation gates

- evidence_command: `PYTHONDONTWRITEBYTECODE=1 python3 tools/checks/linters/check_private_attr_access.py . mu/tests/tools/test_commit_executor_post_merge_cleanup.py && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Fresh authority includes the complete cumulative dev-based candidate. All six inherited source/test files remain byte-identical to the saved native commit; only the hash-bound postmerge test repair is newly adopted.
- Declared linter/module/docs gates and all mandatory native whole-candidate gates pass, with exact commands/counts and honest skips; no production process guard is weakened.
- Original/R1/R2 source/evidence/index/config/receipt preservation holds, and task/queue ownership stays synchronized without additional numbered prerequisites.
- Actual native push, PR merge and PRIMARY synchronization complete before landing is claimed. Record original-cleanup public continuation; real folder retirement and PR1325 coverage remain explicit downstream obligations.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-postmerge-fixture-r1-2026-10-03`.
- Governing packet: this file, `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`.
- TASKS.md authority: the 2026-10-03 tracker sync note for wave `workingrcx-postmerge-fixture-r1-2026-10-03` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-postmerge-fixture-r1-2026-10-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-postmerge-fixture-r1-2026-10-03`
- Active packet: `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`
  - `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-postmerge-fixture-r1-2026-10-03 --output reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONDONTWRITEBYTECODE=1 python3 tools/checks/linters/check_private_attr_access.py . mu/tests/tools/test_commit_executor_post_merge_cleanup.py && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`, `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-postmerge-fixture-r1-2026-10-03.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-postmerge-fixture-r1-2026-10-03`
- Active packet: `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `70c3082006e70453f6b0717c0133082808353d220aa901d9b99486677ba6e668`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`
- Evidence command: `PYTHONDONTWRITEBYTECODE=1 python3 tools/checks/linters/check_private_attr_access.py . mu/tests/tools/test_commit_executor_post_merge_cleanup.py && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`, `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_2026-10-03.md`
  - `reports/control_plane/workingrcx-postmerge-fixture-r1-2026-10-03_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-postmerge-fixture-r1-2026-10-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
