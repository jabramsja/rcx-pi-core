# Pipeline Hardening Conflict Refresh 2026-06-26

Date: 2026-06-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-hardening-conflict-refresh-2026-06-26
Phase-A-Lock: LOCKED
Purpose: Harden the autonomous control-plane before the next math-structure waves. Fix recovery_gate.classify_failure so engine-discipline assertion failures shaped like assert set(...) classify as test_failure instead of unknown_error. Add a per-wave max_turns override to WaveConfig and launch_wave that affects supported bridge commands used for that launched wave, while failing closed instead of writing unsupported max-turn flags to Codex commands. Then queue bounded conflict-refresh packets for PR #1139 and PR #1140 through launcher-compatible config artifacts, without manually rebasing or merging those PRs.

## Scope

Pipeline hardening only. Touch recovery classification, wave launcher config parsing and bridge-command override plumbing, focused tests, TASKS.md and STATUS.md tracker truth if needed, and launcher-compatible control-plane packets for PR #1139 and PR #1140. Do not advance surreals, recursive ordinals, W-types, coinduction, fixpoint, or optimization in this wave.

Files and surfaces in scope:

- TASKS.md (MODIFY) -- tracker sync and queue status after the hardening packet lands.
- STATUS.md (MODIFY IF NEEDED) -- next milestone and current queue wording only if the active next item changes.
- mu/tools/executors/recovery_gate.py (MODIFY) -- classify engine-discipline assert set failures as test_failure.
- mu/tools/executors/launch_wave.py (MODIFY) -- add typed per-wave max_turns config support and launcher metadata.
- mu/tools/executors/executor_common.py (MODIFY IF NEEDED) -- provide bridge command max-turn helpers that update supported tokens and reject unsupported Codex max-turn requests.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- regression for assert set engine-discipline assertion classification.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- regressions for max_turns config validation, metadata, and bridge command application.
- mu/tests/tools/test_executor_dispatch.py (MODIFY IF NEEDED) -- only if dispatcher child-env or routing propagation is part of the implementation.
- reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md (GENERATED) -- launcher-created control packet.
- reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_wave_config.json (KEEP) -- launcher config for this wave.
- reports/control_plane/*1139*conflict*refresh* (CREATE) -- bounded launcher-compatible packet or config for PR #1139 conflict refresh.
- reports/control_plane/*1140*conflict*refresh* (CREATE) -- bounded launcher-compatible packet or config for PR #1140 conflict refresh.
- reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json (GENERATED) -- indicator artifact for this wave.
- TASKS.md -- tracker-sync authority. The 2026-06-26 tracker sync note for wave `pipeline-hardening-conflict-refresh-2026-06-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the current classification issue with a minimal classify_failure regression that includes an engine-discipline assertion shaped like assert set(...).
2. Add the narrowest recovery_gate classifier logic that maps that assertion family to FailureClass.TEST_FAILURE while preserving explicit PR conflict and policy classifications.
3. Add max_turns to WaveConfig as an optional typed field with validation that rejects non-positive, non-integer, or unsafe values.
4. Apply the per-wave max_turns only to the bridge command used for that launched wave, not globally to executor_config.json or unrelated buses.
5. Cover bridge command shapes: commands that already contain --max-turns must be updated, supported Claude commands without the token must receive it, and Codex commands must not receive unsupported max-turn flags.
6. Surface the max_turns override in launch metadata so the operator can see what the wave requested without leaking secrets.
7. Create precise conflict-refresh packet/config artifacts for PR #1139 and PR #1140, each bounded to refreshing dirty but green PR branches through the pipeline.
8. Do not manually rebase, merge, or alter PR #1139 or PR #1140 from this wave; the output is queued packet truth unless the pipeline executor itself performs an authorized bounded refresh.
9. Collect the L4 indicator artifact, run the evidence command, and leave commit, PR creation, review, CI, and merge handling to the pipeline commit executor.

## Constraints

- Use launch_wave.py, executor_dispatch, Phase A, Phase B, bridge review, and commit executor; do not hand-author the implementation package or bypass review.
- Implementer, reviewer, and pager route are Codex.
- No runtime, seed, Python substrate, or JavaScript substrate semantic changes are authorized in this wave.
- No new host-authority sites; this is control-plane plumbing and tests only.
- Do not create a broad catch-all classifier that turns arbitrary AssertionError text into test_failure.
- Do not change default max-turn budgets globally unless directly required by a focused failing test and explicitly justified.
- Do not advance surreals, recursive ordinals, W-types, coinduction, fixpoint, or optimization.
- Do not manually resolve PR #1139 or PR #1140 conflicts outside the queued pipeline packets.

## Stop conditions

- Halt as DEFECT if the new classifier masks PR conflict, L4 contract, policy, or agent review failures as test_failure.
- Halt as DEFECT if max_turns changes the committed bridge defaults or unrelated live buses instead of the launched wave path.
- Halt as DEFECT if the max_turns override is accepted by config but not visible in the command or metadata used by the dispatcher launch.
- Halt as POLICY_BOUND if refreshing #1139 or #1140 requires founder approval beyond bounded dirty-branch conflict refresh.
- Halt as NEEDS_RESCOPING if this wave requires runtime or math-structure changes.
- Do not commit without focused tests, docs consistency, L4 contract enforcement, indicator collection, bridge review, and commit-executor handling.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- classify_failure returns FailureClass.TEST_FAILURE for the engine-discipline assert set assertion family.
- Existing PR conflict and local pytest classification regressions still pass.
- WaveConfig accepts a valid max_turns override and rejects invalid values.
- launch_wave applies max_turns to supported bridge commands for the launched wave and fails closed for unsupported Codex max-turn requests.
- Launch metadata records the requested max_turns override alongside role and pager pins.
- Launcher-compatible conflict-refresh packet/config artifacts exist for PR #1139 and PR #1140 and are not manual rebase instructions.
- Focused py_compile, pytest, docs consistency, L4 contract, indicator collection, and git diff checks pass.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-hardening-conflict-refresh-2026-06-26`.
- Governing packet: this file, `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md`.
- TASKS.md authority: the 2026-06-26 tracker sync note for wave `pipeline-hardening-conflict-refresh-2026-06-26` is canonical for this packet's L4 fields.
- Authorization: Founder-directed autonomous queue continuation after Stage 4 red-team: pipeline hardening is the next authorized item, with implementer=codex, reviewer=codex, pager/autoping/tmux in Codex mode, and no founder decision required unless a real stop condition triggers.

FOUNDER_OVERRIDE:pipeline-hardening-conflict-refresh-2026-06-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-hardening-conflict-refresh-2026-06-26`
- Active packet: `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md`
  - `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/control_plane/pr-1139-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/control_plane/pr-1140-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-hardening-conflict-refresh-2026-06-26 --output reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-hardening-conflict-refresh-2026-06-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-hardening-conflict-refresh-2026-06-26`
- Active packet: `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5077a7d967db5eb51d64be23c5a288d6643e42a141656f76b7dd6a80da86fabb`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_2026-06-26.md`
  - `reports/control_plane/pipeline-hardening-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/control_plane/pr-1139-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/control_plane/pr-1140-conflict-refresh-2026-06-26_wave_config.json`
  - `reports/l4_wave_indicators/pipeline-hardening-conflict-refresh-2026-06-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
