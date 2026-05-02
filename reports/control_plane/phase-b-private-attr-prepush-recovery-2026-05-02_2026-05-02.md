# Phase-B-Private-Attr-Prepush-Recovery-2026-05-02

Date: 2026-05-02
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-RECOVERY]
Wave ID: phase-b-private-attr-prepush-recovery-2026-05-02
Class: L4_ENABLER
Target Gate: G8
Phase-A-Lock: LOCKED
Governing packet: `reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md`

## Scope

Files and directories in scope for the implementation wave:

- `reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md` as the Phase A governing packet.
- The commit-executor receipt test surface that produced the reported private-helper violations: `tests/tools/test_commit_executor_receipt.py` at reported lines `631`, `675`, and `723`.
- The current executor/recovery test surfaces corresponding to TASKS grounding for the prior handoff: `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, and `mu/tests/tools/test_l4_execution_contract_enforcement.py`.
- The existing private-attribute checker and pre-push enforcement surfaces used as evidence and validation gates: `tools/checks/linters/check_private_attr_access.py` and `tools/hooks/pre-push-fast`.
- Implementation source scope is explicit and limited to these control-plane modules:
  - `mu/tools/executors/commit_executor.py` for the public commit-packet refresh seam, the pre-local-commit private-attr gate, and clear blocking errors before commit creation.
  - `mu/tools/executors/phase_b_executor.py` for Phase B private-attr gate selection and remediation-loop routing before commit handoff.
  - `mu/tools/executors/executor_dispatch.py` for the Phase B-to-commit chained handoff and re-entry path that must preserve the same private-attr protection.
  - `mu/tools/executors/recovery_gate.py` for `[PIPELINE-RECOVERY]` classification of the matching `pre-push-fast failed: ERROR: Found private attr access in tests/` failure.
  - `mu/tools/agents/meta_bridge_supervisor.py` only for existing supervisor-facing packaging needed by the automated remediation route.
- No other implementation source modules are in scope.

## Work items

1. Fix the private test seam without weakening anti-cheat. Tests must not call `commit_mod._refresh_tasks_tracker_note_after_packet_truth` or any other single-underscore helper directly; prefer a public API or the existing public commit-packet refresh path.
2. Add a mechanical Phase B gate before commit handoff, and on the re-entry path where appropriate, that runs the existing private-attr checker when Python test files are present in the wave-owned diff.
3. Surface private-attr gate failures as clear blocking errors before `commit_executor` creates a local commit; if the existing Phase B implementer remediation loop can consume the failure, route it there instead of requiring a human same-branch repair.
4. Add or adjust recovery classification so `pre-push-fast failed: ERROR: Found private attr access in tests/` is recognized as a narrow test-integrity failure with an automated Phase B or recovery route, not a generic unrecovered `pr_conflicting` terminal.
5. Add focused regression coverage for the public test seam, Phase B anti-cheat gate selection and failure behavior, and private-attr pre-push recovery classification.

## Constraints

- Do not weaken `tools/checks/linters/check_private_attr_access.py`.
- Do not add an allowlist entry for the reported commit-executor receipt test file.
- Do not add `ANTICHEAT_OK` to bypass the private-attr checker.
- Do not bypass, remove, or soften `tools/hooks/pre-push-fast`.
- Do not manually push, skip commit automation, or route around the existing pipeline/builders.
- Do not touch runtime, substrate, seed, or semantic VM behavior.
- Do not expand this wave beyond pipeline/recovery/test-integrity hardening for the reported private-attr pre-push failure class.
- Do not treat TASKS grounding as proof that every listed implementation item remains unlanded; if implementation evidence later proves an item is already landed, remove it from pending work and acceptance criteria rather than restating it as unresolved.

## Stop conditions

- Stop if the fix would require weakening the private-attr checker, allowlisting the violating test, adding `ANTICHEAT_OK`, or bypassing `pre-push-fast`.
- Stop if the change requires runtime/substrate/seed semantic edits rather than pipeline/recovery/test-integrity hardening.
- Stop if the active code path cannot be identified from the bounded executor/recovery surfaces without broad repo investigation.
- Stop if validation proves the private-attr failure still occurs after the public seam and Phase B gate work.
- Stop if the recovery classification would hide a real pre-push failure instead of routing the specific private-attr test-integrity failure to a bounded automated recovery path.

## Acceptance criteria

- The reported tests no longer access `_refresh_tasks_tracker_note_after_packet_truth` or any other private helper directly.
- `tools/checks/linters/check_private_attr_access.py` passes without allowlisting the affected test file and without `ANTICHEAT_OK`.
- Phase B commit handoff blocks before local commit creation when Python test files in the wave-owned diff contain private attribute access.
- The relevant re-entry path runs or preserves the same private-attr protection when returning to commit handoff after remediation.
- A future `pre-push-fast failed: ERROR: Found private attr access in tests/` is classified as a narrow test-integrity recovery case with an automated Phase B or recovery route, not as generic unrecovered `pr_conflicting`.
- Regression tests cover the public seam, gate selection/failure behavior, and recovery classification.
- Required validation for implementation closeout includes the exact private-attr checker, focused pytest for touched executor/recovery tests, L4 staged/range checks, and `pre-push-fast` before push.

## Grounding / Authorization

- `TASKS.md:207` grounds the triggering prior 2026-05-02 `[PIPELINE-RECOVERY]` Phase B handoff for `phase-b-supervisor-tracker-bootstrap-recovery-2026-05-02` as `Class: L4_ENABLER`, `target_gate_id: G8`, with evidence covering the commit executor, executor dispatch, Phase B executor, meta bridge supervisor, and L4 execution contract tests. This packet recovers the post-commit pre-push failure discovered after that handoff.
- `TASKS.md:358-361` records `[PIPELINE-RECOVERY]` as closed merged follow-through for the pipeline failure recovery system, points at `mu/docs/agents/PipelineRecovery.v0.md` as the design surface, and names `mu/tools/executors/recovery_gate.py` as the implementation file. This wave is bounded follow-through for that pipeline recovery surface, not a new runtime or substrate semantics wave.
- Prior governing packet reference from the TASKS-grounded handoff: `reports/control_plane/phase-b-supervisor-tracker-bootstrap-recovery-2026-05-02_2026-05-02.md`.
- Current governing packet: `reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md`.
- Authorization: standing pipeline-bug-fix authorization applies to this control-surface L4_ENABLER commit-gate/pre-push recovery packet under `[PIPELINE-RECOVERY]`; automation may derive the same-wave override from `FOUNDER_OVERRIDE:phase-b-private-attr-prepush-recovery-2026-05-02`.

## Request From Post-Merge Supervisor

Create and lock a bounded Phase A packet for wave `phase-b-private-attr-prepush-recovery-2026-05-02`. Root-cause evidence from the failed automated commit path: `commit_executor` reached Step 11 `run_pre_push_script` after local commit `a74bfd13`, then failed with `pre-push-fast failed` because `tools/checks/linters/check_private_attr_access.py` reported private attribute access under tests: `tests/tools/test_commit_executor_receipt.py:631: ._refresh_tasks_tracker_note_after_packet_truth`, `:675`, and `:723`.

Direct evidence carried into this packet: `tools/hooks/pre-push-fast:88-93` runs `dev.sh` and fails closed on audit failure; `tools/checks/linters/check_private_attr_access.py:42` scans `tests`, `:85-96` reports non-allowlisted `ast.Attribute` access beginning with a single underscore, and `:117-121` exits 1 on violations. The staged/committed tests introduced in the prior wave called `commit_mod._refresh_tasks_tracker_note_after_packet_truth` directly at the reported lines.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-private-attr-prepush-recovery-2026-05-02`
- Active packet: `reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `148572993a41495a1818528b27437fd4b14a771b7a01bd094f7f1bff1ed76210`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-private-attr-prepush-recovery-2026-05-02.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-05-02T10-11-03p00-00_ecc2bb9d.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-05-02T10-11-03p00-00_ecc2bb9d.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-private-attr-prepush-recovery-2026-05-02.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-05-02T10-11-03p00-00_ecc2bb9d.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/phase-b-private-attr-prepush-recovery-2026-05-02_2026-05-02.md`
  - `reports/l4_wave_indicators/phase-b-private-attr-prepush-recovery-2026-05-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
