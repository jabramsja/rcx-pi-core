# Founder Ordered Redteam Tests Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: tests
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_tests_audit_2026-05-05_blocking.md`
Queue order: non-`/mu` blocking remediation, before non-blocking remediation and before all `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tests-blocking-remediation-2026-05-06
Queue organization source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet governs the blocking tests follow-up from the founder ordered
redteam audit output.

Implementation status (2026-05-06): B1 is remediated in
`mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`; the JS behavioral
parity gate now fails closed on JS execution failure instead of converting the
failure into `pytest.skip(...)`.

Focused local evidence:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity`
  exits `0` with `1 passed in 0.09s`.
- `NODE_OPTIONS=--invalid-option PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsBehavioralParity::test_js_step_parity -rs`
  exits `1` with `AssertionError` at
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:463`,
  `node: --invalid-option is not allowed in NODE_OPTIONS`, and
  `1 failed in 0.08s`.

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

## Scope

Files and directories in scope for this remediation wave:

- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py` - canonical edit
  surface for `TestJsBehavioralParity::test_js_step_parity` and any focused
  regression for the JS execution fail-closed path.
- `mu/tests/l4_gates/` - directory scope limited to the Stage0 VM trusted-path
  gate test module above.
- `tests/l4_gates/test_stage0_vm_trusted_path_gate.py` - symlink evidence path
  for the same tracked test surface; do not treat it as a separate edit target.
- `TASKS.md` - tracker status and acceptance-evidence update only after
  implementation.
- `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
  - governing control-plane packet for this wave.

Reference-only grounding, not edit scope:

- `reports/deferred/blocking/founder_ordered_redteam_tests_audit_2026-05-05_blocking.md`

## Work Items

- Re-verify current source truth for
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:425` through
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:464` before
  implementation. If the skip behavior is already gone, remove B1 from pending
  implementation work and update tracker/evidence status instead of relisting
  stale work.
- If B1 is still present, make JS execution failure in the Stage0 VM behavioral
  parity gate fail closed instead of converting the failure into
  `pytest.skip(...)`.
- Preserve the audit distinction: this is a test fail-closed defect, not
  evidence of a current JS parity mismatch.
- Add or update focused regression evidence proving a sabotaged JS execution
  path fails the gate.
- Run the focused normal-pass command and the focused sabotaged-environment
  command, then record the resulting implementation/evidence status in the
  matching `TASKS.md` entry.

## Constraints

- Do not widen into `/mu` structural runtime remediation; any `/mu` structural
  blocking or non-blocking remediation remains ordered last and requires a hard
  stop before implementation.
- Do not edit JS runtime, Python runtime, scheduler, seed-registration,
  fixture, or production substrate files for this tests fail-closed wave.
- Do not edit source audit packets, non-blocking packets, docs remediation
  packets, tooling remediation packets, `/mu` structural remediation packets, or
  unrelated test files.
- Do not edit Claude-related files.
- Do not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.

## Stop Conditions

- Stop if current source truth proves the skip behavior no longer exists before
  implementation begins; update the tracker instead of implementing stale work.
- Stop if current source truth proves the B1 fail-closed remediation is already
  implemented; remove it from pending work items and acceptance criteria instead
  of re-listing it as unresolved.
- Stop if the fix requires `/mu` structural runtime remediation instead of a
  test fail-closed change; route that work through the `/mu` structural hard-stop
  lane.
- Stop if remediation would require edits outside the in-scope files and
  directories listed above.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- The targeted Stage0 VM JS behavioral parity proof fails closed when JS
  execution fails; JS execution failure must not be converted into a skipped
  test.
- Normal focused JS parity behavior still passes.
- A focused test or direct command demonstrates that the sabotaged JS execution
  path exits nonzero as a failure, not as a skip.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Grounding / Authorization

- `TASKS.md:421` authorizes the founder-ordered redteam wave queue and requires
  control-plane packets plus tracker entries, with remediation ordered by
  category and severity and `/mu` structural remediation last.
- `TASKS.md:425` records the tests audit as completed with 1 blocking tests
  fail-closed defect and no remediation performed by the audit wave.
- `TASKS.md:427` records the organized remediation packet queue created on
  2026-05-06, with remediation not implemented in the queue-organization wave.
- `TASKS.md:428` authorizes
  `[FOUNDER-ORDERED-REDTEAM-TESTS-BLOCKING-REMEDIATION]` as queued/blocking for
  `[NEXT-CODEX-POST-REDTEAM]`, wave ID
  `founder-ordered-redteam-tests-blocking-remediation-2026-05-06`, class
  `L4_ENABLER`, category `tests`, with this packet path, source audit packet
  path, B1 finding inventory, and a stop before widening into `/mu` structural
  remediation.
- Governing packet:
  `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`.
- Source audit packet:
  `reports/deferred/blocking/founder_ordered_redteam_tests_audit_2026-05-05_blocking.md`.
- Wave-bound L4_ENABLER authorization for commit automation:
  FOUNDER_OVERRIDE:founder-ordered-redteam-tests-blocking-remediation-2026-05-06.
- Queue-organization source authorization preserved for chronology:
  FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-tests-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tests-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
  - `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tests-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-tests-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2190f0f749eee022b58e3e1ead95f11e875f808ff8b295513e1d10132f31b396`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tests-blocking-remediation-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-tests-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
  - `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tests-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
