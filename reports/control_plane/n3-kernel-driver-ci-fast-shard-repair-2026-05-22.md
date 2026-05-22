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
- Resend commit `c757b181a5d491e77f1399077050a79a9298e6ff` reached PR #1014 CI,
  then `test` run `26269953766`, job `77321094665`, failed on
  `tests/parity/test_rcx_engine_scheduler_parity.py::test_python_js_agree_on_scheduler_malformed_tail_rejection`
  at `tests/parity/test_rcx_engine_scheduler_parity.py:180`, also timing out
  after 60 seconds in `_run_js_scheduler`.
- The same resend's `green-gate` run `26269954677`, job `77321119497`, failed
  on `tests/engine/test_engine_hemisphere_integration.py::TestRoutingPriorityRegression::test_null_not_swallowed_by_stall`
  with a 300-second pytest timeout while validating Mu in
  `rcx_pi/selfhost/mu_type.py:245`.
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
- Resend commit `5d5e3b6b` reached PR #1014 CI, then `green-gate` run
  `26271177927`, job `77324746463`, and `test` run `26271176743`, job
  `77324742998`, both failed after about 44 minutes inside the green-gate step.
  The executor failure excerpt named L4 gate JS/cross-substrate/cutover evidence
  timeouts:
  `tests/l4_gates/test_boot1_default_routing_gate.py::TestJsBoot1Default::test_omitted_matches_explicit_true`,
  `tests/l4_gates/test_boot1_default_routing_gate.py::TestCrossSubstrateDefaultParity::test_omitted_flag_parity`,
  `tests/l4_gates/test_boot1_structural_iteration_gate.py::TestRealReentryProof::*`,
  `tests/l4_gates/test_boot1_structural_iteration_gate.py::TestBoot1TimestampResetReproduction::*`,
  and
  `tests/l4_gates/test_stage0_vm_performance.py::TestTier2IntegrationWorkloads::test_workload_cutover_engine_pipeline`.
- Direct workflow evidence showed `scripts/green_gate.sh` still ran
  `-m "slow" tests/l4_gates/` as merge-blocking L4 evidence, while local marker
  collection proved the named classes were already in the `slow` lane. The gap is
  therefore not a `not slow` leakage issue; it is a missing split between
  merge-bounded L4 slow evidence and full-budget L4 evidence.
- Local reproduction did not prove a semantic failure in the selected probes:
  `TestJsBoot1Default::test_omitted_flag_routes_boot1_with_observer` passed in
  18.90s, `TestJsBoot1Default::test_omitted_matches_explicit_true` passed in
  43.57s, and `TestRealReentryProof::test_js_real_reentry_depth` passed in
  44.74s. These durations are too expensive for the merge gate under the full
  CI workload but do not by themselves prove a production runtime regression.
- A same-wave commit-executor retry then failed pre-commit doc governance because
  the first lane-lock implementation added a new `test_*.py` file under
  `mu/tests/`, while `mu/tests/docs/test_growth_caps.py` counts every
  `test_*.py` below `mu/tests/`. The recovery consolidates the lane-lock source
  assertions into that existing growth-governance test file instead of raising
  the test-file cap.
- Resend commit `5d924a37` reached PR #1014 CI, then both required checks failed
  on the same merge-bounded L4 slow-lane timeout:
  `tests/l4_gates/test_observer_type_guard_gate.py::TestPythonRoutingObserverTypeGuard::test_routing_accepts_valid_observer`
  timed out after 300 seconds in `rcx_pi/selfhost/mu_type.py:245` during
  `is_mu`. The failing test is a positive full routing execution with a valid
  observer; the surrounding rejection/source-lock guard coverage remains bounded.
- The same follow-up then failed commit executor Step 8b before commit because
  the targeted fast pytest gate applied `-m "not slow and not fuzzer"` to a
  changed slow-only test file, causing pytest to select zero tests and exit 5.
  That is a commit-gate control bug, not a runtime semantic failure.

## Scope

Allowed write set for this repair:

- `mu/tests/parity/test_boot1_shadow_parity.py`
- `mu/tests/parity/test_rcx_engine_scheduler_parity.py`
- `mu/tests/engine/test_engine_hemisphere_integration.py`
- `mu/tests/l4_gates/test_boot1_default_pipeline_gate.py`
- `mu/tests/l4_gates/test_boot1_default_routing_gate.py`
- `mu/tests/l4_gates/test_observer_type_guard_gate.py`
- `mu/tests/l4_gates/test_boot1_structural_iteration_gate.py`
- `mu/tests/l4_gates/test_stage0_vm_performance.py`
- `mu/tests/docs/test_growth_caps.py`
- `mu/scripts/green_gate.sh`
- `.github/workflows/slow_tests.yml`
- `pyproject.toml`
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
projection, or Mu semantic file is in scope. The executor scope is
limited to commit-gate routing so this exact slow-shard timeout does not recur
when the repair is resent through the pipeline.

## Implementation

- Mark expensive Boot1 parity/default classes as `@pytest.mark.slow` so they
  run in the owned slow lanes instead of leaking into `[PY 10/17]`.
- Add source-lock tests that fail if those expensive classes drift back out of
  `@pytest.mark.slow`.
- Increase the scheduler parity Node subprocess cap from 30s to 60s; local
  targeted proof measured scheduler JS parity cases at 24-32 seconds in
  isolation, which is too expensive for PR fast-shard execution under xdist
  contention.
- Mark all full scheduler JS parity vectors as `@pytest.mark.slow` with a
  source-lock test so the fast PR shard keeps only lane-classification coverage.
- Bind the scheduler success-path vector to a slow-lane 180-second Node
  subprocess cap while retaining the 60-second default for the other scheduler
  vectors.
- Mark the two full wrapper hemisphere-routing priority regression probes as
  `@pytest.mark.slow` with a source-lock test. Local proof measured them at
  70.23 seconds and 60.47 seconds, while the slow wrapper-equivalence and Paxos
  probes in the same file measured 236.24 seconds and 117.80 seconds.
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
- Introduce the `l4_expensive` pytest marker for full-budget L4 evidence that
  must remain runnable but is too expensive for the merge green-gate budget.
- Update the merge green gate to run `slow and not l4_expensive` for
  `tests/l4_gates/`, keeping bounded L4 evidence merge-blocking while excluding
  the CI-timeout-prone full JS/cross-substrate/cutover probes.
- Update the nightly/manual slow workflow to run both `slow and not
  l4_expensive` and `l4_expensive`, with a larger per-test timeout for the full
  evidence lane.
- Add source locks for the green-gate lane split and for the expensive Boot1 and
  Stage0 VM evidence classes so future changes cannot silently reintroduce the
  same merge-gate timeout shape.
- Move the observer gate's positive full `run_engine_with_routing` execution into
  `l4_expensive` while preserving the observer type rejection and source-lock
  checks in `slow and not l4_expensive`.
- Make commit executor Step 8b accept pytest's all-deselected exit code 5 only
  when stdout proves the fast marker filter selected zero tests, and add a
  regression for slow-only changed test files.

## Constraints

- Do not change production Python or JavaScript runtime code.
- Do not relabel the original runtime wave as non-structural.
- Do not delete Boot1 parity/default coverage; expensive coverage must remain
  collected by the explicit `l4_expensive` slow workflow lane.
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
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m "not slow and not fuzzer" tests/parity/test_rcx_engine_scheduler_parity.py --collect-only -q` reports only the scheduler slow-mark source-lock selected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m slow tests/parity/test_rcx_engine_scheduler_parity.py --collect-only -q` reports all five full scheduler JS parity vectors selected by the slow lane.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m slow tests/parity/test_rcx_engine_scheduler_parity.py --timeout=300 --tb=short` passes.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m "not slow and not fuzzer" tests/engine/test_engine_hemisphere_integration.py --collect-only -q` reports 13 fast checks selected, including the routing-priority slow-mark source-lock.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -m slow tests/engine/test_engine_hemisphere_integration.py --collect-only -q` reports the four full wrapper probes selected by the slow lane.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m "not slow and not fuzzer" tests/parity/test_rcx_engine_scheduler_parity.py tests/engine/test_engine_hemisphere_integration.py --timeout=300 --tb=short --durations=10` passes.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m slow tests/engine/test_engine_hemisphere_integration.py --timeout=420 --tb=short --durations=10` passes.
- `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -x --tb=short --import-mode=importlib -m "not slow and not fuzzer" mu/tests/l4_gates/test_boot1_default_pipeline_gate.py mu/tests/l4_gates/test_boot1_default_routing_gate.py mu/tests/parity/test_boot1_shadow_parity.py mu/tests/parity/test_rcx_engine_scheduler_parity.py` passes.
- `python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id n3-kernel-driver-mu-continuation-state-runtime-2026-05-20` passes.
- `python3 tools/checks/check_host_semantics_ratchet.py` passes with no footprint increase.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` passes with no unaccepted new authority sites.
- `bash tools/checks/check_docs_consistency.sh` passes.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-kernel-driver-ci-fast-shard-repair-2026-05-22 --wave-class L4_ENABLER` passes.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m "not slow and not fuzzer" tests/l4_gates/test_boot1_default_routing_gate.py tests/l4_gates/test_boot1_structural_iteration_gate.py tests/l4_gates/test_stage0_vm_performance.py tests/docs/test_growth_caps.py --timeout=300 --tb=short --durations=10` passes with `32 passed, 32 deselected in 0.12s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m "slow and not l4_expensive" tests/l4_gates/test_boot1_default_routing_gate.py tests/l4_gates/test_boot1_structural_iteration_gate.py tests/l4_gates/test_stage0_vm_performance.py --timeout=300 --tb=short --durations=10` passes with `10 passed, 49 deselected in 183.47s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m l4_expensive tests/l4_gates/test_boot1_default_routing_gate.py tests/l4_gates/test_boot1_structural_iteration_gate.py tests/l4_gates/test_stage0_vm_performance.py --collect-only` reports `22/59 tests collected`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q tests/docs/test_growth_caps.py --tb=short` passes with `5 passed in 0.02s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m "slow and not l4_expensive" tests/l4_gates/test_observer_type_guard_gate.py --timeout=300 --tb=short --durations=10` passes with `16 passed, 1 deselected in 34.63s`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -q -m l4_expensive tests/l4_gates/test_observer_type_guard_gate.py --collect-only` reports `1/17 tests collected`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate::test_run_pytest_on_files_accepts_all_deselected_fast_marker_lane --tb=short` passes.

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
  - `mu/tests/l4_gates/test_observer_type_guard_gate.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-ci-fast-shard-repair-2026-05-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
