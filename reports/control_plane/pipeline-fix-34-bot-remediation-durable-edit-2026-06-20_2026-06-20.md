# NEXT-CODEX-POST-REDTEAM - PIPELINE-FIX-34: tier-3 bot_findings_pending recovery requires + applies durable edits (no meta-envelope-only exhaustion)

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-fix-34-bot-remediation-durable-edit-2026-06-20
Phase-A-Lock: LOCKED
Purpose: PIPELINE-FIX-34 recovery hardening. ROOT (handoff + reproduced this session when pager-w2's bot remediation stranded): the tier-3 `bot_findings_pending` recovery loop in recovery_gate.py drives a recovery agent that returns `{action, commands, explanation}`; when the agent returns META-ENVELOPE-ONLY output (a populated `explanation` but action != 'edit' / empty `commands`), NO durable file edits are applied to remediate the bot finding, yet the loop keeps re-invoking until it EXHAUSTS into the generic `tier3_exhausted` budget-burn (recovered=False) leaving INDICATOR-ONLY evidence and the bot finding unfixed. FIX: for the `bot_findings_pending` failure class specifically, REQUIRE the recovery agent to emit structured edit actions (action='edit' with commands=[{file_path, old_text, new_text}]) and APPLY them via the existing `_apply_edit`; when the agent returns meta-envelope-only output with no edit commands, record a DISTINCT, fail-CLOSED terminal outcome ('bot_findings_pending: no durable edits applied') via `_finish_recovery_status(recovered=False, exhausted=True, outcome='no_durable_edits', state='tier3_no_durable_edits')` so the existing `exhausted=True` -> `pipeline_hard_fail` event fires -- instead of silently burning the iteration budget into the generic `tier3_exhausted` with indicator-only evidence. Terminal-but-NOT-fail-closed is unacceptable (per INV_TYPED_FAIL_CLOSED_OUTCOMES): the no-durable-edits state is DISTINCT and actionable but KEEPS hard-fail severity (exhausted=True). Preserve the existing SPLIT skip/escalate severity semantics (the Bot P1 split-severity fix, PR #792): skip stays NON-exhausted (exhausted=False, no pipeline_hard_fail), escalate stays EXHAUSTED (exhausted=True, pipeline_hard_fail fires) -- and the anti-theater policy rejection. Recovery-tooling only: NO runtime, substrate, seed, projection, or JS change; bounded to recovery_gate.py + its tests.

## Scope

Recovery-tooling fix to the tier-3 bot_findings_pending path in recovery_gate.py + its tests. No runtime/substrate change. TASKS.md is tracker-sync authority. Non-conflicting with Stage0 (recovery_gate vs eval_seed/bootstrap_core).

Files and surfaces in scope:

- mu/tools/executors/recovery_gate.py (MODIFY) -- the tier-3 `bot_findings_pending` response handling: require + apply structured edit actions (action='edit' + commands via `_apply_edit`); on meta-envelope-only output (no edit commands) record a DISTINCT fail-closed terminal -- `recovered=False`, `exhausted=True`, a distinct `no_durable_edits` outcome and `tier3_no_durable_edits` state (NOT the generic silent `tier3_exhausted` budget-burn) so the existing `exhausted=True` -> `pipeline_hard_fail` event in `_finish_recovery_status` fires; preserve the SPLIT skip (exhausted=False, no hard_fail) / escalate (exhausted=True, pipeline_hard_fail fires) severity semantics + the anti-theater policy rejection.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- regression tests: edit-applied path remediates; meta-envelope-only bot_findings_pending -> DISTINCT fail-closed terminal (recovered=False, exhausted=True, `no_durable_edits`/`tier3_no_durable_edits`, pipeline_hard_fail event), NOT silent indicator-only `tier3_exhausted`; deliberate skip stays NON-exhausted and escalate stays EXHAUSTED (split severity unchanged).
- reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read the tier-3 recovery loop in recovery_gate.py (the bot_findings_pending entry, the {action, commands, explanation} dispatch, the `edit` action + `_apply_edit`, the exhaustion paths, the SPLIT skip/escalate short-circuit at the `exhausted_flag = not is_skip` line, the direct `escalate` path, and the `_finish_recovery_status` `exhausted=True` -> `pipeline_hard_fail` mechanism) to ground the fix.
2. For bot_findings_pending: require structured edit actions; apply action='edit' + commands via `_apply_edit`; when the agent returns meta-envelope-only output (no edit commands), call `_finish_recovery_status(recovered=False, exhausted=True, outcome='no_durable_edits', state='tier3_no_durable_edits')` so the terminal is DISTINCT from the generic `tier3_exhausted` budget-burn AND fail-CLOSED (the existing `exhausted=True` branch fires `pipeline_hard_fail`), rather than silently burning iterations to `tier3_exhausted` with indicator-only evidence.
3. Preserve the existing SPLIT skip/escalate severity semantics (skip -> exhausted=False, no hard_fail; escalate -> exhausted=True, pipeline_hard_fail fires) and the anti-theater policy rejection; do not change other failure classes.
4. Add regression tests for: (a) the edit-applied path remediates; (b) the meta-envelope-only -> DISTINCT fail-closed terminal path (recovered=False, exhausted=True, `no_durable_edits`/`tier3_no_durable_edits`, pipeline_hard_fail fires) -- explicitly NOT the silent generic `tier3_exhausted`; (c) skip stays NON-exhausted and escalate stays EXHAUSTED (split severity unchanged).
5. Run the evidence command and collect the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Recovery-tooling only: NO runtime (eval_seed), substrate, seed, projection, or JS change; bounded to recovery_gate.py + its tests.
- Scope the change to the bot_findings_pending failure class; do NOT alter other failure classes' recovery semantics.
- Preserve the existing SPLIT skip/escalate severity semantics from the Bot P1 split-severity fix (PR #792): skip stays NON-exhausted (exhausted=False, no pipeline_hard_fail); escalate stays EXHAUSTED (exhausted=True, pipeline_hard_fail fires). Do NOT collapse them into a single non-exhausted bucket. Preserve the anti-theater policy rejection.
- Fail-CLOSED + actionable on no-durable-edits: the terminal MUST set recovered=False, exhausted=True with a DISTINCT `no_durable_edits` outcome / `tier3_no_durable_edits` state so `pipeline_hard_fail` fires (per INV_TYPED_FAIL_CLOSED_OUTCOMES). Terminal-but-NOT-fail-closed (exhausted=False, or reusing the silent generic `tier3_exhausted` budget-burn) is NOT acceptable. Do not weaken into accepting indicator-only evidence as a remediation.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if requiring durable edits would break a legitimate non-edit recovery path (deliberate skip or escalate).
- If the fix would require touching runtime/substrate files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- tier-3 bot_findings_pending applies structured edit actions via `_apply_edit` when the agent emits them.
- meta-envelope-only output (no edit commands) for bot_findings_pending records a DISTINCT, fail-CLOSED terminal: recovered=False, exhausted=True, a distinct `no_durable_edits` outcome and `tier3_no_durable_edits` state (NOT the generic silent `tier3_exhausted` budget-burn), and the `exhausted=True` branch of `_finish_recovery_status` fires the `pipeline_hard_fail` event. Terminal-but-NOT-fail-closed is rejected (INV_TYPED_FAIL_CLOSED_OUTCOMES).
- deliberate skip stays NON-exhausted (exhausted=False, no hard_fail) and escalate stays EXHAUSTED (exhausted=True, pipeline_hard_fail fires) -- split severity unchanged; anti-theater policy rejection preserved; other failure classes unchanged.
- test_recovery_gate.py covers the three paths (edit-applied, meta-envelope-only fail-closed terminal, skip-non-exhausted/escalate-exhausted) and passes.
- net host semantics delta 0; indicator collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20` is canonical for this packet's L4 fields (Class L4_ENABLER, target_gate_id G8, primary_blocker_class INTEGRATION, primary_invariant_id INV_TYPED_FAIL_CLOSED_OUTCOMES). The no-durable-edits terminal is the typed fail-closed outcome that invariant governs.
- Authorization: Founder 2026-06-20: drive the queue. PIPELINE-FIX-34 (queue item) hardens the exact tier-3 bot_findings_pending churn that stranded pager-w2 this session (bot remediation exhausted with no durable edits). Runs parallel to the Stage0 reduction (non-overlapping files: recovery_gate vs eval_seed/bootstrap_core).

FOUNDER_OVERRIDE:pipeline-fix-34-bot-remediation-durable-edit-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20`
- Active packet: `reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-34-bot-remediation-durable-edit-2026-06-20 --output reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-34-bot-remediation-durable-edit-2026-06-20`
- Active packet: `reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `eb919ac081ba13584df69fa44d5e874c06be9e9d044e228eaf87bb68ad4d1b93`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_2026-06-20.md`
  - `reports/deferred/non_blocking/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-34-bot-remediation-durable-edit-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
