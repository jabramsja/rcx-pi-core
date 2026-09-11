# Census R3 CI Fixture Isolation on Existing PR 1287

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-CENSUS-R3-CI-FIXTURE-ISOLATION]
Wave ID: workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 8ef3129e991f01d8433836bfca57ebd741d13426d0563b106a0b6ca26092258e
Purpose: Unblock the eight reproduced green-gate failures on existing census PR #1287 with a test-fixture-only repair, preserving the already-reviewed census safety behavior and proceeding directly to fleet classification after merge.

## Scope

Only census test-fixture Git-environment isolation, a regression for ambient filter configuration, and exact generated governance/tracker artifacts. Preserve the existing production CLI and all model defaults unchanged.

Files and surfaces in scope:

- mu/tests/tools/test_workingrcx_fleet_census.py: fixture construction/invocation isolation and focused regression only
- TASKS.md, CHANGELOG.md and this repair's builder-generated packet, indicator and optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the CI failure using disposable fixture configuration: _git fixture setup ignores system/global Git configuration, while _cli inherits it and the production CLI intentionally reads effective filter settings. Existing CI failure evidence is https://github.com/jabramsja/rcx-pi-core/actions/runs/34636471724, exact head 4658184dd456d48e702176831d43c84fa5b8bfd0. Do not infer an executable-filter regression from expected unknown status.
2. Make ordinary fixture Git setup and CLI invocation independent of ambient runner configuration without modifying host Git configuration or the production CLI. Preserve explicit fixture-controlled local/include/global/worktree filter coverage and submodule coverage. Regress the ambient-filter baseline that broke CI; retain clean/dirty/count/error assertions and no-filter-execution/no-target-mutation assertions.
3. Run the declared focused proof and let the outer executor own staging, review, commit, pre-push, CI and merge on the existing PR branch jabramsja/workingrcx-fleet-census-r3-2026-09-11 for PR #1287. Do not create or switch to a new PR branch.
4. Keep the original census code, captured report, Astra/max defaults, original locked packet, old bus, receipts and exhausted recovery counters unchanged. TASKS/CHANGELOG must distinguish original census pending-merge evidence from this active test repair and keep classification immediate next after PR #1287 lands.

## Constraints

- Authorized control-surface L4_ENABLER under the founder's standing pipeline-bug-fix authorization. This repair must use the existing PR branch jabramsja/workingrcx-fleet-census-r3-2026-09-11; FOUNDER_OVERRIDE:workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.
- This is a fresh narrow repair stub in the current census landing slot, not an edit to the immutable R3 stub/packet and not a retry-counter reset. Build Phase A and all later artifacts through the existing launcher/dispatcher.
- No production CLI, executor, recovery guard, launcher, model configuration, workflow, runtime or Mu changes. Do not silence assertions, skip failing CI cases, disable the read-only filter guard, or modify real fleet targets/host Git configuration.
- Do not resume or modify stopped fleet census R1/R2, native-stub R1/R2/R3 or any preserved predecessor. No PR closures, fleet cleanup, new precursor queue positions or hypothetical hardening.
- Temporary regression fixtures are disposable; preserve real evidence. Do not leave dangling fixture links in the active .scratch recovery baseline after completed validations.

## Stop conditions

- Stop if HEAD/branch does not match the exact PR #1287 baseline or another actor owns this carrier.
- Stop if a fix requires production/enforcement changes, a new PR branch, weakening safety assertions, modifying the original R3 packet/recovery evidence, or out-of-allowlist paths.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- The declared tests pass with an ambient executable Git-filter configuration in the disposable test harness as well as the ordinary environment; normal clean/dirty observations remain tested.
- Existing explicit local/include/global/worktree filter and submodule safety regressions still prove no executable filter runs and no target mutation occurs.
- Only the declared fixture test and exact governance/tracker artifacts differ from 4658184dd456d48e702176831d43c84fa5b8bfd0.
- The pipeline updates and lands existing PR #1287 after required CI; census and Astra/max defaults are not called landed beforehand, and fleet classification remains immediate next.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-CENSUS-R3-CI-FIXTURE-ISOLATION]; wave id `workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11 --output reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9a97a0cddaff73a3839a70cc7661e9987959b1af68640662d5e55bb82d2f52e8`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `reports/control_plane/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-census-r3-ci-fixture-isolation-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
