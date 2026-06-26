# Observability Pane Recovery Contract 2026-06-22

Date: 2026-06-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: observability-pane-recovery-contract-2026-06-22
Phase-A-Lock: LOCKED
Purpose: Repair the pre-push failure where the tmux pane recovery-status test expects the historical active-recovery headline while the current pane renderer emits the newer compact plain-English recovery wording. Keep the fix scoped to observability/test contract alignment so pending Nightly and Stage 4 runtime work do not absorb tooling drift.

## Scope

Pipeline-hardening observability/test contract repair only. Align the tmux pane active-recovery output and the recovery worktree-resolution regression so the pre-push gate reflects the intended founder-facing dashboard behavior.

Files and surfaces in scope:

- tools/observability/_pane_processes.sh (MODIFY IF NEEDED) -- active recovery display contract used by the root tools path.
- mu/tools/observability/_pane_processes.sh (MODIFY IF NEEDED) -- mirrored active recovery display contract used by the mu tools path.
- tests/tools/test_recovery_gate.py (MODIFY IF NEEDED) -- update the regression to assert the intended active recovery wording and failure detail without accepting loss of worktree resolution.
- reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-22 tracker sync note for wave `observability-pane-recovery-contract-2026-06-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/observability-pane-recovery-contract-2026-06-22_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reproduce the failing pre-push assertion from the Nightly lane using the focused test.
2. Inspect the current pane renderer output for tier3_waiting_on_agent recovery and decide whether the renderer should restore the active Tier headline, the test should accept the compact wording, or both should be tightened.
3. Keep the Watching: active-worktree assertion intact so the live-root selection contract remains protected.
4. Keep the active recovery failure detail visible enough for operators; do not hide the failure class entirely behind the compact summary.
5. Run the configured evidence command, collect the indicator artifact, and leave commit/push to the pipeline.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor. Do not hand-author receipts or manually commit this wave.
- No runtime, substrate, seed, registry, matcher, StructuralNumbers, Stage 4 implementation, or Nightly GCD test files may change.
- Do not bypass pre-push-fast. The root cause must be fixed so the hook passes normally.
- Keep tools/ and mu/tools/ observability copies synchronized if both paths exist and the contract applies to both.
- Do not weaken the test to only check command success; it must still prove active-worktree resolution and active recovery visibility.

## Stop conditions

- Halt if the only way to pass is to remove active recovery visibility from the pane.
- Halt if the change requires touching runtime, substrate, Stage 4, or GCD repair files.
- Halt if tools/ and mu/tools/ observability paths would diverge without a documented local convention.
- Do not commit without pipeline-produced handoff, receipt, focused test evidence, and docs consistency.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- The focused failing test passes and still asserts Watching: jabramsja/active-wave.
- The regression asserts an active Tier 3 recovery signal and the agent_review_crash problem detail, either through restored headline wording or the accepted compact wording.
- tools/observability/_pane_processes.sh and mu/tools/observability/_pane_processes.sh remain synchronized for the active recovery rendering logic.
- No non-observability runtime or structuralization files appear in the diff.
- The configured evidence command passes and the L4 indicator artifact is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `observability-pane-recovery-contract-2026-06-22`.
- Governing packet: this file, `reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md`.
- TASKS.md authority: the 2026-06-22 tracker sync note for wave `observability-pane-recovery-contract-2026-06-22` is canonical for this packet's L4 fields.
- Authorization: Opened after the Nightly GCD repair reached local commit but pre-push-fast failed on the pane recovery wording regression. This is a separate pipeline-hardening lane so the GCD repair is not manually amended or pushed with a hook bypass.

FOUNDER_OVERRIDE:observability-pane-recovery-contract-2026-06-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `observability-pane-recovery-contract-2026-06-22`
- Active packet: `reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md`
- Indicator artifact: `reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_processes.sh`
  - `reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md`
  - `reports/control_plane/observability-pane-recovery-contract-2026-06-22_wave_config.json`
  - `reports/deferred/non_blocking/observability-pane-recovery-contract-2026-06-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `observability-pane-recovery-contract-2026-06-22`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/observability-pane-recovery-contract-2026-06-22_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id observability-pane-recovery-contract-2026-06-22 --output reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: observability-pane-recovery-contract-2026-06-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `observability-pane-recovery-contract-2026-06-22`
- Active packet: `reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5a369a985f9a2eac9dd7eb3c72d1af447be6c911ddc8eb2d0bea95be545e6a53`
- Indicator artifact: `reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/observability/_pane_processes.sh`
  - `reports/control_plane/observability-pane-recovery-contract-2026-06-22_2026-06-22.md`
  - `reports/control_plane/observability-pane-recovery-contract-2026-06-22_wave_config.json`
  - `reports/deferred/non_blocking/observability-pane-recovery-contract-2026-06-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/observability-pane-recovery-contract-2026-06-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
