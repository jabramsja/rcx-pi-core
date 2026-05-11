# JS Bridge VM Ordering Source-Lock Repair

Date: 2026-05-11
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-bridge-vm-ordering-source-lock-repair-2026-05-11
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural evidence repair
FOUNDER_OVERRIDE:js-bridge-vm-ordering-source-lock-repair-2026-05-11
Authorization: standing pipeline-bug-fix authorization for same-wave repair of the bridge REQUEST_CHANGES findings against this Phase A packet.

## Scope

- Governing packet for this repair wave: `reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md`.
- Later implementation scope, after Phase A approval: `mu/tests/parity/test_js_vm_bridge_parity.py` and `tests/l4_gates/test_stage0_vm_trusted_path_gate.py`.
- Grounding scope: `TASKS.md:518` and the routed governing evidence packet `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`.
- The repair is evidence-only: prove JS bridge VM ordering through the public runtime entrypoint and lock out the source-lock bypass pattern.

## Work items

1. Replace the JS bridge VM ordering proof's split private trusted-step access with the public JS runtime entrypoint `stepKernel(..., {returnMeta:true, vmConfig})` under bridge mode.
2. Remove the private Stage0 trusted-step monkeypatch path described by the reviewer as `['_stage0Vm','StepTrusted'].join('')` plus `stage0Vm[trustedStepName]`.
3. Add public-entrypoint trace evidence by instrumenting Stage0 bundle objects passed through `vmConfig`, for example by logging access when the live VM path reads `bundle.programs`.
4. Assert ordering-sensitive group signatures and same-output negative controls so the proof demonstrates ordering behavior instead of only smoke parity.
5. Add a mechanical source-lock guard in `tests/l4_gates/test_stage0_vm_trusted_path_gate.py` so split-name fragments such as `StepTrusted` fail outside the existing trusted allowlist.
6. Validate only the focused JS bridge parity proof and the focused source-lock guard named in this packet.

## Constraints

- Do not edit `mu/host/js` runtime semantics, seed registration, scheduler behavior, Stage0 VM behavior, compiled bundles, or Claude-related files.
- Do not add JS ordering shortcuts or host-only semantics; the proof must exercise existing Mu projections and Stage0 VM bundles.
- Do not reset, amend, or rewrite existing commits; any implementation repair must be a follow-up commit through the commit executor path.
- Do not broaden this packet into unrelated `/mu` structural implementation, docs cleanup, queue repair, or general repo investigation.
- If current code truth later proves a listed work item is already landed, remove it from pending implementation and acceptance criteria instead of re-listing it as unresolved.

## Stop conditions

- Stop if the proof cannot be expressed through the public `stepKernel(..., {returnMeta:true, vmConfig})` entrypoint without private trusted-step access.
- Stop if the source-lock guard would require weakening or broadening the existing trusted allowlist.
- Stop if satisfying the proof requires runtime, seed registry, scheduler, Stage0 VM, compiled bundle, or Claude-surface edits.
- Stop if focused validation fails for a reason outside the two scoped test files; return with reproduced evidence and a narrower follow-up packet rather than expanding scope.
- Stop at Phase A once this plan is bridge-converged; do not execute the underlying implementation as part of this packet rewrite.

## Acceptance criteria

- `mu/tests/parity/test_js_vm_bridge_parity.py` no longer constructs or uses split private trusted-step access to bypass the literal source-lock gate.
- The JS bridge VM ordering proof uses `stepKernel(..., {returnMeta:true, vmConfig})` with bridge mode enabled and public `vmConfig` bundle instrumentation.
- The proof records public-entrypoint trace evidence that the live VM path reads Stage0 bundle data, including `bundle.programs`.
- Ordering-sensitive group signatures and same-output negative controls are asserted in the parity proof.
- `tests/l4_gates/test_stage0_vm_trusted_path_gate.py` fails split-name fragments such as `StepTrusted` outside the existing trusted allowlist.
- Focused validation passes with:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_vm_bridge_parity.py tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsSourceLock::test_js_trusted_step_allowlist`
  or an equivalent narrower source-lock test if that test is renamed.
- No out-of-scope runtime, compiled bundle, scheduler, seed registration, Claude, or unrelated control-plane files are changed.

## Grounding / Authorization

- `TASKS.md:518` binds `[NEXT-CODEX-POST-REDTEAM]` to the routed JS bridge VM ordering evidence packet, Class `L4_ENABLER`, Category `/mu structural evidence`, target gate `G8`, and packet `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`.
- `TASKS.md:518` states that later proof must exercise existing Mu projections and Stage0 VM bundles rather than adding JS ordering shortcuts.
- Governing evidence packet reference: `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md:6` names wave `js-bridge-vm-ordering-evidence-2026-05-09`, and `:12` carries `FOUNDER_OVERRIDE:js-bridge-vm-ordering-evidence-2026-05-09`.
- This repair packet is a same-wave pipeline-bug repair for the bridge REQUEST_CHANGES findings on `js-bridge-vm-ordering-source-lock-repair-2026-05-11`.
- Same-wave repair override: `FOUNDER_OVERRIDE:js-bridge-vm-ordering-source-lock-repair-2026-05-11`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `js-bridge-vm-ordering-source-lock-repair-2026-05-11`
- Active packet: `reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md`
- Indicator artifact: `reports/l4_wave_indicators/js-bridge-vm-ordering-source-lock-repair-2026-05-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
  - `mu/tests/parity/test_js_vm_bridge_parity.py`
  - `reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md`
  - `reports/l4_wave_indicators/js-bridge-vm-ordering-source-lock-repair-2026-05-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `js-bridge-vm-ordering-source-lock-repair-2026-05-11`
- Active packet: `reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `564e37b5b0d4772ff47dc34d3d553bf9ef2c8e2da99ea83fb0a6dea847c13dab`
- Indicator artifact: `reports/l4_wave_indicators/js-bridge-vm-ordering-source-lock-repair-2026-05-11.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py mu/tests/parity/test_js_vm_bridge_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/js-bridge-vm-ordering-source-lock-repair-2026-05-11.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
  - `mu/tests/parity/test_js_vm_bridge_parity.py`
  - `reports/control_plane/js-bridge-vm-ordering-source-lock-repair-2026-05-11_2026-05-11.md`
  - `reports/l4_wave_indicators/js-bridge-vm-ordering-source-lock-repair-2026-05-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
