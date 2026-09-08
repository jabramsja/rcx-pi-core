# Phase B Launch Tracker Restore Capability R4A

Date: 2026-09-07
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PHASE-B-LAUNCH-TRACKER-RESTORE-CAPABILITY-R4A]
Wave ID: phase-b-launch-tracker-restore-capability-r4a-2026-09-07
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 1516d5b4a8794a4408b2bc885df4867fadd948dea633b06b85368464a9a7f474
Purpose: Land the markerless Phase B capability required to capture, prove, and restore a launcher-authored same-wave tracker note on a later fresh launch. This packet does not activate or claim live use of the capability; it removes the R3 self-application deadlock so activation can run only after the implementation is on dev.

## Scope

Markerless capability landing only: generic launch-bound tracker capture/removal/restoration machinery, focused tests, TASKS queue truth, and same-wave governance.

Files and surfaces in scope:

- A markerless packet that follows the existing Phase B path and makes no claim that candidate-introduced code executed in its own process.
- Generic capability in phase_b_executor.py plus focused tests in test_phase_b_executor.py.
- TASKS preservation of the stopped R3 NO_GO and the strict R4A CURRENT -> R4B NEXT -> fresh evidence-handoff R2 order.
- TASKS.md -- tracker-sync authority. The 2026-09-07 tracker sync note for wave `phase-b-launch-tracker-restore-capability-r4a-2026-09-07` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical packet from this stub on exact PR #1267 merge 52874fd2e9234cb95d2a28f75765c2cea73451a5; preserve the stopped R3 worktree, state, review, and staged candidate unchanged as noncomplete evidence.
2. Keep this capability packet free of every launch-tracker restoration opt-in marker or token so the currently loaded executor uses its ordinary legacy path.
3. Implement the future marker-gated capture, exact whole-note-removal proof, byte-exact restoration, resumable state continuity, and terminal at-most-once behavior without importing files from the stopped R3 lane.
4. Derive source/target/comparison authority from the current launch-bound packet, route, candidate-authority spec, and HEAD equality. Do not hard-code PR #1267 or any one commit in production; a later packet must be able to bind its own exact launch base.
5. For an activated future packet, require restored launcher truth before SDK review, indicator collection, candidate-authority preparation, staged L4, supervisors, bridge review, or commit handoff; fail closed on missing, stale, malformed, or drifted authority while preserving markerless behavior.
6. Add focused tests for the generic capability, dynamic exact-base binding, crash/resume continuity, restoration-before-downstream ordering, at-most-once consumption, and unchanged markerless behavior. Do not add non-occurring parser or platform matrices.
7. Synchronize TASKS through the R3 NO_GO: R4A is sole CURRENT, R4B is immediate NEXT, fresh evidence-handoff R2 follows R4B, and all later PR1219, PR census, never-behind, PR disposition, preservation-first fleet cleanup, and Mu production work remains ordered without loss.
8. Land R4A through providerless commit, PR, required CI/review, merge, and cleanup. Only after the exact merge exists, create and builder-launch the small marker-bearing R4B activation stub from that merge.

## Constraints

- Functional scope is exactly phase_b_executor.py and test_phase_b_executor.py; TASKS and same-wave governance are the only additional tracked surfaces.
- Do not edit candidate_authority.py, staged-L4 checks, dispatcher, launcher, Phase A, recovery, commit, bridge, configs, runtime, substrate, hosts, seeds, projections, Mu, or Claude-owned files.
- Do not resume, copy, cherry-pick, or patch-transfer the stopped R3 candidate; reconstruct from exact #1267 source and its review evidence.
- Do not claim live activation in R4A. Model-bearing roles and pager are Codex gpt-5.6-sol ultra; commit remains providerless.
- Ignore deferred and non-occurring edge cases.

## Stop conditions

- Stop before launch unless source/target/comparison are exact #1267 and the lane, bus, and Codex-only role overrides are fresh.
- Stop if this markerless capability wave attempts to exercise candidate-introduced code in its already-running executor.
- Stop if production needs a path outside the two Phase B files or a new durable cross-component schema.
- If the same live-path/self-application blocker recurs, preserve the lane and narrow again; do not revise a full packet in place.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Only the six allowlisted paths change; functional changes remain in the two Phase B files.
- The packet is markerless, the current live run stays on legacy behavior, and review does not rely on candidate code having executed in-process.
- Production contains no fixed #1267 comparison constant; future activation derives and validates one exact launch base from existing authority surfaces.
- Focused evidence proves restore-before-downstream ordering, resume continuity, at-most-once behavior, and unchanged markerless behavior.
- TASKS records R3 as preserved NO_GO, R4A CURRENT, R4B NEXT, and retains the complete downstream queue.
- Providerless PR, CI, review, merge, and cleanup complete before R4B is bound and launched.

## Grounding / Authorization

- Task: [PHASE-B-LAUNCH-TRACKER-RESTORE-CAPABILITY-R4A]; wave id `phase-b-launch-tracker-restore-capability-r4a-2026-09-07`.
- Governing packet: this file, `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`.
- TASKS.md authority: the 2026-09-07 tracker sync note for wave `phase-b-launch-tracker-restore-capability-r4a-2026-09-07` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:phase-b-launch-tracker-restore-capability-r4a-2026-09-07

## Non-normative review clarification

This clarification makes the existing native packet contract mechanically checkable; it does not add to, replace, reorder, or supersede any Purpose, Scope, Work item, Constraint, Stop condition, or Acceptance criterion.

The six allowlisted repository paths referenced by the Scope and Acceptance criteria are exactly:

1. `mu/tools/executors/phase_b_executor.py`
2. `mu/tests/tools/test_phase_b_executor.py`
3. `TASKS.md`
4. `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`
5. `reports/deferred/non_blocking/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_bridge_nonblockers.md`
6. `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`

For Work item 5 and the focused-evidence Acceptance criterion, acceptance requires four distinct activated-path negative cases in `mu/tests/tools/test_phase_b_executor.py`: missing authority, stale authority, malformed authority, and drifted authority. Each case must prove fail-closed termination before SDK review, indicator collection, candidate-authority preparation, staged L4, supervisors, bridge review, or commit handoff. The separate markerless-path case must continue to prove unchanged legacy behavior.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `phase-b-launch-tracker-restore-capability-r4a-2026-09-07`
- Active packet: `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`
  - `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-launch-tracker-restore-capability-r4a-2026-09-07 --output reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`, `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-launch-tracker-restore-capability-r4a-2026-09-07.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-launch-tracker-restore-capability-r4a-2026-09-07`
- Active packet: `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0189f8af42078e84529d340eeea8bce622c0d314f2cce9172afbe97df1fc301e`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`, `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-launch-tracker-restore-capability-r4a-2026-09-07_2026-09-07.md`
  - `reports/l4_wave_indicators/phase-b-launch-tracker-restore-capability-r4a-2026-09-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
