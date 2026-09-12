# Private-review prepared-checkpoint byte-preserving resume R2

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PHASE-B-PRIVATE-REVIEW-BYTE-PRESERVING-RESUME-R2]
Wave ID: phase-b-private-review-byte-preserving-resume-r2-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 5d0ad3bf9ad2680ff8fc37f029896633b2bf14a6408b8d3c80b0880aa78670eb
Purpose: Reconstruct the existing private-review recovery obligation from the exact landed predecessor: distinguish unprepared from prepared pending-review state, bind prepared state to staged Git-index bytes, and resume only the owed review without rebuilding the package. Validate recovered reviewer material, including QUESTION, before changing the pending checkpoint. Do not import the stopped broad R1 implementation.

## Scope

One Phase B private-attribute pending-review consumer and its public regressions; fresh reconstruction in the already-current recovery R2 slot. No recovery producer, new retry mechanism, fleet action or later PR1219 atom.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py and mu/tests/tools/test_phase_b_executor.py
- TASKS.md, CHANGELOG.md and this wave's builder-generated packet/indicator/optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `phase-b-private-review-byte-preserving-resume-r2-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Keep the existing ordinary/reentry pre-preparation pending checkpoints explicitly non-resumable as prepared authority. A recovered unprepared checkpoint must fail before package preparation, staging, candidate/checkpoint mutation or actor calls. On fresh ordinary/reentry remediation, save a distinct prepared pending-review checkpoint only after successful package preparation and staging, before reviewer launch.
2. Bind that prepared checkpoint to existing wave/task/plan/comparison/round/candidate authority, canonical staged path inventory and index modes/object/blob bytes. Preserve findings, explicit dispositions and deferred identity. Before any recovered-path mutation or actor, verify exact authority and index/worktree equality. Missing, malformed or mismatched authority fails closed with the candidate and last valid checkpoint unchanged; never adopt current bytes as authority.
3. For a valid prepared recovery, invoke only the existing owed private-attribute reviewer without package preparation, L4 recollection, restaging or implementer replay. Preserve the saved review context and use existing continuation semantics after a validated decision. Do not introduce general actor-replay/finalization machinery owned by the following R3C6-R2 task.
4. Validate the retained recovered reviewer envelope/schema and exact job/turn/decision identity before every outcome that may replace the prepared pending checkpoint, expressly including QUESTION. Missing or malformed material returns a structured error without changing the checkpoint or candidate. A valid QUESTION retains the existing founder-question terminal semantics; never infer GO or erase dispositions.
5. Add public run_phase_b coverage for both ordinary/reentry prepared resumes, the unprepared versus prepared crash boundary, staged/index-versus-worktree mismatch, and valid/missing/malformed recovered QUESTION material. Prove zero preparation/restaging/implementer replay on valid resume, no mutations/actors on invalid checkpoint authority, and unchanged fresh/unrelated flows. Run the complete existing test module.
6. Synchronize TASKS and CHANGELOG with PR #1290 exact merge and its consumed live outcome (one recoverable move, three incomplete targets, 407 untouched HOLDs), this existing current slot, and fresh R3C6-R2 next. Preserve every stopped lane and later PR1219/Mu obligation. Use launch_wave.py/native dispatcher for packet generation and the normal implementation/review/commit/push/CI/merge path.

## Constraints

- Fresh carrier from exact PR #1290 merge only. Reconstruct from landed source, never copy/adopt code, tests, packets, reviews, receipts or counters from the stopped broad R1 lane or any other stopped candidate.
- No changes to recovery_gate.py, executor_dispatch.py, launch_wave.py, commit_executor.py, bridge adapters, configs, Claude-owned files, runtime or Mu. No fleet/PR mutation, old operation replay, indexing changes or cleanup follow-up in this wave.
- Do not make L4 globally deterministic, freeze timestamps, weaken candidate/review authority, infer decisions or modify fresh/unrelated review behavior. The synthetic reader readiness/settling finding is explicitly non-blocking and outside scope.
- All selected local roles remain Codex gpt-6-astra/max. The native pipeline authors the canonical packet, implements, stages, reviews, commits, pushes and merges. Do not spawn subagents or hand-edit generated packets.
- Keep the current queue position; fresh R3C6-R2 remains next. Handle only reproduced blockers to this recovery consumer, not hypothetical checkpoint variants or later PR1219 atoms.

## Stop conditions

- Stop if exact source/base authority differs or implementation requires production/test paths outside the closed allowlist; preserve all evidence and report the concrete scope dependency.
- Reject a candidate that resumes an unprepared checkpoint, rebuilds a prepared candidate during recovery, accepts index/worktree mismatch, or replaces pending state from missing/malformed recovered reviewer material. Do not stop for the explicitly deferred settling nonblocker.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py --tb=short`

## Acceptance criteria

- Only the closed allowlist changes; builder packet, TASKS and indicator bind this exact wave and comparison commit.
- Fresh successful preparation creates durable staged-index-authoritative pending-review state; only verified prepared recovery invokes the existing owed reviewer without preparation/restaging/implementer replay.
- Invalid checkpoint authority and malformed/missing recovered reviewer material preserve candidate and pending state; valid recovered QUESTION keeps existing terminal semantics, ordinary and reentry.
- The full test_phase_b_executor.py module and native staged L4, independent review, supervisors, pre-push, CI and merge gates pass; queue and preservation truth remain accurate.

## Grounding / Authorization

- Task: [PHASE-B-PRIVATE-REVIEW-BYTE-PRESERVING-RESUME-R2]; wave id `phase-b-private-review-byte-preserving-resume-r2-2026-09-11`.
- Governing packet: this file, `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `phase-b-private-review-byte-preserving-resume-r2-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:phase-b-private-review-byte-preserving-resume-r2-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `phase-b-private-review-byte-preserving-resume-r2-2026-09-11`
- Active packet: `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-private-review-byte-preserving-resume-r2-2026-09-11 --output reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-private-review-byte-preserving-resume-r2-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-private-review-byte-preserving-resume-r2-2026-09-11`
- Active packet: `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2e23a569ead75d4e7f9edd9a68f2ddcdf62fb9d43be79f5bac391337a7eb2c3b`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`, `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-private-review-byte-preserving-resume-r2-2026-09-11_2026-09-11.md`
  - `reports/l4_wave_indicators/phase-b-private-review-byte-preserving-resume-r2-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
