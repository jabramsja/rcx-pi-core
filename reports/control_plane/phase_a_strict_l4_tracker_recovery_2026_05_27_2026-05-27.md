# Phase A Strict L4 Tracker Recovery 2026 05 27

Date: 2026-05-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-a-strict-l4-tracker-recovery-2026-05-27
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Repair Phase A strict staged L4 tracker-authority recovery after bridge GO failed the strict staged L4 pre-lock guard because TASKS.md lacked a detector-visible tracker sync note for a strict staged L4 wave id.

## Scope

Files and surfaces in scope for the recovery wave:

- `mu/tools/executors/phase_a_executor.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `TASKS.md`, only for a detector-visible same-wave tracker sync note if the implementation or strict staged L4 validation requires one.
- `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`, only as the canonical generated L4 indicator artifact required by tracker-sync validation.
- This governing packet: `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`.
- Repo builder/API-backed handoff and receipt surfaces used by dispatcher, Phase B, pre-commit, and commit-executor routing. These surfaces are in scope only as generated pipeline artifacts, not as hand-authored implementation substitutes.

The failure class is bounded to Phase A strict staged L4 recovery before lock: bridge review can converge GO, then `lock_plan` can fail because a strict staged L4 `--wave-id` has no detector-visible TASKS.md tracker sync note.

- `reports/deferred/non_blocking/phase-a-strict-l4-tracker-recovery-2026-05-27_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Red-team the current manual recovery diff honestly before accepting it. The existing packet says the intended fix and focused regression are already present in the local manual recovery diff; Phase B must verify current code truth and adjust only if needed.

2. Mechanize the strict staged L4 missing-tracker recovery path in `mu/tools/executors/phase_a_executor.py`: when Phase A bridge/implementer recovery reaches this specific pre-lock failure class, allow one bounded recovery pass that may edit only the packet and `TASKS.md`, then require bridge review to run again before any lock.

3. Preserve the existing non-interactive pipeline route. Do not use `run_review.py`. Preserve `executor_config.json` behavior where `agent_review_enabled=false`. Use dispatcher, builder/API-backed handoff, receipt, pre-commit, and commit-executor surfaces instead of hand-authored bypasses.

4. Keep or add focused regression coverage in `mu/tests/tools/test_executor_dispatch.py` for `TestPhaseAStrictStagedL4Guard::test_run_phase_a_recovers_strict_staged_l4_missing_tracker_before_lock`. The regression must prove the missing-tracker failure is recovered before lock, bounded to packet plus `TASKS.md`, and followed by bridge re-review before locking.

5. If this wave needs a `TASKS.md` tracker note to satisfy strict staged L4 validation, add it using repo tracker-sync conventions and this same-wave override: `FOUNDER_OVERRIDE:phase-a-strict-l4-tracker-recovery-2026-05-27`.

6. Produce a proper pipeline handoff/receipt for the bounded repair. The handoff must describe the strict staged L4 failure, the exact files changed, the focused regression, and the validation evidence.

## Constraints

- Do not edit production runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, Claude-related files, CI workflow files, branch protection, check names, or the seven-check GitHub surface.
- Do not weaken strict staged L4 validation, `lock_plan`, tracker-sync detection, bridge re-review, pre-commit, or commit-executor governance.
- Do not widen the recovery pass beyond packet plus `TASKS.md` for the missing-tracker correction.
- Do not use `run_review.py`, interactive review loops, manual merge shortcuts, or hand-authored bypass artifacts.
- Do not flip or depend on `agent_review_enabled=true`; preserve the current `agent_review_enabled=false` route.
- Do not relist already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not treat the predecessor strict staged L4 runtime wave as in scope. This packet repairs the Phase A tracker-authority failure class only.

## Stop Conditions

- Stop if the repair needs any file outside the scoped executor, test, packet, tracker note, generated L4 indicator artifact, or generated pipeline handoff/receipt surfaces.
- Stop if the implementation would bypass bridge re-review after a recovery pass, lock a packet after stale review, or make `lock_plan` tolerate missing detector-visible TASKS.md authority.
- Stop if strict staged L4 validation requires broader tracker semantics than a same-wave packet plus `TASKS.md` recovery can honestly provide.
- Stop if the focused regression cannot prove the missing-tracker recovery path without weakening existing strict staged L4 guard behavior.
- Stop if Phase B discovers the manual recovery diff is already fully landed and no code/test change remains; in that case, convert the wave to a tracker/handoff validation closeout instead of reimplementing landed work.
- Stop if the work drifts into solving `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27` runtime behavior rather than the Phase A tracker-authority recovery mechanism.

## Acceptance Criteria

- The packet has explicit Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections before bridge review.
- `mu/tools/executors/phase_a_executor.py` supports exactly one bounded strict staged L4 missing-tracker recovery pass before lock, restricted to the packet and `TASKS.md`.
- Bridge review is rerun after that recovery pass and before locking; stale bridge GO cannot be reused after the tracker repair.
- `mu/tests/tools/test_executor_dispatch.py::TestPhaseAStrictStagedL4Guard::test_run_phase_a_recovers_strict_staged_l4_missing_tracker_before_lock` covers the failure class and passes.
- `agent_review_enabled=false` remains the route, and no `run_review.py` path is introduced.
- No out-of-scope production runtime, CI, branch-protection, check-name, seven-check GitHub, Claude, Stage0, seed, scheduler, registry, parity, or host-oracle files are edited.
- Required validations pass at minimum:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile mu/tools/executors/phase_a_executor.py`
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestPhaseAStrictStagedL4Guard::test_run_phase_a_recovers_strict_staged_l4_missing_tracker_before_lock -p no:cacheprovider`
  - `git diff --check`
  - Strict staged L4 validation for `phase-a-strict-l4-tracker-recovery-2026-05-27` once the same-wave tracker note exists.
- Pipeline handoff/receipt evidence records the exact repair, focused regression, and strict staged L4 validation result.

## Grounding / Authorization

- `TASKS.md:634-638` keeps `[NEXT-CODEX-POST-REDTEAM]` open and says the queue remains open for future bounded work not already proven by landed slices.
- `TASKS.md:642` authorizes autonomous non-interactive dispatcher/pipeline work and says manual pipeline repair is allowed only as an unblocker when paired with a same-wave mechanical/automated fix in dispatcher, builder, recovery, commit, pre-commit, or another appropriate pipeline surface.
- Governing packet: `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`.
- Direct failure evidence preserved from the supervisor request: Phase A bridge converged GO for `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27`, then failed with `Phase A strict staged L4 guard failed before lock: TASKS.md lacks detector-visible tracker sync note(s) for strict staged L4 wave id(s): n3-ci-runtime-mu-algorithm-hotpath-2026-05-27`.
- Root contradiction to repair: `mu/tools/executors/phase_a_executor.py` allowed bridge/implementer recovery only for the packet file while `lock_plan` requires detector-visible TASKS.md authority for strict staged L4 `--wave-id` commands.
- Authorization: standing pipeline-bug-fix authorization from `TASKS.md:642` for a bounded unblocker paired with a same-wave mechanical pipeline fix.
- FOUNDER_OVERRIDE:phase-a-strict-l4-tracker-recovery-2026-05-27

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `phase-a-strict-l4-tracker-recovery-2026-05-27`
- Active packet: `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`
  - `reports/deferred/non_blocking/phase-a-strict-l4-tracker-recovery-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `phase-a-strict-l4-tracker-recovery-2026-05-27`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/phase-a-strict-l4-tracker-recovery-2026-05-27_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-a-strict-l4-tracker-recovery-2026-05-27`
- Active packet: `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5d35da8c211c0e2250d9fbf4b98ffc8900fa7f0fc38ebc044199dd60d94f2a9c`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase_a_strict_l4_tracker_recovery_2026_05_27_2026-05-27.md`
  - `reports/deferred/non_blocking/phase-a-strict-l4-tracker-recovery-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/phase-a-strict-l4-tracker-recovery-2026-05-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
