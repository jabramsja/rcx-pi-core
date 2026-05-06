# Founder Ordered Redteam Tests Audit - Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_tests_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tests-audit-2026-05-05

This packet records blocking tests-audit findings only. The audit wave did not
implement remediation.

## Scope Executed

- `tests` is a tracked symlink to `mu/tests`; `git ls-files tests mu/tests`
  discovered 363 entries at audit execution time: 362 physical `mu/tests`
  entries plus the `tests` symlink.
- Active repo-local test files outside `tests/` and `mu/tests/` discovered by
  inventory were `conftest.py` and the seven non-archive tests under
  `mu/host/python/rcx_pi/specs/` and `mu/host/python/rcx_pi/worlds/`.
- Fixture surfaces under `mu/tests/fixtures/` were inventoried. The landed
  `rcx_engine_state_minimal.json` and
  `rcx_enginenew_scheduler_operator_pool.json` fixtures are referenced by
  structural/parity tests and were not relisted as unresolved work.
- Archived tests under `archive/` were treated as historical evidence only.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## B1 - JS Stage0 VM Behavioral Parity Test Skips On JS Execution Failure

Classification: BLOCKING DEFECT

Surfaces: L4 Stage0 VM trusted-path gate, JavaScript behavioral parity, G8
test fail-closed behavior.

Evidence:

- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:425` through
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:430` declare
  `TestJsBehavioralParity` and `test_js_step_parity` as the proof that JS
  `_stage0VmStepTrusted` produces the same results as public `stage0VmStep`.
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:457` through
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:461` execute the JS
  parity check through `subprocess.run(["node", "-e", js_code], ...)`.
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:463` through
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:464` convert any
  nonzero JS execution result into `pytest.skip(...)` instead of a test
  failure.
- Normal current execution passes:

```text
$ PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity
.                                                                        [100%]
1 passed in 0.09s
```

- A sabotaged JS execution environment proves the fail-open behavior: the JS
  subprocess fails, but pytest exits zero because the test is skipped.

```text
$ NODE_OPTIONS=--invalid-option PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity -rs
s                                                                        [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/l4_gates/test_stage0_vm_trusted_path_gate.py:464: JS execution failed: node: --invalid-option is not allowed in NODE_OPTIONS
1 skipped in 0.06s
```

Why this blocks:

- The test can pass the suite without exercising the JS trusted-path parity
  invariant it claims to prove.
- A real JS syntax error, import failure, missing compiled bundle, or runtime
  incompatibility in this gate would be reported as a skip instead of a hard
  G8 failure.
- This is a test fail-closed defect, not a current JS parity failure: the normal
  focused command passes today.

Remediation is not authorized in this audit wave. Follow-up remediation must be
ordered by the founder remediation rule after all four audit waves classify
findings, with tests blockers before tests non-blockers and any `/mu`
structural remediation ordered last with a hard stop before implementation.
