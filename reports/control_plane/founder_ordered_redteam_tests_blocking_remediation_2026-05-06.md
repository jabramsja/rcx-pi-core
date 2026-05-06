# Founder Ordered Redteam Tests Blocking Remediation

Date: 2026-05-06
Status: QUEUED - BLOCKING REMEDIATION PACKET
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: tests
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_tests_audit_2026-05-05_blocking.md`
Queue order: non-`/mu` blocking remediation, before non-blocking remediation and before all `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the blocking tests follow-up from the founder ordered
redteam audit output. It does not implement remediation.

## Source Finding

### B1 - JS Stage0 VM Behavioral Parity Test Skips On JS Execution Failure

Classification: BLOCKING DEFECT

Surfaces: L4 Stage0 VM trusted-path gate, JavaScript behavioral parity, G8
test fail-closed behavior.

Source evidence preserved from
`reports/deferred/blocking/founder_ordered_redteam_tests_audit_2026-05-05_blocking.md`:

- Lines 41-44: `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:425`
  through `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:430`
  declare `TestJsBehavioralParity` and `test_js_step_parity` as the proof that
  JS `_stage0VmStepTrusted` produces the same results as public `stage0VmStep`.
- Lines 45-47: `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:457`
  through `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:461`
  execute the JS parity check through
  `subprocess.run(["node", "-e", js_code], ...)`.
- Lines 48-51: `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:463`
  through `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:464`
  convert any nonzero JS execution result into `pytest.skip(...)` instead of a
  test failure.
- Lines 54-58 preserve normal focused-pass output:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity`
  exits with `1 passed in 0.09s`.
- Lines 63-69 preserve sabotaged-environment output:
  `NODE_OPTIONS=--invalid-option PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity -rs`
  exits zero with `SKIPPED [1] tests/l4_gates/test_stage0_vm_trusted_path_gate.py:464:
  JS execution failed: node: --invalid-option is not allowed in NODE_OPTIONS`
  and `1 skipped in 0.06s`.

## Remediation Scope For Future Wave

- Make JS execution failure in the Stage0 VM behavioral parity gate fail closed
  instead of converting the failure into a skip.
- Preserve the distinction recorded by the audit: this is a test fail-closed
  defect, not evidence of a current JS parity mismatch.
- Add or update focused regression evidence proving a sabotaged JS execution
  path fails the gate.

## Stop Conditions

- Stop if current source truth proves the skip behavior no longer exists before
  implementation begins; update the tracker instead of implementing stale work.
- Stop if the fix requires `/mu` structural runtime remediation instead of a
  test fail-closed change; route that work through the `/mu` structural hard-stop
  lane.
- Stop if remediation would require edits outside the tests proof surface and
  matching tracker/control-plane updates.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- The targeted Stage0 VM JS behavioral parity proof fails closed when JS
  execution fails.
- Normal focused JS parity behavior still passes.
- A focused test or direct command demonstrates the fail-closed regression.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-TESTS-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `tests`, severity `blocking`, source audit packet path, and the
acceptance evidence once implemented.
