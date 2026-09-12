# PR 1291 Fixture CI Repair R2 — Native Existing-Branch Binding

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PRIVATE-REVIEW-R2-CI-FIXTURE-MAINTENANCE-R2]
Wave ID: private-review-r2-ci-fixture-maintenance-r2-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 555b23be88c9a08e7657ab8de742575c99a09f374a9252934a853f9eddce7c8c
Purpose: Land existing PR #1291 with the observed fixture-only CI repair and mechanically recognized existing-branch authority. Remain in the current private-review R2 landing slot; R3C6-R2 remains next.

## Scope

One disposable census fixture helper and its regression, plus exact new tracker/governance artifacts. No production code changes or old-packet reconciliation is needed in this fresh carrier.

Files and surfaces in scope:

- mu/tests/tools/test_workingrcx_fleet_census.py: fixture maintenance suppression and focused trace regression only
- TASKS.md, CHANGELOG.md and this wave's generated packet/indicator/optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `private-review-r2-ci-fixture-maintenance-r2-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Implement only the known 19-line repair: add per-fixture Git invocation -c maintenance.auto=false and a trace regression proving a real fixture commit occurs without git maintenance/gc child starts. The preserved candidate is /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/private-review-resume-r2-evidence-2026-09-11/terminal_ci_recovery/mu/tests/tools/test_workingrcx_fleet_census.py (SHA256 74a9c5e0a3abe0affcd9541d8a736cccb8cfc630418dfcbf9dfd6e8aeb9ac33b). Compare only that file to the exact baseline; prior approvals are evidence, not this wave's approval.
2. Retain all snapshot byte/mtime/index/ref and output-preservation assertions, explicit filter/submodule coverage, and current skip policy. Prior focused baseline trace recorded git maintenance run --auto --quiet --detach; suppression passed40/1 and independent reviewer reproduced fail-before/pass-after. Run the declared whole census module; do not claim the unchanged private-review module's693test result covers this test change.
3. Use the existing PR branch jabramsja/phase-b-private-review-byte-preserving-resume-r2-2026-09-11 for PR #1291. Preserve this literal existing PR branch marker and the explicit Authorized control-surface L4_ENABLER authorization through native packet generation; Phase B's existing-branch selector and commit authorization consume them. Before handoff, verify the native selector resolves exactly this branch. Do not switch/rebase to origin/dev or create another PR.
4. Update current TASKS/CHANGELOG truth: original private-review implementation remains unmerged in PR1291; old CI-repair lane was stopped before commit/push due missing branch-binding markers, not a test failure. Keep cleanup1MOVED/3INCOMPLETE/407priorHOLD and both consumed one-shot operations unchanged. R3C6-R2 remains next after actual merge; every later PR1219/Mu obligation stays in order.
5. Let native PhaseA/B, staging, supervisors, commit, push, CI and merge own the landing. Keep investigation to exact task anchors and this test; do not re-read entire historical buses/reports or duplicate already-completed proofs without need.

## Constraints

- Authorized control-surface L4_ENABLER under the founder's standing pipeline-bug-fix authorization. FOUNDER_OVERRIDE:private-review-r2-ci-fixture-maintenance-r2-2026-09-11. Use the existing PR branch jabramsja/phase-b-private-review-byte-preserving-resume-r2-2026-09-11; no new PR.
- Fresh corrected builder stub and namespaced bus only; never amend/relaunch either stopped repair contract, reuse its decisions as fresh authority, reset counters, or hand-edit packages/receipts. Preserve all prior carriers and evidence.
- No production census CLI, private-review source/tests, executor/recovery/launcher/commit code, workflows, model config, Claude-owned surfaces, runtime or Mu edits. No assertion weakening, additional skips, snapshot exclusions or host Git/OS settings.
- No old packet/indicator edits, branch switching, fleet action replay, new numbered queue position or speculative hardening. All selected local roles stay Codex gpt-6-astra/max; do not spawn subagents.

## Stop conditions

- Stop before implementation if HEAD is not 571f0999288f6a5c8f4d76bda9aa0c45ddc58ea5 or branch is not jabramsja/phase-b-private-review-byte-preserving-resume-r2-2026-09-11. Stop before commit if native target-branch selection/authorization does not preserve that exact branch.
- Stop for production/enforcement scope dependency or any need to weaken preservation assertions. Missing recognized branch authority must not be worked around by a new PR, manual git or hand-authored handoff.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py --tb=short`

## Acceptance criteria

- Fresh native PhaseA/B approve only the declared test/governance changes; original private-review source/tests, production census CLI and old packet/indicator remain baseline-identical.
- Whole census module passes and the trace regression still exposes the detached-maintenance baseline without suppression. Existing snapshot and output-preservation assertions remain active.
- Native handoff and commit target equal jabramsja/phase-b-private-review-byte-preserving-resume-r2-2026-09-11; existing PR1291 passes required checks and merges with both its original implementation and this fixture fix.
- Trackers accurately distinguish reviewed, committed and merged states; all preservation obligations remain and R3C6-R2 is immediate next.

## Grounding / Authorization

- Task: [PRIVATE-REVIEW-R2-CI-FIXTURE-MAINTENANCE-R2]; wave id `private-review-r2-ci-fixture-maintenance-r2-2026-09-11`.
- Governing packet: this file, `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `private-review-r2-ci-fixture-maintenance-r2-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:private-review-r2-ci-fixture-maintenance-r2-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `private-review-r2-ci-fixture-maintenance-r2-2026-09-11`
- Active packet: `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id private-review-r2-ci-fixture-maintenance-r2-2026-09-11 --output reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: private-review-r2-ci-fixture-maintenance-r2-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `private-review-r2-ci-fixture-maintenance-r2-2026-09-11`
- Active packet: `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6d326e9c15226f9c56e0445b675020669b7d2de4d5980b74787a73aec7538fac`
- Indicator artifact: `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `reports/control_plane/private-review-r2-ci-fixture-maintenance-r2-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/private-review-r2-ci-fixture-maintenance-r2-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
