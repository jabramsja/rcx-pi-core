# Founder Ordered Redteam Tests Audit - Non-Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - NON-BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_tests_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tests-audit-2026-05-05

This packet records non-blocking tests-audit findings only. The audit wave did
not implement remediation.

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
- Test-theater checks reported no new shell-level test theater, while
  `check_gate_behavioral_pairs.py --json` reported the existing curated L4 gate
  mix of 1579 methods: 1308 behavioral, 178 source-lock, 8 hybrid, and 85
  theater-risk heuristic entries.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## N1 - Agent Tooling Smoke Test Skips Missing Core Scripts

Classification: NON-BLOCKING DEFECT

Surfaces: agent/tooling smoke tests, test fail-closed behavior.

Evidence:

- `mu/tests/tools/test_agent_tooling_smoke.py:64` declares
  `TestAgentToolingSmoke` as smoke coverage for importable/runnable agent
  tools.
- `mu/tests/tools/test_agent_tooling_smoke.py:67` through
  `mu/tests/tools/test_agent_tooling_smoke.py:76` enumerate eight core scripts
  that should show help without crashing.
- `mu/tests/tools/test_agent_tooling_smoke.py:77` through
  `mu/tests/tools/test_agent_tooling_smoke.py:85` state "Core tools should show
  help without crashing" but call `pytest.skip(...)` when a listed script path
  is absent.
- Current focused execution passes because the listed files exist today:

```text
$ PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_tooling_smoke.py::TestAgentToolingSmoke::test_tool_help_works
........                                                                 [100%]
8 passed in 1.16s
```

- Direct method invocation with a missing script proves the test outcome is a
  skip, not a failure:

```text
$ python3 - <<'PY'
import importlib.util
from pathlib import Path
from _pytest.outcomes import Skipped
path = Path('mu/tests/tools/test_agent_tooling_smoke.py')
spec = importlib.util.spec_from_file_location('tooling_smoke', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    mod.TestAgentToolingSmoke().test_tool_help_works('does/not/exist.py')
except Skipped as exc:
    print(f'skipped: {exc}')
else:
    print('not skipped')
PY
skipped: Script not found: does/not/exist.py
```

Why this is non-blocking:

- The current listed scripts exist and the focused smoke test passes.
- The gap is a future fail-closed weakness: deleting or moving a listed core
  script could reduce coverage via skip instead of producing a hard tooling
  smoke failure.

Remediation is not authorized in this audit wave.

## N2 - Meta-Circular Evidence Gate Retains A Source-Lock Claim For A Non-Production Fallback Path

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: L4 Stage0 / meta-circular evidence tests, source-lock-only
assertions, stale production-path wording.

Evidence:

- `mu/tests/l4_gates/test_meta_circular_evidence_gate.py:351` through
  `mu/tests/l4_gates/test_meta_circular_evidence_gate.py:366` assert by source
  text that `_apply_projection_trusted` must call `_stage0_match` and
  `_stage0_substitute`, and the docstring says this is the "sole production
  path".
- Current production cutover truth is different for `step_kernel_mu`:
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1031` sets
  `_STAGE0_VM_CUTOVER = True`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1068` imports
  `_stage0_vm_step_trusted`, and `mu/host/python/rcx_pi/selfhost/step_mu.py:1075`
  through `mu/host/python/rcx_pi/selfhost/step_mu.py:1127` execute kernel,
  bridge, match, and subst bundles through `_stage0_vm_step_trusted`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1303` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1308` route the live cutover path
  through `_step_kernel_with_vm`; `_step_trusted` is the fallback branch when
  cutover is false.
- `mu/tests/l4_gates/test_stage0_vm_cutover.py:408` through
  `mu/tests/l4_gates/test_stage0_vm_cutover.py:430` correctly prove by a
  behavioral negative control that `_apply_projection_trusted` is not called on
  the cutover `step_kernel_mu` path.

Why this is non-blocking:

- The repository has a separate behavioral cutover gate that proves the live
  `step_kernel_mu` production path does not call `_apply_projection_trusted`.
- The stale source-lock assertion is therefore not the only protection for the
  invariant, but it can still mislead future audit/remediation work by labeling
  a fallback helper as the current production path.

Remediation is not authorized in this audit wave.
