# Phase B Recovery Classifier Scope Repair

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `phase-b-recovery-classifier-scope-repair-2026-05-29`
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface
Authorization: standing pipeline-bug-fix authorization
Phase-A-Lock: BOOTSTRAP_PHASE_B_EXCEPTION
FOUNDER_OVERRIDE:phase-b-recovery-classifier-scope-repair-2026-05-29

## Scope

This is a bounded control-surface repair for the pipeline path that hard-failed
while recovering the `js-stage0-vm-trusted-run-hotpath-2026-05-29` wave.

Allowed product writes:

- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/l4_gates/test_intermediate_validation_lock_gate.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_recovery_gate.py`
- `reports/control_plane/phase-b-recovery-classifier-scope-repair-2026-05-29.md`

No runtime, substrate, seed, scheduler, registry, production workflow, or Mu
semantic changes are authorized by this packet.

## Direct Evidence

- Dispatcher output for the failed live run ended with
  `Surface recovery: class=l4_contract_violation tier=3 recovered=False`.
- `.agent_bus/recovery/recovery_status.json` recorded
  `state: tier3_exhausted`, `failure_class: l4_contract_violation`,
  and `detail: max 3 Tier 3 iterations exhausted`.
- The recovery event log recorded three identical delegate failures:
  `baselined .scratch symlink escaped its stable realpath:
  .scratch/phase_b_r2_review_bd4aea6b/.scratch/__pycache__/artifact.cpython-313.pyc`.
- Filesystem inspection of that path returned `is_symlink True`,
  `readlink /tmp`, and `resolve /private/tmp`.
- `mu/tools/executors/phase_b_executor.py` already documented that
  `L4_STRUCTURAL` is reserved for executable runtime/substrate deltas, but the
  no-runtime fallback returned `L4_STRUCTURAL`, enabling a docs/indicator-only
  pre-supervisor package to claim structural class.
- `mu/tools/executors/recovery_gate.py` allowed the out-of-wave tracker-note
  classifier to run for generic `commit_executor` results, including
  `run_pre_push_script` results that should route as test failures.
- The pre-push gate
  `tests/l4_gates/test_intermediate_validation_lock_gate.py::TestIntermediateValidationBehavior::test_js_rejects_unsupported_underscore_in_intermediate`
  failed with `stdout: NO_ERROR` because it patched `kernel._stepKernelCore`,
  while `mu/host/js/engine/pipeline.js` now obtains its runtime hook through
  `_vmConfigTrust.makeStepKernelCoreRunner`.

## Repair

1. Demote tracker/control-packet/indicator-only Phase B package scope from
   `L4_STRUCTURAL` to `L4_ENABLER`, while preserving the existing guards that a
   generic "smaller prerequisite" sentence alone does not downgrade a structural
   packet and that live reentry package refresh can preserve a structural packet.
2. Keep `run_pre_push_script` pytest failures out of the out-of-wave
   tracker-note recovery classifier unless the failed step is a supervisor step.
3. Treat nested review-sandbox `.scratch/.../.scratch/__pycache__/*.pyc`
   artifacts as scratch cache noise during hybrid recovery scope audit, while
   preserving the root `.scratch/__pycache__` symlink escape rejection.
4. Update the F-37 JS behavioral gate to patch `_vmConfigTrust`'s exported
   runner factory, so the test exercises the same seam used by
   `runAlgorithmWithBridge`.

## Local Evidence

- `python3 -m py_compile mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestClassifyFailure::test_pre_push_pytest_failure_is_not_reclassified_as_tracker_note_recovery mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_nested_review_scratch_pycache_symlink_stays_out_of_manifest_drift --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_demotes_docs_only_structural_scope_to_enabler --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestClassifyFailure::test_phase_b_l4_structural_tracker_note_gap_is_recoverable mu/tests/tools/test_recovery_gate.py::TestClassifyFailure::test_pre_push_pytest_failure_is_not_reclassified_as_tracker_note_recovery mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_preexisting_scratch_pycache_pyc_stays_out_of_manifest_drift mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_pytest_tagged_scratch_pycache_pyc_stays_out_of_manifest_drift mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_preexisting_scratch_symlink_to_scratch_dir_is_baselined mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_scratch_pycache_exemption_rejects_symlinked_cache_dir mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_scratch_pycache_exemption_rejects_symlinked_pyc_file mu/tests/tools/test_recovery_gate.py::TestHybridScopeAudit::test_nested_review_scratch_pycache_symlink_stays_out_of_manifest_drift --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_prefers_same_wave_override_and_final_scope mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_rejects_packet_body_source_authorization mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_uses_structural_class_for_runtime_scope mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_demotes_docs_only_structural_scope_to_enabler mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_pre_supervisor_tracker_note_verification_rejects_stale_top_note --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestPhaseBWaveClassResolution::test_structural_tracker_note_uses_package_l4_gate_from_changed_scope mu/tests/tools/test_phase_b_executor.py::TestFinalPytestGate::test_structural_tracker_note_includes_l4_required_proof_fields mu/tests/tools/test_phase_b_executor.py::TestFinalPytestGate::test_structural_tracker_note_l4_files_command_includes_indicator_artifact --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/l4_gates/test_intermediate_validation_lock_gate.py::TestIntermediateValidationBehavior::test_js_rejects_unsupported_underscore_in_intermediate --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_intermediate_validation_lock_gate.py --tb=short`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-b-recovery-classifier-scope-repair-2026-05-29`
- `git diff --check`

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-recovery-classifier-scope-repair-2026-05-29`
- Active packet: `reports/control_plane/phase-b-recovery-classifier-scope-repair-2026-05-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `855f47035e58df02b03057e6299256df776ef3d9943253a765e8f8cb2ef28e3c`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-recovery-classifier-scope-repair-2026-05-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/phase-b-recovery-classifier-scope-repair-2026-05-29.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-recovery-classifier-scope-repair-2026-05-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/phase-b-recovery-classifier-scope-repair-2026-05-29.md`
  - `reports/l4_wave_indicators/phase-b-recovery-classifier-scope-repair-2026-05-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
