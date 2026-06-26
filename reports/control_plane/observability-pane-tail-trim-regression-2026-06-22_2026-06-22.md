# Observability Pane Tail Trim Regression 2026-06-22

Date: 2026-06-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: observability-pane-tail-trim-regression-2026-06-22
Phase-A-Lock: LOCKED
Purpose: Repair the bot-remediation trim regression on the existing PR branch for PR #1148 so constrained tmux panes keep the active recovery problem detail while preserving useful tail context.
Lane: control-surface observability pipeline-hardening
Authorization: authorized control-surface L4_ENABLER; standing pipeline-bug-fix authorization for bounded PR #1148 same-branch repair.

## Scope

Control-surface observability repair only. Land on the existing PR branch for PR #1148 and repair the constrained-pane tail-trim regression without touching runtime, substrate, seed, Stage 4, matcher, StructuralNumbers, or Nightly GCD files.

Files and surfaces in scope:

- tools/observability/_pane_processes.sh (MODIFY IF NEEDED) -- root observability pane trim contract.
- mu/tools/observability/_pane_processes.sh (MODIFY IF NEEDED) -- mirrored Mu observability pane trim contract.
- tests/tools/test_recovery_gate.py (MODIFY IF NEEDED) -- focused regression coverage for recovery problem detail plus last-pager/tail visibility.
- reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-22 tracker sync note for wave `observability-pane-tail-trim-regression-2026-06-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the current focused pre-push failure on the existing PR branch and capture the missing recovery problem detail.
2. Adjust the pane trim budgeting so a constrained pane with RECOVERY keeps an active Tier 3 signal and either the explicit problem line or agent_review_crash signal.
3. Preserve a useful post-recovery tail or last-pager signal when there is enough pane budget, instead of hiding the tail entirely.
4. Keep tools and mu/tools observability copies synchronized when both paths are in scope.
5. Run the configured evidence command, collect the indicator artifact, and leave commit, push, and PR update to the commit executor.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor. Do not hand-author receipts, handoffs, commits, pushes, or PR updates.
- This is an authorized same-branch control-surface repair for the existing PR branch; do not create a separate runtime or Nightly GCD repair branch from this wave.
- No runtime, substrate, seed, registry, matcher, StructuralNumbers, Stage 4, or Nightly GCD test files may change.
- Do not bypass pre-push-fast. The root observability regression must be fixed so the hook passes normally.
- Do not weaken the regression to only check command success; it must still prove active-worktree resolution, active recovery visibility, and problem-detail visibility.

## Stop conditions

- Halt if recovery problem detail cannot fit without removing the active recovery signal.
- Halt if the fix requires touching runtime, substrate, Stage 4, matcher, StructuralNumbers, or Nightly GCD repair files.
- Halt if tools and mu/tools observability paths would diverge without a documented local convention.
- Do not commit without pipeline-produced handoff, receipt, focused evidence, docs consistency, and ratchet checks.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- The focused failing pre-push test passes and still asserts Watching: jabramsja/active-wave.
- A constrained pane with active Tier 3 recovery preserves a recovery signal and the problem detail or agent_review_crash signal.
- A constrained pane still preserves useful tail context or last-pager visibility when enough rows are available.
- tools/observability/_pane_processes.sh and mu/tools/observability/_pane_processes.sh remain synchronized for the trim contract.
- No non-observability runtime or structuralization files appear in the diff.
- The configured evidence command passes and the L4 indicator artifact is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `observability-pane-tail-trim-regression-2026-06-22`.
- Governing packet: this file, `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md`.
- TASKS.md authority: the 2026-06-22 tracker sync note for wave `observability-pane-tail-trim-regression-2026-06-22` is canonical for this packet's L4 fields.
- Authorization: Authorized control-surface L4_ENABLER same-PR repair on the existing PR branch for PR #1148 under standing pipeline-bug-fix authorization. Scope is limited to observability pane trim contract, focused tests, tracker, packet, and indicator surfaces.

FOUNDER_OVERRIDE:observability-pane-tail-trim-regression-2026-06-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `observability-pane-tail-trim-regression-2026-06-22`
- Active packet: `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md`
- Indicator artifact: `reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_processes.sh`
  - `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md`
  - `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_wave_config.json`
  - `reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id observability-pane-tail-trim-regression-2026-06-22 --output reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: observability-pane-tail-trim-regression-2026-06-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `observability-pane-tail-trim-regression-2026-06-22`
- Active packet: `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2fec60d461685eb1386ae26041f96e0b63e2ba02aedd25bde7e6465df7a33476`
- Indicator artifact: `reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_processes.sh`
  - `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_2026-06-22.md`
  - `reports/control_plane/observability-pane-tail-trim-regression-2026-06-22_wave_config.json`
  - `reports/l4_wave_indicators/observability-pane-tail-trim-regression-2026-06-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
