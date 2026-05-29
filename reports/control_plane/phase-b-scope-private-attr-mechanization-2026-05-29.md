# Phase B Scope Private Attr Mechanization 2026-05-29

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-b-scope-private-attr-mechanization-2026-05-29
Class: L4_ENABLER
Target Gate: G8
Phase-A-Lock: LOCKED
Purpose: Mechanize the dispatcher/Phase B/commit path failures found while repairing the P7W5 package: exact staged-scope parsing must agree with the Phase B generated scope block, and selected-test integrity gates must scan the selected staged tests instead of unrelated dirty tests.

## Scope

Allowed write scope:

- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/checks/linters/check_private_attr_access.py`
- `mu/tools/checks/linters/check_underscore_imports.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_check_private_attr_access.py`
- `mu/tests/tools/test_check_underscore_imports.py`
- `TASKS.md`
- `reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md`
- `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`

Out of scope:

- Production runtime semantics, JS/Python substrate behavior, seed content, Stage0, scheduler, registry, projection data, branch protection, workflow check names, Claude files, test skips, test xfails, or baseline edits.
- The preserved JS kernel continuation optimization is a separate runtime packet and is not authorized here.

## Direct Evidence

- `.agent_bus/rendered/phase-b-reentry-r4-57c77249.md:31-37` records a Phase B reviewer defect: `_parse_exact_stage_scope_files()` returned `[]` for a live packet because the parser matched `may stage exactly` / `authorized staged files`, while `_render_phase_b_indicator_scope_refresh_block()` emitted `- Current staged files:`.
- `mu/tools/executors/phase_b_executor.py` now parses `may stage exactly`, `authorized staged files`, and legacy `current staged files`, while the renderer emits `Authorized staged files` for new packets.
- `mu/tools/executors/commit_executor.py` now passes selected staged test files into the private-attr/import checker subprocesses, mirroring the Phase B selected-test gate.
- The checker tools now expose `scan_files(root, files)` so selected staged tests can be checked without failing on unrelated dirty tests.

## Acceptance Criteria

- Phase B exact-scope parser accepts both legacy `Current staged files` refresh blocks and new `Authorized staged files` refresh blocks.
- Phase B scope-refresh renderer emits `Authorized staged files` so generated packet language is authority-bearing.
- Phase B private-attr gate scans only wave-owned Python test files.
- Commit executor Step 8c scans only selected staged Python test files for private-attr and underscored-import integrity gates.
- Focused checker, Phase B executor, commit executor, py_compile, docs consistency, diff check, and strict L4 contract validation pass.

## Local Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_check_private_attr_access.py mu/tests/tools/test_check_underscore_imports.py mu/tests/tools/test_phase_b_executor.py::TestPrivateAttrGate mu/tests/tools/test_phase_b_executor.py::TestSdkReviewScopeSelection mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_private_attr_gate_scans_only_selected_staged_tests --tb=short` exited `0`: `61 passed in 13.54s`.
- `python3 -m py_compile mu/tools/checks/linters/check_private_attr_access.py mu/tools/checks/linters/check_underscore_imports.py mu/tools/executors/phase_b_executor.py mu/tools/executors/commit_executor.py` exited `0`.
- `git diff --check` exited `0`.

## Required Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_check_private_attr_access.py mu/tests/tools/test_check_underscore_imports.py mu/tests/tools/test_phase_b_executor.py::TestPrivateAttrGate mu/tests/tools/test_phase_b_executor.py::TestSdkReviewScopeSelection mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_private_attr_gate_scans_only_selected_staged_tests --tb=short`
- `python3 -m py_compile mu/tools/checks/linters/check_private_attr_access.py mu/tools/checks/linters/check_underscore_imports.py mu/tools/executors/phase_b_executor.py mu/tools/executors/commit_executor.py`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-b-scope-private-attr-mechanization-2026-05-29 --wave-class L4_ENABLER`
- `./tools/checks/check_docs_consistency.sh`
- `git diff --check`

FOUNDER_OVERRIDE:phase-b-scope-private-attr-mechanization-2026-05-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `phase-b-scope-private-attr-mechanization-2026-05-29`
- Active packet: `reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_private_attr_access.py`
  - `mu/tests/tools/test_check_underscore_imports.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/checks/linters/check_private_attr_access.py`
  - `mu/tools/checks/linters/check_underscore_imports.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md`
  - `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-b-scope-private-attr-mechanization-2026-05-29`
- Active packet: `reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2d09b9e7df85bc062bdade6a35ef102b48995bae3dfb07c11b0a6a8761397f37`
- Indicator artifact: `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_private_attr_access.py mu/tests/tools/test_check_underscore_imports.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_private_attr_access.py`
  - `mu/tests/tools/test_check_underscore_imports.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/checks/linters/check_private_attr_access.py`
  - `mu/tools/checks/linters/check_underscore_imports.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/phase-b-scope-private-attr-mechanization-2026-05-29.md`
  - `reports/l4_wave_indicators/phase-b-scope-private-attr-mechanization-2026-05-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
