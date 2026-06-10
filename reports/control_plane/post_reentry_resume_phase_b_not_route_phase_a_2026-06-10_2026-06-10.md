# Post Reentry Resume Phase B Not Route Phase A 2026-06-10 2026-06-10

Date: 2026-06-10
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-reentry-resume-phase-b-not-route-phase-a-2026-06-10
Phase-A-Lock: LOCKED
Purpose: GOAL: Fix the dispatcher's post_reentry recovery doing a disproportionate full ROUTE_PHASE_A re-run instead of RESUMING the already-seeded Phase B re-entry. When the pre-commit supervisor returns NEEDS_PHASE_B after a post-GO re-entry (post_reentry_needs_phase_b), the Tier-1 recovery recovery_gate.fix_post_reentry_needs_phase_b SEEDS the phase_b_state.json resume state and returns action=resume_phase_b_reentry, and the dispatcher PRESERVES that state (the executor_dispatch state-preservation branch when recovery.action==resume_phase_b_reentry). BUT the dispatcher then routes ROUTE_PHASE_A (a full ~1.5h Phase A->B re-run), discarding the seeded re-entry. This disproportionate re-run wastes a cycle and can compound into a re-route loop -- verified this session: it stranded waves #60 and #63, each needing a manual commit_executor --standalone hand-finish.

## Scope

Route a recovered `post_reentry_needs_phase_b` to RESUME Phase B (consume the seeded `phase_b_state.json`) instead of a full `ROUTE_PHASE_A` re-run. Tooling-only `L4_ENABLER`; no runtime dirs.

Files/directories in scope:
- `mu/tools/executors/recovery_gate.py` -- `fix_post_reentry_needs_phase_b` (the Tier-1 recovery that seeds `phase_b_state.json` and returns `action=resume_phase_b_reentry`).
- `mu/tools/executors/executor_dispatch.py` -- the dispatcher's post-recovery routing (`_recovered_retry_record`, `ROUTING_DISPATCH`, and the state-preservation branch for `recovery.action==resume_phase_b_reentry`).
- `mu/tests/tools/test_recovery_gate.py` -- regression coverage for the recovery.
- `mu/tests/tools/test_executor_dispatch.py` -- regression coverage for the dispatcher routing.

## Work items

(Concrete, bounded tasks derived from the Post-Merge Supervisor request below and the TASKS.md `progress_proof_after`.)

1. Route the recovered `post_reentry_needs_phase_b` to `ROUTE_PHASE_B` (resume) instead of `ROUTE_PHASE_A`. Implement by the post_reentry recovery emitting a `retry_record` carrying `decision=ROUTE_PHASE_B` (so the dispatcher's `_recovered_retry_record` routes to `phase_b_executor`, and the preserved `phase_b_state.json` drives the resume), and/or by the dispatcher routing to `ROUTE_PHASE_B` when `recovery.action==resume_phase_b_reentry` and the seeded state is present. Confirm the exact decision point by reading BOTH `fix_post_reentry_needs_phase_b` and the dispatcher's post-recovery routing; choose the minimal correct change.
2. Keep the existing state-preservation -- the dispatcher already preserves the seeded `phase_b_state.json` when `recovery.action==resume_phase_b_reentry`; do not regress it.
3. Fail-safe for un-resumable cases: a genuinely un-resumable post_reentry (missing `plan_path` / un-seedable state) MUST still fail safe -- surface the failure, do not silently skip or weaken.
4. (Secondary, optional) For an all-non-blocking residual, the recovery MAY proceed straight to commit instead of re-entering Phase B -- only if cleanly determinable from the seeded state.
5. Add regression coverage in `test_recovery_gate.py` / `test_executor_dispatch.py`: (a) a recovered `post_reentry_needs_phase_b` yields `ROUTE_PHASE_B` (resume), not `ROUTE_PHASE_A`; (b) a genuinely un-seedable case still fails safe; (c) other recovery classes' routing is unchanged.

## Constraints

What is NOT in scope:
- MUST NOT touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers` (`L4_ENABLER` boundary).
- No masking: no `retry` / `skip` / `xfail`; do not weaken existing recovery/dispatch tests.
- Scope strictly to the `post_reentry_needs_phase_b` routing; do NOT change other recovery classes' routing.
- No new host-only semantics; this is a structural routing fix in the tooling layer only.

## Stop conditions

- If the minimal correct change cannot be confined to `recovery_gate.py` + `executor_dispatch.py` + their tests (e.g. it would require touching a runtime dir or changing how `phase_b_executor` consumes the seeded state), STOP and surface the boundary instead of widening scope.
- If routing post_reentry to `ROUTE_PHASE_B` cannot be done without changing other recovery classes' routing or weakening an existing recovery/dispatch test, STOP.
- If the seeded `phase_b_state.json` cannot drive a resume without a runtime/substrate change, STOP and report (do not add host-only semantics to force it).
- If the `evidence_command` tests cannot pass without masking (retry/skip/xfail), STOP -- an honest failing test is the correct outcome, not a weakened one.

## Acceptance criteria

- A recovered `post_reentry_needs_phase_b` routes to `ROUTE_PHASE_B` and resumes from the seeded `phase_b_state.json` (NOT a full `ROUTE_PHASE_A` re-run).
- A genuinely un-resumable post_reentry (missing `plan_path` / un-seedable state) fails safe -- the failure is surfaced, not silently skipped or weakened.
- Other recovery classes' routing is unchanged; the existing state-preservation is retained.
- Regression tests added: recovered post_reentry -> `ROUTE_PHASE_B` resume; un-seedable -> fail safe; other recovery classes unchanged.
- `evidence_command` passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_executor_dispatch.py`.
- No runtime dir touched; no masking; diff confined to the in-scope files.

## Grounding / Authorization

- TASKS.md authorization: `[NEXT-CODEX-POST-REDTEAM]` tracker sync note (2026-06-10), TASKS.md `[NEXT-CODEX-POST-REDTEAM]` -- packet ref `reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`, Class `L4_ENABLER`, `target_gate_id: G8`.
- FOUNDER_OVERRIDE:post-reentry-resume-phase-b-not-route-phase-a-2026-06-10
- Authorization: standing pipeline-bug-fix authorization for autonomous executor/control-plane recovery-routing fixes; wave-bound to the FOUNDER_OVERRIDE above so commit automation can derive the same-wave override mechanically from this line and from TASKS.md `[NEXT-CODEX-POST-REDTEAM]`.
- Governing packet: this file (`reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`); L4 fields are auto-derived from the canonical TASKS.md tracker note (see the `L4_FIELDS_FROM_TRACKER` block below).

## Request from Post-Merge Supervisor

GOAL: Fix the dispatcher's post_reentry recovery doing a disproportionate full ROUTE_PHASE_A re-run instead of RESUMING the already-seeded Phase B re-entry. When the pre-commit supervisor returns NEEDS_PHASE_B after a post-GO re-entry (post_reentry_needs_phase_b), the Tier-1 recovery recovery_gate.fix_post_reentry_needs_phase_b SEEDS the phase_b_state.json resume state and returns action=resume_phase_b_reentry, and the dispatcher PRESERVES that state (the executor_dispatch state-preservation branch when recovery.action==resume_phase_b_reentry). BUT the dispatcher then routes ROUTE_PHASE_A (a full ~1.5h Phase A->B re-run), discarding the seeded re-entry. This disproportionate re-run wastes a cycle and can compound into a re-route loop -- verified this session: it stranded waves #60 and #63, each needing a manual commit_executor --standalone hand-finish.

CONTEXT (verified by reading the code): recovery_gate.fix_post_reentry_needs_phase_b writes a resume_state (plan_path, completed_step='needs_phase_b_reentry', scope files, bridge_rounds, all_non_blocking) to phase_b_state.json and returns _fix_result(True, 'resume_phase_b_reentry', ...). The dispatcher's _recovered_retry_record routes per a recovered result's retry_record ONLY when that retry_record carries a decision in ROUTING_DISPATCH (consumed in the Phase-B in-process retry path). The post_reentry recovery does NOT supply a retry_record with decision=ROUTE_PHASE_B, so _recovered_retry_record returns None and the dispatcher falls back to ROUTE_PHASE_A (re-running Phase A) instead of resuming Phase B from the seeded state. The dispatcher already preserves the seeded phase_b_state.json when recovery.action==resume_phase_b_reentry.

REQUIRED FIX: route a recovered post_reentry_needs_phase_b to RESUME Phase B (re-invoke phase_b_executor, which consumes the seeded phase_b_state.json) instead of ROUTE_PHASE_A. Implement by having the post_reentry recovery emit a retry_record carrying decision=ROUTE_PHASE_B (so the dispatcher's _recovered_retry_record routes to phase_b_executor and the preserved phase_b_state.json drives the resume), and/or by the dispatcher routing to ROUTE_PHASE_B when recovery.action==resume_phase_b_reentry and the seeded state is present. The implementer MUST confirm the exact decision point by reading both fix_post_reentry_needs_phase_b and the dispatcher's post-recovery routing, and choose the minimal correct change. Keep the existing state-preservation. A genuinely un-resumable post_reentry (missing plan_path / un-seedable state) MUST still fail safe (surface the failure, not silently skip or weaken). Optionally, for an all-non-blocking residual, the recovery MAY proceed straight to commit instead of re-entering Phase B (secondary; only if cleanly determinable from the seeded state). Add a regression test: a recovered post_reentry_needs_phase_b yields ROUTE_PHASE_B (resume), not ROUTE_PHASE_A, and a genuinely un-seedable case still fails safe; other recovery classes' routing is unchanged.

This is an L4_ENABLER tooling-only change (recovery_gate.py + executor_dispatch.py + their tests): MUST NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). No masking (no retry/skip/xfail; do not weaken existing recovery/dispatch tests). Scope strictly to the post_reentry_needs_phase_b routing; do not change other recovery classes' routing.

Routed next-candidate:
post-reentry-resume-phase-b-not-route-phase-a-2026-06-10

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id post-reentry-resume-phase-b-not-route-phase-a-2026-06-10 --output reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor package is staged at .scratch/phase_b_supervisor_package.json; commit handoff receipt remains pending the supervisor decision..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `post-reentry-resume-phase-b-not-route-phase-a-2026-06-10`
- Active packet: `reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`
- Indicator artifact: `reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`
  - `reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-reentry-resume-phase-b-not-route-phase-a-2026-06-10`
- Active packet: `reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0b2573f18c5c98f399ead7ea9c4c5369b0d2a3ea111a316f2018c9cf662d0e9c`
- Indicator artifact: `reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor package is staged at .scratch/phase_b_supervisor_package.json; commit handoff receipt remains pending the supervisor decision..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/post_reentry_resume_phase_b_not_route_phase_a_2026-06-10_2026-06-10.md`
  - `reports/l4_wave_indicators/post-reentry-resume-phase-b-not-route-phase-a-2026-06-10.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
