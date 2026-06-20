# NEXT-CODEX-POST-REDTEAM - Phase B blocking finding convergence hardening

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-b-blocking-finding-convergence-hardening-2026-06-20
Phase-A-Lock: LOCKED
Purpose: Harden Phase B so a reviewer NO_GO or REQUEST_CHANGES finding classified as blocking can never be persisted or resumed as deferred non-blocking bridge convergence, and so post-Phase-A control-packet line-reference drift is checked before final pytest, supervisor, or commit handoff.

## Scope

Pipeline hardening only. This wave may modify Phase B executor logic, focused Phase B executor tests, this control packet/config, TASKS.md via the launcher tracker-note builder, and the generated L4 indicator artifact.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- enforce fail-closed bridge convergence and pre-finalization packet lint.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- add regressions for blocking-finding state contradictions and post-bridge control-packet line-ref drift.
- reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_wave_config.json (NEW) -- launcher input for this wave.
- reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `phase-b-blocking-finding-convergence-hardening-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Add a deterministic guard in Phase B before bridge_converged finalization that reclassifies or validates accumulated deferred/non-blocking findings and fails closed if any effective disposition is blocking.
2. Ensure REQUEST_CHANGES or NO_GO bridge reviews with blocking findings checkpoint bridge_fix_pending and invoke the implementer, and cannot continue to final pytest, supervisor, or commit handoff without a subsequent clean bridge review.
3. Add a pre-finalization control-packet line-reference lint using the existing checker logic for reports/control_plane packets after bridge convergence and before final pytest/supervisor.
4. Add focused regressions proving a saved bridge_converged state containing a blocking finding in all_non_blocking does not resume to commit_ready.
5. Add focused regressions proving post-bridge governing-packet line-reference drift halts or routes as blocking before final pytest/supervisor.
6. Keep the fix in pipeline/control-plane tooling only; do not touch runtime, substrate, seed, JS production, or structural-number test semantics.
7. Run the evidence command and collect the L4 indicator artifact.

## Constraints

- Use the launcher and dispatcher path; do not hand-commit this wave.
- Do not modify runtime, substrate, seed, registry, JS production, StructuralNumbers gates, or merged rational-wave artifacts except through test fixtures.
- Do not weaken reviewer finding classification, severity floors, or governance downgrade rules.
- Do not remove the ability to defer genuine non-blocking DOC_ACCURACY or POLICY_BOUND findings.
- Do not add a second line-ref checker; reuse tools/checks/check_control_packet_line_refs.py or its existing callable logic.
- Keep tests focused and deterministic; avoid broad end-to-end pipeline runs inside unit tests.

## Stop conditions

- Stop as DEFECT if Phase B cannot distinguish effective blocking findings from deferred non-blocking findings without changing reviewer schema.
- Stop as POLICY_BOUND if the fix would make current non-blocking DOC_ACCURACY deferral impossible.
- Stop as INTEGRATION if the line-ref lint cannot be applied to post-Phase-A control packets without duplicating checker logic.
- Do not proceed to commit without the configured evidence command passing and the indicator artifact collected.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- A bridge_converged resume state with any effective blocking finding in all_non_blocking cannot reach commit_ready.
- A NO_GO or REQUEST_CHANGES bridge review with blocking findings takes the bridge-fix path or fails closed at max rounds; it never becomes deferred-only convergence.
- A control packet with a post-bridge code file:line reference is rejected before final pytest, supervisor, or commit handoff.
- Existing genuine non-blocking finding deferral remains supported.
- The configured evidence command passes.
- reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `phase-b-blocking-finding-convergence-hardening-2026-06-20`.
- Governing packet: this file, `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `phase-b-blocking-finding-convergence-hardening-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Follow-up automation packet required by the structural-numbers-rationals-2026-06-19 closeout: the operator performed a bounded manual doc-only unblock after a round-4 NO_GO control-packet line-ref finding was not routed through a deterministic bridge-fix path.

FOUNDER_OVERRIDE:phase-b-blocking-finding-convergence-hardening-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `phase-b-blocking-finding-convergence-hardening-2026-06-20`
- Active packet: `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md`
  - `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id phase-b-blocking-finding-convergence-hardening-2026-06-20 --output reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: phase-b-blocking-finding-convergence-hardening-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-blocking-finding-convergence-hardening-2026-06-20`
- Active packet: `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4d4f3a57d10478b00a2af1b2abe277928e95d9034f870f68fa6bd84e2b6bcd6f`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_2026-06-20.md`
  - `reports/control_plane/phase-b-blocking-finding-convergence-hardening-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/phase-b-blocking-finding-convergence-hardening-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
