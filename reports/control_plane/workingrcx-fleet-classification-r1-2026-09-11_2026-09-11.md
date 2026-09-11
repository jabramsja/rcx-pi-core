# Landed WorkingRCX Fleet Preservation-First Classification

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-CLASSIFICATION]
Wave ID: workingrcx-fleet-classification-r1-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 23a3071ada821809372c0b8b3e784a1ce489e93b8b85e77ad4245710e16897f9
Purpose: Advance the existing urgent fleet cleanup queue by classifying the landed R3 inventory into exact conditional cleanup candidates and explicit preservation/HOLD decisions. No fleet mutation in this wave.

## Scope

New deterministic read-only classification CLI, focused disposable tests, exact classification report and generated governance/tracker artifacts only.

Files and surfaces in scope:

- mu/tools/executors/workingrcx_fleet_classification.py and mu/tests/tools/test_workingrcx_fleet_classification.py
- reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json
- TASKS.md, CHANGELOG.md, this wave's builder-generated packet/indicator and optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `workingrcx-fleet-classification-r1-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Implement the small public CLI named in evidence_command. Consume only the landed census at reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json as inventory; bind the report to its raw SHA-256 ac6f61337081c9adb7c100bac061270f6c7864aaed55d48912f50b8473d0cd81 and exact predecessor c209bf29841425305003eeceddfd567a93874742. Generic temporary census fixtures may use their own recorded hashes. Do not re-enumerate the real filesystem or regenerate the source census.
2. Produce one deterministic reasoned decision per input row, preserving exact paths and available HEAD/branch/common-dir identity, source observation/error evidence and honest totals. Reject malformed or incomplete top-level inventory instead of claiming coverage; per-row uncertainty remains HOLD. Keep missing entries, non-repositories, standalone clones, symlinks, detached/unknown/dirty states, outside-fleet registrations, protected evidence and unmerged history on HOLD. Do not interpret missing registrations as deleted valuable work or prune them.
3. Identify a bounded CONDITIONAL_RETIRE_CANDIDATE subset only for present, successfully inspected, clean, symbolic linked worktrees at direct fleet-root paths in the canonical WorkingRCX common repository. Prove each recorded HEAD is an ancestor of the exact comparison commit using only local read-only Git object queries in this fresh carrier, with lazy fetching and optional writes disabled. Unavailable objects or inconclusive probes remain HOLD. No checkout, target Git command, fetch, process or GitHub census is permitted by the classifier.
4. Never select the primary WorkingRCX root, WorkingRCX-preservation or descendants, audit/admin source, dev/main/master worktrees, current/recorded census carrier, or any target explicitly protected as active or preserved noncomplete evidence by the canonical queue. Phase A must make the finite protected-target and candidate policy explicit from current TASKS authority; do not infer preservation retirement from an old LANDED note alone. This is classification, not authorization to modify any protected target.
5. Each conditional candidate must retain its exact source identity and explicit still-unmet apply prerequisites: reconcile census identity with action-time target state; prove idle and not protected; preserve and verify all valuable/untracked/ignored evidence before retirement; preserve branch/history; use supported safe never-behind preparation without losing WIP; then bind exact identity and pass each terminal action itself to execute_terminal_mutation_once, whose fresh fetch and behind(origin/dev)=0 checks must pass. A classification row or diagnostic return never grants reusable mutation authority. If identity, liveness, preservation or the existing boundary cannot be satisfied, apply must HOLD that target without blocking unrelated valid targets.
6. Tests cover actual recorded categories and public CLI determinism/source binding, a clean merged conditional candidate, dirty/unmerged/protected/missing/unknown HOLD, full row accounting and no target mutation. Use disposable repositories and isolated Git configuration following the landed fixture lessons; do not inspect or modify the live fleet in tests. Repeated declared evidence runs must safely reproduce or verify the owned report without failing on their own existing identical output or overwriting unrelated files.
7. Update TASKS/CHANGELOG with #1287 landed, classification pending until merge, the actual decision counts and apply immediately next. Retain every unresolved HOLD and all existing downstream PR1219/recovery/Mu obligations. Do not claim all directories are cleaned or add new precursor waves.

## Constraints

- Use only this fresh carrier from c209bf29841425305003eeceddfd567a93874742; stopped census/native-stub/recovery candidates, buses, receipts and reports remain unchanged and are not implementation or census source authority.
- No real fleet mutation, archive, delete, move, reset, stash, checkout, worktree prune/remove, source-census rewrite, stale PR disposition or remote ref change as classifier behavior. The same-wave carrier's normal pipeline commit/push/merge/retirement lifecycle remains authorized.
- No changes to census production code/tests, executor/dispatcher/launcher/recovery code, model defaults, Claude-owned surfaces, runtime or Mu. Existing terminal-mutation API is referenced, not redesigned. Defer hypothetical hardening that does not block this bounded classification.
- All local model-bearing roles remain Codex gpt-6-astra/max. Only the pipeline may refine the packet, implement, stage, review, commit, push and merge. Optional nonblocker output is allowlisted but not required to exist.

## Stop conditions

- Stop if the exact predecessor or landed census hash is wrong, the source inventory is incomplete, or the requested implementation exceeds the closed allowlist.
- Stop on any attempted live target mutation, hidden uncertainty, unaccounted census row, or request to adopt preserved stopped evidence. An individual ineligible target is HOLD, not justification to widen this wave.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_classification.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_classification.py --census reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json --base-commit c209bf29841425305003eeceddfd567a93874742 --output reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-classification-r1-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- The focused tests and repeated evidence command pass; the classification artifact is bound to the exact landed source and covers all 411 input rows with reasoned decisions.
- Conditional candidates satisfy the bounded recorded-evidence policy and still name fresh preservation/idle/identity/one-shot prerequisites. Every uncertain or protected target remains HOLD and no live target is touched.
- TASKS, packet, report and indicator agree without fake cleanup closure; after merge, the existing fleet apply wave remains immediate next.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-CLASSIFICATION]; wave id `workingrcx-fleet-classification-r1-2026-09-11`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `workingrcx-fleet-classification-r1-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-classification-r1-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-classification-r1-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_classification.py`
  - `mu/tools/executors/workingrcx_fleet_classification.py`
  - `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-classification-r1-2026-09-11 --output reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_classification.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_classification.py --census reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json --base-commit c209bf29841425305003eeceddfd567a93874742 --output reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-classification-r1-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_classification.py`, `mu/tools/executors/workingrcx_fleet_classification.py`, `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json`, `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-classification-r1-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-fleet-classification-r1-2026-09-11`
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

- Refresh wave: `workingrcx-fleet-classification-r1-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7a869b14b0026f6554582c011729c87a8f98b4e7e8a73aeafbd706093e35df38`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_classification.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_classification.py --census reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json --base-commit c209bf29841425305003eeceddfd567a93874742 --output reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-classification-r1-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_classification.py`, `mu/tools/executors/workingrcx_fleet_classification.py`, `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json`, `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_workingrcx_fleet_classification.py`
  - `mu/tools/executors/workingrcx_fleet_classification.py`
  - `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-classification-r1-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
