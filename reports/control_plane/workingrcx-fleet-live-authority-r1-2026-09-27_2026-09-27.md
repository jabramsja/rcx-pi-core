# Renew the blocked fleet retirement authority from current live identities

Date: 2026-09-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-fleet-live-authority-r1-2026-09-27
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 189243e009ddb56555bec517f29fabfbc4e8702e770f4677158ed3851544e99f
Purpose: Complete the existing actual WorkingRCX cleanup task after its first public apply was safely held by stale pre-reboot device identities. Native code already preserves and retires sources, but hard-coded original wave/predecessor gates reject fresh retirement authority. Correct only that demonstrated renewal boundary and generate current native actions; do not redesign the pipeline or weaken identity checks.

## Scope

Sixteen exact paths: two existing retirement-admission/planning sources, two directly related test files, lifecycle documentation, TASKS/CHANGELOG, and native new-wave packet/indicator/action artifacts. No runtime change, new numbered obligation, or unrelated pipeline hardening.

Files and surfaces in scope:

- TASKS.md -- Preserve every task ID and cleanup-before-Mu order; record actual prior12HOLD/zero-retirement outcome and fresh authority, not cleanup completion.
- CHANGELOG.md -- Record only the observed stale-authority correction and native validations.
- mu/tools/executors/workingrcx_fleet_classification.py -- Replace the observed one-wave/predecessor-only retirement admission with explicit fresh reviewed authority binding; retain all existing identity, ownership and coverage safeguards.
- mu/tools/executors/workingrcx_fleet_apply.py -- Keep fresh retirement classification, planning and committed foreground authority consistent without replaying or rewriting original consumed plans; retain exact action-time identity and preservation checks.
- mu/tests/tools/test_workingrcx_fleet_classification.py -- Regress the actual fresh-successor rejection and mismatched authority rejection without granting arbitrary source mutation.
- mu/tests/tools/test_workingrcx_fleet_apply.py -- Real-Git regressions for stale identity holding without mutation, fresh authority with independent operation IDs, and unchanged consumed-operation/no-replay protection.
- mu/docs/agents/WorktreeLifecycle.v0.md -- Document actual fresh authority renewal after observed identity drift without weakening original receipt or source-preservation policy.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md -- Phase A alone expands the full native packet from this external STUB.
- reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json -- Native indicator/proof binding.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_census.json -- Fresh complete native observation after the reboot, including current exact device/inode/mode, current useful-work evidence and inherited owners.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_classification.json -- Fresh native exact source/action admission against landed predecessor48ed34c6, never a patched copy of the old census.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work.json -- Native useful-work ledger preserving missing-work and inherited landing ownership.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work_coverage.json -- Native exact coverage evidence; preserve pending owners rather than claiming archival is integration.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_apply_plan.json -- Fresh finite committed original-wave-consistent operation roots and exact identities; no reuse of any spent operation.
- reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_retirement_evidence.json -- Native current bound evidence and actual validations, with old batch1 preserved as12HOLD/zero moves.
- reports/deferred/non_blocking/workingrcx-fleet-live-authority-r1-2026-09-27_bridge_nonblockers.md -- Optional native actual nonblocker report only; no extra queue prerequisite.
- TASKS.md -- tracker-sync authority. The 2026-09-27 tracker sync note for wave `workingrcx-fleet-live-authority-r1-2026-09-27` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read the preserved root-cause evidence and the actual classify/build_residual_plan/require_residual_authority/inspect_identity functions before changing code. This is a captured live failure, not an edge-case matrix. The changed device number invalidates the old authority; matching inodes alone do not authorize a device-number substitution.
2. Provide the smallest coherent native fresh-successor retirement admission for this existing task. Bind each fresh wave, predecessor, census, classification, useful-work reports and plan explicitly through the normal committed authority. Avoid replacing the old hard-coded pair with another one-use hard-coded pair that requires a code wave for every refresh. Preserve conservative validation of inconsistent or incomplete authority; do not turn any arbitrary JSON into live deletion permission.
3. Keep all old wave artifacts, checksums, operation roots, claims, terminal receipts and exhausted recovery records immutable. The original batch1 now has12verifiedHOLDs; do not replay it or spend its remaining old batches. New source identities must come from a fresh native full observation and verification, not editing the old device fields. Fresh independent operation IDs must follow the new classification hash/wave.
4. Generate the native fresh retirement census against exact predecessor48ed34c6e2d32d9121e072f3780cbe2189d692d3, then classification/useful-work/coverage/plan/evidence through the existing CLIs. Keep PRIMARY, separate dev, this active carrier, stopped Mu, canonical preservation evidence, unrelated outside-fleet registrations and unsafe owners protected. Do not introduce blanket exclusions for previously supported legitimate sources. The prior completed carrier may be considered only with explicit fresh safe authority; never replay its ESCALATED completion.
5. Regress both the reproduced hard-coded admission refusal and stale identity no-mutation behavior through actual source-backed code, while proving old consumed claims remain spent and exact source identity/history/index/WIP/owner preservation stays mandatory. Run the declared suites. Check current admitted target identities read-only after artifact generation and before final handoff; if they drift, retain the precise cause instead of silently claiming an executable plan.
6. Native Phase A authors the full packet; Phase B owns code, artifacts, staging and review; commit executor owns commit/push/PR/CI/merge. All LLM roles Codex gpt-6-astra/max, commit providerless. Use the complete inherited executable PATH; the native ARM gh credential helper is already corrected. Do not recreate the quota daemon or any broad hardening wave.
7. Carry exact prior landing/current blocker into TASKS and retain all original obligations. PRIMARY WIP is protected, with heldTASKS transactionab25025ded1749b3b70f38e1489f6d46/stash6763f6be48375654a46996d171ecb406193815a2 and olderheld59653ccc/944fba65 unchanged. Root checkpoint and evidence are in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26.
8. After native merge and PRIMARY/base sync, foreground must execute the fresh public apply/verify pairs, preserve each recoverable destination, report actual removals and registration deltas, and keep genuinely missing useful-work owners explicit. Existing row38 remains current until its real cleanup obligations are accounted for, then existing Mu production. No new numbered queue prerequisite.

## Constraints

- Root supplies only external STUB and bounded TASKS/checkpoint/evidence. Do not ask root to write the full packet or implement code; route through launch_wave.py/dispatcher and native gates.
- Only the16declared paths. No runtime/host semantics changes, global pipeline redesign, unrelated model/provider policy changes or speculative hardening.
- Never disable filesystem identity, current behind-zero authority, liveness/owner/lock, original history/index/WIP preservation or independent recovery verification. Do not force/prune/reset/drop stashes or rewrite old operation records.
- One native mutation lane; preserve all user/protectedWIP and all historical evidence. No quota watchdog, forced hook, replay/reset or new numbered task.

## Stop conditions

- If the actual required admission correction needs a file outside the16paths, report exact code evidence and missing authority before writing it; do not chase speculative cases.
- Do not use the stale original plan for additional mutations or treat a native code merge as actual folder cleanup.
- If a live target changes or lacks safe ownership/recoverability, hold that target precisely and continue eligible peers only under fresh authority.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_workingrcx_fleet_classification.py mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- The same actual fleet can receive a fresh explicitly bound retirement wave/predecessor without editing a one-use global constant or weakening committed authority.
- Stale identities still HOLD before mutation; original consumed batch and all old records remain unchanged. Fresh native operations have distinct immutable authority.
- Normal native required tests, review, CI and merge land the scoped correction and fresh current artifacts; PRIMARY and separate dev remain synchronized with protectedWIP preserved.
- Foreground independently verifies actual admitted retirements and retains accurate useful-work owners/TASKS/to-do before Mu; no false completed-cleanup claim.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-fleet-live-authority-r1-2026-09-27`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`.
- TASKS.md authority: the 2026-09-27 tracker sync note for wave `workingrcx-fleet-live-authority-r1-2026-09-27` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-live-authority-r1-2026-09-27

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-live-authority-r1-2026-09-27`
- Active packet: `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/WorktreeLifecycle.v0.md`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tests/tools/test_workingrcx_fleet_classification.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_classification.py`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_apply_plan.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_census.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_classification.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_retirement_evidence.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work_coverage.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-live-authority-r1-2026-09-27 --output reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_workingrcx_fleet_classification.py mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tests/tools/test_workingrcx_fleet_classification.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_classification.py`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_apply_plan.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_census.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_classification.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_retirement_evidence.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work_coverage.json`, `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-live-authority-r1-2026-09-27.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-live-authority-r1-2026-09-27`
- Active packet: `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `d6dd33bcbb987045054b66333c436077bebc9927ceff05149f6a5614a1891436`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_workingrcx_fleet_classification.py mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/WorktreeLifecycle.v0.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tests/tools/test_workingrcx_fleet_classification.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_classification.py`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_apply_plan.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_census.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_classification.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_retirement_evidence.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work.json`, `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work_coverage.json`, `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/WorktreeLifecycle.v0.md`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tests/tools/test_workingrcx_fleet_classification.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_classification.py`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_2026-09-27.md`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_apply_plan.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_census.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_classification.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_retirement_evidence.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work.json`
  - `reports/control_plane/workingrcx-fleet-live-authority-r1-2026-09-27_useful_work_coverage.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-live-authority-r1-2026-09-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
