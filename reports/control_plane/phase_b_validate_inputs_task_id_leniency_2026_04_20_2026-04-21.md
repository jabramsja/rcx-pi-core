# Phase B Validate Inputs Task Id Leniency 2026 04 20

Date: 2026-04-21
Status: IN PROGRESS (Phase B converged; commit restart-branch truth follow-on)
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20
Purpose: Rewrite the subordinate `[PIPELINE-RECOVERY]` Phase A packet so it no longer relies on ungrounded `NOW`/`NEXT` bucket-anchor language. Current repo truth authorizes `[PIPELINE-RECOVERY]` as the only task-id anchor for this wave, while current Phase B handoff already carries wave identity separately via `wave_id`. This packet therefore authorizes only a narrowly evidenced `validate_inputs` exception, not generic task-id aliasing: any allowed divergence must be proved from explicit same-wave metadata available inside `mu/tools/executors/phase_b_executor.py` and the locked packet/routing record path, while `handoff.task_id` remains the routing anchor and `handoff.wave_id` remains the specific-wave carrier.

## Scope

- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/agents/meta_bridge_supervisor.py`
- `mu/tools/hooks/pre-push-fast`
- `mu/tests/docs/test_growth_caps.py`
- `tools/audits/audit_fast.sh`
- `tools/checks/derive_wave_id.sh`
- `mu/tests/tools/test_executor_dispatch.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tests/tools/test_meta_bridge_supervisor.py`
- `mu/tests/tools/test_wave_id_derivation.py`
- `reports/control_plane/phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md` for Phase A packet authority only

No directory-wide scope is authorized. Commit/recovery discussion is in scope only for the explicit restart-branch handoff truth path: `phase_b_executor.py::prepare_commit_handoff()` / `run_phase_b()`, `commit_executor.py::run_commit_pipeline()` Step 2 `ensure_feature_branch`, and `recovery_gate.py::fix_feature_branch_mismatch()`.

## Work Items

- Define the authoritative identity tuple for this wave from current repo truth:
  - `[PIPELINE-RECOVERY]` is the sole authoritative routing and downstream `task_id` anchor for this wave.
  - `wave_id` is the specific-wave identity carrier for downstream handoff; do not treat it as a second `task_id`.
- If Phase B implements a `validate_inputs` exception, bind it to explicit same-wave metadata available inside `phase_b_executor.py` and the locked packet/routing record path; do not infer allowance from `NOW`, `NEXT`, `bucket`, `anchor`, or any other alias vocabulary that is not itself an authoritative field.
- Add or adjust adjacent `mu/tests/tools/test_phase_b_executor.py` coverage only for the new explicitly authorized exception path and, if the implementation touches handoff behavior, for the unchanged contract that `task_id` stays the routing anchor while `wave_id` carries wave specificity.
- Carry explicit restart-branch truth through the commit handoff when this wave is resumed from a restart worktree: if Phase B is already on a safe `jabramsja/...` feature branch that differs from the canonical `jabramsja/{wave_id}` branch, the handoff may carry that exact `target_branch`, and commit/recovery must honor that explicit branch instead of reconstructing only `branch_prefix/wave_id`.
- If this same restart-branch continuation also carries a bounded single-use `FOUNDER_OVERRIDE:<id>` token, the commit-side Gate 8 supervisor wrapper must pass that token through mechanically to the existing external L4 validator path instead of re-imposing a stricter local `FOUNDER_OVERRIDE:<wave_id>` equality rule that current validator truth does not require.
- The same restart-branch continuation must not let nested pre-push / audit surfaces derive a bogus `--wave-id` from the restart branch suffix. The pre-push path and `audit_fast.sh` must share the same exact-match tracker-note guard so restart branches fall back cleanly when the branch suffix is not the authoritative wave id.
- If this wave adds one new wave-owned test module to prove the restart-branch derivation fix, it may also update `mu/tests/docs/test_growth_caps.py` by the minimum single-file founder-signoff increment required to keep doc-governance enforcement aligned with the staged package.

## Constraints

- Do not treat `NOW`/`NEXT`, `bucket`, or `anchor` wording as authority. `TASKS.md:229-240` and `reports/control_plane/hybrid_recovery_agent_2026-04-16.md:6-10` do not define such a rule.
- Do not widen `task_id` acceptance to arbitrary aliases, cross-wave substitutions, or any mismatch that cannot be proved from explicit same-wave metadata in the in-scope Phase B surfaces.
- Do not overload commit handoff's single `task_id` field with both lane and wave identity. Keep the routing anchor in `task_id`; keep wave specificity in `wave_id`.
- Do not widen beyond the `phase_b_executor.py` validation path, its same-file handoff path, and adjacent `phase_b_executor` tests.
- Do not reopen the broader `[PIPELINE-RECOVERY]` hybrid recovery design, `phase_b_implementer.py`, bridge/meta-review flow, or runtime-delegable scope. `recovery_gate.py` is in scope only for restart-branch handoff truth alignment with the commit surface.
- Do not widen founder override authority beyond the existing non-structural allow-list plus external `enforce_l4_execution_contract.py --staged --wave-id <wave_id>` validation path. This packet authorizes only removal of the extra local exact-match choke point in `meta_bridge_supervisor.py`.
- Do not change L4 validator semantics. This packet authorizes only the caller-side wave-id derivation / fallback logic so restart branches stop passing invalid `--wave-id` values into existing checks.
- Do not widen doc-governance edits beyond the single additive test-file cap allowance needed for this wave-owned test module.
- Do not permit arbitrary branch overrides. Any explicit `target_branch` must stay under the existing `branch_prefix` contract and must only preserve the already-active restart/resume feature branch.
- Do not treat this Phase A rewrite as implementation or closeout.

## Stop Conditions

- Stop if the cited in-scope surfaces do not expose enough explicit same-wave metadata to prove a bounded exception. In that case, keep exact `task_id` equality fail-closed rather than inventing a bucket-anchor alias rule.
- Stop if implementing the required proof source or downstream propagation requires changes outside the in-scope executor, recovery, test, and packet files listed above.
- Stop if the only viable path requires replacing `routing_record.task_id` as the canonical downstream `task_id` or adding a broader multi-file handoff schema change.
- Stop if the restart-branch fix requires widening PR/cleanup semantics beyond the explicit handoff `target_branch` field, commit Step 2 branch selection, or Tier 1 feature-branch recovery alignment.
- Stop if continuation override support would require inventing a second authority surface beyond the staged tracker note / package token and the existing external L4 validator.
- Stop if fixing restart-branch pre-push drift requires a new source of wave truth beyond the existing tracker note / exact-match branch guard already present in the shared helper path.
- Stop if current code truth already implements and proves the explicit same-wave exception; narrow or close the packet instead of re-listing landed work.

## Acceptance Criteria

- The packet names `[PIPELINE-RECOVERY]` as the authoritative routing and handoff `task_id` source for this wave, grounded in `TASKS.md:229-240` and `reports/control_plane/hybrid_recovery_agent_2026-04-16.md:6-10`.
- The packet names `wave_id` as the specific-wave downstream carrier and explicitly requires `prepare_commit_handoff` / `run_phase_b` to keep `handoff.task_id` on `routing_record.task_id`.
- The packet authorizes at most one fail-closed `validate_inputs` exception class: an explicit same-wave exception proved from in-scope metadata, not generic `NOW`/`NEXT` or bucket aliasing.
- Pending test work is limited to the new explicitly authorized exception path and any touched handoff behavior; existing unrelated-mismatch rejection is baseline current-code coverage, not a new unresolved work item.
- If a resumed wave is already operating on a safe restart branch, the commit handoff may carry explicit `target_branch` truth and the commit/recovery surfaces must honor that branch instead of failing closed on a reconstructed canonical branch collision.
- If a resumed wave carries an explicit bounded `FOUNDER_OVERRIDE:<id>` token, the commit-side Gate 8 wrapper must accept that same token format when the external L4 validator passes; the wrapper may not fail closed solely because the override ID includes bounded continuation wording beyond bare `wave_id`.
- `audit_fast.sh` and `pre-push-fast` must share an exact-match wave-id derivation rule: a restart branch whose suffix is not present in a tracker note must not pass `--wave-id`, while an exact tracker-note match may still do so.
- If the wave stages `mu/tests/tools/test_wave_id_derivation.py`, doc-governance pre-commit must no longer fail solely because the shared test-file cap is one file behind the founder-authorized repo count.
- No additional implementation file enters scope without an explicit packet update.

## Grounding / Authorization

- `TASKS.md` keeps `[PIPELINE-RECOVERY]` open for queued follow-through after the landed hybrid recovery packet, and explicitly lists `validate_inputs` task-id leniency as one of the remaining control-surface follow-ups under this parent lane.
- `reports/control_plane/hybrid_recovery_agent_2026-04-16.md` names `Task: [PIPELINE-RECOVERY]` and `Wave ID: hybrid-recovery-agent-2026-04-16`; it does not define a second authoritative task-id or any `NOW`/`NEXT` bucket rule for this follow-up.
- `mu/tools/executors/phase_b_executor.py` now reads authoritative Task/Wave header identity from the real packet header in `load_plan_packet()` and enforces the bounded same-wave exception plus duplicate-header fail-closed behavior in `validate_inputs()`.
- `mu/tools/executors/phase_b_executor.py` keeps the downstream routing anchor in `prepare_commit_handoff()` and `run_phase_b()`: `task_id` stays on `routing_record.task_id` while `wave_id` carries the specific wave.
- `mu/tests/tools/test_phase_b_executor.py` already proves both the unrelated-mismatch fail-closed baseline and the tracked same-wave exception path, so this packet does not authorize any broader aliasing rule.
- Live repo evidence from this same wave showed the follow-on branch-truth gap: `.agent_bus/recovery/recovery_status.json` recorded `failure_class: feature_branch_mismatch` at `step: ensure_feature_branch` because the restart worktree was on `jabramsja/phase-b-validate-inputs-task-id-leniency-restart-2026-04-21` while `.agent_bus/executors/phase_b_handoff.json` still implied the canonical `jabramsja/phase-b-validate-inputs-task-id-leniency-2026-04-20` target branch. That observed stop authorizes the narrow commit/recovery branch-truth alignment in this packet.
- Founder authorization for this same in-flight wave also permits a single-use governance bypass token `FOUNDER_OVERRIDE:phase-b-validate-inputs-task-id-leniency-2026-04-20-restart-branch-continuation` to clear the non-structural adjacency / rolling-window gate if this restart-branch continuation hardening otherwise blocks at pre-push. This override is bounded to this wave’s commit continuation only and does not widen structural scope.
- Live supervisor failure on this same wave proved an additional narrow choke point: `.scratch/auto_supervisor_package.json` carried `founder_override_token: FOUNDER_OVERRIDE:phase-b-validate-inputs-task-id-leniency-2026-04-20-restart-branch-continuation`, while `mu/tools/agents/meta_bridge_supervisor.py` Gate 8 still hard-required `founder_override_token == FOUNDER_OVERRIDE:<wave_name>`. The external L4 validator path did not require that equality, so this packet now authorizes removing only that local exact-match mismatch.
- Live pre-push failure on this same wave proved a second duplicate-logic choke point: `tools/audits/audit_fast.sh:152-190` derived `--wave-id phase-b-validate-inputs-task-id-leniency-restart-2026-04-21` directly from the restart branch suffix when `TASKS.md` was in the committed range, while the staged tracker note remained `phase-b-validate-inputs-task-id-leniency-2026-04-20`. `mu/tools/hooks/pre-push-fast:77-84` already contained the needed exact-match tracker-note guard. This packet now authorizes collapsing that drift onto the shared helper path so restart branches fall back instead of failing the existing L4 checker with a bogus wave id.
- The latest standalone `commit_executor` rerun on this same wave cleared supervisor review but then failed in `run_pre_commit_script` because `tests/docs/test_growth_caps.py:49` reported `Test file count (305) exceeds baseline (190) + cap (114) = 304`. Founder then instructed `FIX, RERUN`, authorizing the minimum same-wave growth-cap increment needed to admit the already-staged `mu/tests/tools/test_wave_id_derivation.py` module instead of abandoning the bounded restart-branch fix.
