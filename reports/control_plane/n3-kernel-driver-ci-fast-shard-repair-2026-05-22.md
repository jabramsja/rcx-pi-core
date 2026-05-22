# N3 Kernel Driver CI Fast Shard Repair

Date: 2026-05-22
Status: READY FOR COMMIT EXECUTOR
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-ci-fast-shard-repair-2026-05-22
Class: L4_ENABLER
Lane: control-surface CI/test shard repair and commit-gate recovery
Authorization: authorized control-surface L4_ENABLER same-PR repair for PR #1014.
Target branch: jabramsja/n3-kernel-driver-mu-continuation-state-runtime-2026-05-20
Governing repair packet: reports/control_plane/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.md

## Purpose

Repair the PR #1014 CI failure that blocked the already-committed N3 kernel
driver continuation-state structural runtime wave. This is a test-shard,
evidence-lane, and commit-gate repair only. It does not change production
Python or JavaScript runtime, substrate, seed, scheduler, registry, projection,
or Mu semantics.

The original runtime wave remains `L4_STRUCTURAL`; this packet exists because
the staged repair is intentionally non-runtime and therefore must not be
packaged as the structural runtime wave.

## Root Cause Evidence

- Current PR #1014 `test` run `26268781617`, job `77317636981`, failed on
  commit `e08f0ba2173bfccbdcae6bf29151c383ead3da7f` with one remaining
  timeout: `tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_seed_path_selection`
  timed out after 60 seconds in `_run_js_scheduler`.
- Earlier green-gate run `26251622398`, job `77263960447`, reached the pytest
  summary in `[PY 10/17] Python test suite (excludes stress, slow, fuzzer)` and
  reported `18 failed, 8451 passed, 22 skipped, 1 warning in 2318.03s`.
- The same log records Boot1 default JS subprocess timeouts, Boot1 shadow
  pytest-timeout failures, and scheduler parity Node subprocess timeouts:
  `tests/l4_gates/test_boot1_default_pipeline_gate.py::TestJsPipelineBoot1Default::test_omitted_matches_explicit_true`,
  `tests/l4_gates/test_boot1_default_routing_gate.py::TestJsBoot1Default::*`,
  `tests/parity/test_boot1_shadow_parity.py::TestBoot1*`, and
  `tests/parity/test_rcx_engine_scheduler_parity.py::*`.
- The fast PR shard excludes slow tests at `scripts/green_gate.sh:138-141`,
  while slow L4 gates remain merge-blocking at `scripts/green_gate.sh:164-169`.
  Full slow tests also have their own nightly/manual workflow at
  `.github/workflows/slow_tests.yml:40-43`.
- Local focused proof after the repair selected the new source-lock tests in
  the fast shard and completed the targeted fast shard with
  `45 passed in 84.60s`.
- The slow L4 default proof still runs and completed with
  `20 passed in 177.98s`.
- Re-entering the dispatcher with only the test repair staged failed supervisor
  validation because the package was still bound to the structural runtime wave:
  `L4_STRUCTURAL wave has no runtime/substrate files`.
- Re-entering through the standalone commit executor under this L4_ENABLER
  packet reached supervisor `COMMIT_GO`, then failed Step 8b because the commit
  gate ran all affected test files without the PR fast-shard marker filter:
  `targeted pytest gate failed (exit=-1): pytest timed out after 960s`.
- The next commit executor run created local commit `53b8af47`, then failed
  Step `run_pre_push_script` because `pre-push-fast` evaluates the full
  `origin/dev...HEAD` runtime wave and the detector-visible tracker body did not
  carry the runtime packet's same-wave marker-touch override token.

## Scope

Allowed write set for this repair:

- `mu/tests/parity/test_boot1_shadow_parity.py`
- `mu/tests/parity/test_rcx_engine_scheduler_parity.py`
- `mu/tests/l4_gates/test_boot1_default_pipeline_gate.py`
- `mu/tests/l4_gates/test_boot1_default_routing_gate.py`
- `TASKS.md`, only for this L4_ENABLER tracker sync note
- `mu/tools/executors/commit_executor.py`, only for the Step 8b fast-shard filter
- `mu/tests/tools/test_commit_executor_receipt.py`, only for the Step 8b regression
- `mu/tools/executors/phase_b_executor.py`, only for bare backticked
  same-wave override extraction from structural packets
- `mu/tests/tools/test_phase_b_executor.py`, only for the override-extraction
  regression
- `reports/control_plane/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.md`
- `reports/l4_wave_indicators/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.json`

No production runtime, substrate, host boundary, scheduler seed, registry,
projection, workflow, or Mu semantic file is in scope. The executor scope is
limited to commit-gate routing so this exact slow-shard timeout does not recur
when the repair is resent through the pipeline.

## Implementation

- Mark expensive Boot1 parity/default classes as `@pytest.mark.slow` so they
  run in the owned slow lanes instead of leaking into `[PY 10/17]`.
- Add source-lock tests that fail if those expensive classes drift back out of
  `@pytest.mark.slow`.
- Increase the scheduler parity Node subprocess cap from 30s to 60s; local
  targeted fast proof measured a scheduler case at 31.90s, which exceeds the
  old cap while remaining under the new cap.
- Mark only the scheduler success-path selection vector as `@pytest.mark.slow`
  with a source-lock test so it stays in the owned slow lane; keep the scheduler
  rejection/fail-closed parity vectors in the fast PR shard.
- Bind the slow scheduler success-path vector to a slow-lane 180-second Node
  subprocess cap while retaining the 60-second default for the fast scheduler
  rejection/fail-closed vectors.
- Preserve fast Boot1 security, validation, primitive-count, and source-lock
  coverage in `[PY 10/17]`.
- Make commit executor Step 8b mirror the PR fast-shard marker filter with
  `-m "not slow and not fuzzer"` plus deterministic `ci_fast` environment.
  The slow evidence remains in the owned slow lanes rather than the serial
  commit hook path.
- Make Phase B tracker-note generation extract bare backticked same-wave
  `FOUNDER_OVERRIDE` lines from structural packets so packet-authorized
  marker-touch waves produce detector-visible tracker override tokens before
  commit handoff.

## Constraints

- Do not change production Python or JavaScript runtime code.
- Do not relabel the original runtime wave as non-structural.
- Do not delete Boot1 parity/default coverage; expensive coverage must remain
  collected by the slow lane.
- Do not claim this reduces host semantics. The host-semantics ratchet must
  remain unchanged.
- Do not change public accepted input behavior, KernelRunResult fields, or
  JS/Python metadata parity.

## Acceptance

- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m "not slow and not fuzzer" tests/parity/test_boot1_shadow_parity.py tests/l4_gates/test_boot1_default_pipeline_gate.py tests/l4_gates/test_boot1_default_routing_gate.py --collect-only -q` reports the expensive Boot1 tests deselected and the source-lock tests selected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -n 4 --dist worksteal -m "not slow and not fuzzer" tests/parity/test_boot1_shadow_parity.py tests/parity/test_rcx_engine_scheduler_parity.py tests/l4_gates/test_boot1_default_pipeline_gate.py tests/l4_gates/test_boot1_default_routing_gate.py --timeout=300 --durations=20 --tb=short -q` passes.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -n 4 --dist worksteal -m slow tests/l4_gates/test_boot1_default_pipeline_gate.py tests/l4_gates/test_boot1_default_routing_gate.py --timeout=300 --durations=20 --tb=short -q` passes.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_run_pytest_on_files_uses_fast_shard_marker_filter --tb=short` passes.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestPrepareCommitHandoff::test_build_phase_b_tracker_note_reads_backticked_same_wave_override_line --tb=short` passes.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m "not slow and not fuzzer" tests/parity/test_rcx_engine_scheduler_parity.py --collect-only -q` reports the slow success-path vector deselected and the scheduler source-lock/rejection vectors selected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m slow tests/parity/test_rcx_engine_scheduler_parity.py --collect-only -q` reports the success-path vector selected by the slow lane.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m slow tests/parity/test_rcx_engine_scheduler_parity.py --timeout=300 --tb=short` passes.
- `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -x --tb=short --import-mode=importlib -m "not slow and not fuzzer" mu/tests/l4_gates/test_boot1_default_pipeline_gate.py mu/tests/l4_gates/test_boot1_default_routing_gate.py mu/tests/parity/test_boot1_shadow_parity.py mu/tests/parity/test_rcx_engine_scheduler_parity.py` passes.
- `python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id n3-kernel-driver-mu-continuation-state-runtime-2026-05-20` passes.
- `python3 tools/checks/check_host_semantics_ratchet.py` passes with no footprint increase.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` passes with no unaccepted new authority sites.
- `bash tools/checks/check_docs_consistency.sh` passes.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-kernel-driver-ci-fast-shard-repair-2026-05-22 --wave-class L4_ENABLER` passes.

## Proof Limits

This repair proves CI shard ownership, timeout classification, and commit-gate
resubmission viability for the identified Boot1/scheduler test failures. It
does not prove a new runtime structural reduction, host-semantics reduction, or
additional Mu programming progress beyond the existing PR #1014 runtime diff.

Required override token for this bounded control-surface repair:

FOUNDER_OVERRIDE:n3-kernel-driver-ci-fast-shard-repair-2026-05-22

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-ci-fast-shard-repair-2026-05-22`
- Active packet: `reports/control_plane/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a95fba1702545d800143403434bba7c21c82cf11e290511f04d0c12e9070b693`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.json`
- Evidence command: `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -n 4 --dist worksteal -m "not slow and not fuzzer" tests/parity/test_boot1_shadow_parity.py tests/parity/test_rcx_engine_scheduler_parity.py tests/l4_gates/test_boot1_default_pipeline_gate.py tests/l4_gates/test_boot1_default_routing_gate.py --timeout=300 --durations=20 --tb=short -q && PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -n 4 --dist worksteal -m slow tests/l4_gates/test_boot1_default_pipeline_gate.py tests/l4_gates/test_boot1_default_routing_gate.py --timeout=300 --durations=20 --tb=short -q && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_run_pytest_on_files_uses_fast_shard_marker_filter --tb=short && PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -x --tb=short --import-mode=importlib -m "not slow and not fuzzer" mu/tests/l4_gates/test_boot1_default_pipeline_gate.py mu/tests/l4_gates/test_boot1_default_routing_gate.py mu/tests/parity/test_boot1_shadow_parity.py mu/tests/parity/test_rcx_engine_scheduler_parity.py && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-kernel-driver-ci-fast-shard-repair-2026-05-22 --wave-class L4_ENABLER`.
- Evidence delta: (1) PR #1014 green-gate run 26251622398 job 77263960447 failed `[PY 10/17]` with 18 timeout failures in Boot1 default, Boot1 shadow, and scheduler parity tests. (2) Expensive Boot1 default/parity classes now stay in owned slow lanes with source-lock tests selected by the fast shard; slow L4 default evidence remains merge-blocking. (3) Scheduler parity Node timeout moved from 30s to 60s after local focused proof measured a scheduler case at 31.90s. (4) Commit executor Step 8b now mirrors the PR fast-shard marker filter and deterministic `ci_fast` env after the first resend timed out at 960s by running all affected slow-marked files serially. (5) Host-semantics and host-authority ratchets remain unchanged; this repair does not alter runtime semantics.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_rcx_engine_scheduler_parity.py`
  - `reports/control_plane/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
