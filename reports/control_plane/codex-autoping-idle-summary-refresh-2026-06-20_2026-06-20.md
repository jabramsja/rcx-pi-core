# Codex Autoping Idle Summary Refresh 2026-06-20

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: codex-autoping-idle-summary-refresh-2026-06-20
Phase-A-Lock: LOCKED
Purpose: Fix the Codex autoping watcher so an idle-no-wave state refreshes the durable summary text instead of leaving a stale attention-required message from an earlier wave.

## Scope

Pipeline/operator tooling only: Codex autoping watcher idle-state summary refresh. Do not touch runtime, substrate, seed, StructuralNumbers, arithmetic gates, JS parity, implementer/reviewer role selection, pager route selection, or tmux layout behavior beyond any direct test harness needed for this watcher branch.

Files and surfaces in scope:

- mu/tools/session/codex_autoping_watch.py (MODIFY) -- write a neutral durable summary when the watcher reaches idle_no_wave.
- mu/tests/tools/test_codex_autoping_watch.py (MODIFY) -- add or extend fake-state regression coverage for stale summary replacement in the idle branch.
- reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `codex-autoping-idle-summary-refresh-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Add a deterministic idle summary string for the Codex autoping watcher that includes enough context to distinguish idle/no-wave from attention-required.
2. Write that summary to summary_path before or with the idle_no_wave state update, and record last_summary consistently in the state payload.
3. Add focused tests that start from a stale attention-required summary and prove the idle branch replaces it without launching real Codex, Claude, or tmux.
4. Run the configured evidence command and collect the indicator artifact.

## Constraints

- Use the pipeline launcher and dispatcher path for this wave.
- Do not manually edit generated packet/tracker/routing surfaces outside the launcher/builder path.
- Do not launch real Codex, Claude, or persistent tmux windows in tests.
- Do not alter orchestrator mode, role_agents, bridge_agent_defaults, or pager route defaults in this wave.
- Do not touch runtime, substrate, seed, registry, projection seed, JS parity, or StructuralNumbers files.

## Stop conditions

- Stop done when idle_no_wave writes an accurate durable summary, regression coverage passes, the evidence command passes, the indicator artifact is collected, and commit/push/PR are handled through the commit executor.
- Halt as NEEDS_RESCOPING if summary freshness requires redesigning the autoping runner or tmux pane renderer rather than the watcher idle branch.
- Halt as POLICY_BOUND if the fix requires hidden Codex state mutation beyond the watcher-owned state/summary files.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_codex_autoping_watch.py`

## Acceptance criteria

- A watcher cycle with no active wave/job writes a neutral idle summary to summary_path.
- The idle summary replaces a stale attention-required summary from a previous wave.
- The JSON state for idle_no_wave records last_summary consistently with the durable summary file.
- The summary includes the selected repo root or bus context, so the operator can tell which watcher is idle.
- Existing attention_required summary behavior remains unchanged.
- Tests pass without real Codex, Claude, or tmux.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `codex-autoping-idle-summary-refresh-2026-06-20`.
- Governing packet: this file, `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `codex-autoping-idle-summary-refresh-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder-directed autonomous queue continuation after codex-mode switch closeout: the operator identified a live stale-summary defect in the Codex autoping surface and directed autonomous wave execution instead of manual reporting.

FOUNDER_OVERRIDE:codex-autoping-idle-summary-refresh-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `codex-autoping-idle-summary-refresh-2026-06-20`
- Active packet: `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tools/session/codex_autoping_watch.py`
  - `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md`
  - `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id codex-autoping-idle-summary-refresh-2026-06-20 --output reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_codex_autoping_watch.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: codex-autoping-idle-summary-refresh-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `codex-autoping-idle-summary-refresh-2026-06-20`
- Active packet: `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9a44e9d93bdfcb44254cc0f9d3b920734f7c70147f21e257fd9b7673d3ccd777`
- Indicator artifact: `reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_codex_autoping_watch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_codex_autoping_watch.py`
  - `mu/tools/session/codex_autoping_watch.py`
  - `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_2026-06-20.md`
  - `reports/control_plane/codex-autoping-idle-summary-refresh-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/codex-autoping-idle-summary-refresh-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
