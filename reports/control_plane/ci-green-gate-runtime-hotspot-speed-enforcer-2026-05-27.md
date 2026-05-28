# Ci-Green-Gate-Runtime-Hotspot-Speed-Enforcer-2026-05-27

Date: 2026-05-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27
Class: L4_ENABLER
Category: CI duration hardening and test-gate classification repair
Lane: control-surface (CI/test enforcement)
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Authorize a bounded CI-duration repair wave grounded in measured GitHub and local profile evidence. The wave may optimize tests and speed-enforcer mechanics without weakening coverage. It must not change production runtime semantics; if evidence requires Mu runtime/projection optimization, stop and route a separate L4_STRUCTURAL wave.

## Scope

Files and directories in scope:

- Governing packet: `reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md`.
- Speed classification gate: `tools/checks/check_test_speed.sh`.
- Focused speed-gate tests under `tests/tools/` or `mu/tests/tools/`, limited to `check_test_speed` behavior.
- Proven unmarked general-suite leak: `tests/structural/test_engine_pipeline_discipline.py`, limited to `TestPipelineBoundaryMuValidation::test_pipeline_accepts_valid_mu`.
- L4 engine evidence test helpers and top-duration L4 gate tests only if Phase B proves a test-only optimization preserves the same production evidence:
  - `tests/l4_gates/engine_evidence_cache.py`
  - `tests/l4_gates/test_engine_transition_gate.py`
  - `tests/l4_gates/test_boot1_structural_iteration_gate.py`
  - `tests/l4_gates/test_engine_exit_reason_gate.py`
  - `tests/l4_gates/test_boot1_default_pipeline_gate.py`
  - `tests/l4_gates/test_observer_schema_lock_gate.py`
  - `tests/l4_gates/test_js_observer_api_guard_gate.py`
  - `tests/l4_gates/test_engine_terminal_event_gate.py`
  - `tests/l4_gates/test_recurrence_v2_gate.py`
- `TASKS.md`, report indexes, and indicator artifacts only if strict L4/docs consistency requires them.

- `reports/deferred/non_blocking/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Preserve the seven-check PR surface as non-negotiable: `test`, `green-gate`, `orbit-dot`, `orbit-provenance`, `engine-run-schema`, `orbit-svg`, and `orbit-index`.
2. Repair the speed-enforcer blind spot where a file containing any `pytest.mark.slow` exempts unmarked tests in that file. The repaired gate must detect unmarked tests that call slow runtime functions from mixed fast/slow files.
3. Optimize `test_pipeline_accepts_valid_mu` without weakening its claim. It currently calls `run_engine_pipeline` four times only to prove valid Mu values pass boundary validation; replace that with a proof that still executes the public boundary checks but does not pay four full engine runs.
4. Review the top L4 duration nodes and optimize only if a test-only change preserves production evidence. Do not lower evidence bounds unless targeted output proves the terminal result, event ordering, and parity claims remain identical.
5. Leave any Mu runtime/projection optimization as a separately routed L4_STRUCTURAL wave with Python/JS parity obligations, host-semantics ratchets, authority-inventory checks, and focused production regression tests.

## Constraints

- Use dispatcher, Phase B, pre-commit supervisor, and commit executor. Do not use `run_review.py`.
- Do not edit runtime files, seeds, Stage0, Python/JS production semantics, workflows, branch protection, ratchet baselines, authority baselines, Claude files, or unrelated executor surfaces in this L4_ENABLER wave.
- Do not skip, xfail, delete, or broadly mark tests slow as a substitute for preserving merge-gate evidence.
- Do not claim CI is fixed from local timing alone. Final acceptance must separate local duration evidence from GitHub Actions evidence.
- Do not claim a Mu runtime root cause without profile output or file:line evidence.

## Stop Conditions

- Stop and route a separate L4_STRUCTURAL wave if the only meaningful fix requires changes under `mu/host/`, `mu/stage0/`, seed JSON, JS runtime modules, or production `rcx_pi` semantics.
- Stop if a proposed speed change removes the only merge-gate proof for a boundary, parity, observer, or fail-closed claim.
- Stop if the speed enforcer cannot mechanically distinguish mixed-file slow marks from whole-file slow marks.
- Stop if validation fails for a reason outside this packet's scoped test/gate surfaces.

## Acceptance Criteria

- Focused tests prove the repaired speed enforcer catches an unmarked slow runtime test in a file that also contains a marked slow test.
- `test_pipeline_accepts_valid_mu` remains covered by a public `run_engine_pipeline` boundary-validation proof and runs materially faster in local focused timing.
- Local duration evidence is recorded for:
  - `tests/structural/test_engine_pipeline_discipline.py::TestPipelineBoundaryMuValidation::test_pipeline_accepts_valid_mu`
  - `python3 -m pytest -n auto --dist worksteal -m "not slow and not fuzzer" --ignore=tests/stress/ --ignore=tests/parity/test_js_parity_automated.py --timeout=300 --durations=50 -q`
  - `python3 -m pytest -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 --durations=50 -q`
- Required validation passes: focused changed tests, `bash tools/checks/check_test_speed.sh`, `git diff --check`, docs consistency if docs/report files change, strict L4 execution contract for this wave, host-semantics ratchet, and host-authority inventory ratchet.
- Commit executor pushes and verifies the PR with the full seven-check surface before merge.

## Grounding / Authorization

- PR #1029 current-head CI after commit `68893629d90df88fcdc5af9cdfe47dd45ce18c15` showed the full seven-check surface and passed before merge at `92a8e63f46e9fcd70d6ca1d40f7a145d8a601c5d`.
- GitHub run evidence from prior completed PR #1029 head `9f38c77f`: CI `Green gate (authoritative, python-only)` ran from `2026-05-27T21:10:00Z` to `2026-05-27T21:26:45Z`; `rcx-green-gate` `Run green gate` ran from `2026-05-27T21:10:13Z` to `2026-05-27T21:27:31Z`.
- GitHub log evidence from that run: general Python tests reported `8506 passed, 22 skipped, 1 warning in 448.82s`; L4 evidence tests reported `145 passed in 463.78s`. The parallel green-gate job reported `8506 passed, 22 skipped, 1 warning in 466.35s`; L4 evidence tests reported `145 passed in 477.94s`.
- Local duration evidence for the L4 merge lane: `tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity` was 29.92s; `test_different_id_cycle_no_freeze` was 15.04s; multiple Boot1/engine parity tests were 11.68s to 13.93s.
- cProfile evidence for `test_simple_terminal_parity`: `run_engine_pipeline`, `_service_boundary_effect`, `step_kernel_mu`, `_run_sub_algorithm`, `run_algorithm_meta_circular`, and `assert_mu/is_mu` dominated cumulative time. The profile reported 548,435,142 calls in 105.698s under cProfile.
- Local general-suite duration evidence: `test_pipeline_accepts_valid_mu` was the slowest node at 35.34s, and cProfile tied it to four `run_engine_pipeline` calls with the same Mu engine hot path.
- Source evidence for the speed-enforcer gap: `tools/checks/check_test_speed.sh:39-40` exempts an entire file when any `pytest.mark.slow` exists; `tests/structural/test_engine_pipeline_discipline.py:955-964` has an unmarked `test_pipeline_accepts_valid_mu` that calls `run_engine_pipeline` four times.

FOUNDER_OVERRIDE:ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27

Authorization: bounded L4_ENABLER repair for CI/test speed classification, test-only optimization, and evidence reporting. Production runtime or Mu projection optimization is not authorized in this packet and must be routed as a separate L4_STRUCTURAL wave if needed.

## Phase B Local Evidence

Implementation summary:

- `check_test_speed.sh` now scans test functions with AST mark handling instead of exempting a whole file on any `pytest.mark.slow` text.
- Focused speed-enforcer regressions are consolidated into `mu/tests/tools/test_check_gate_behavioral_pairs.py::TestSpeedEnforcer` to avoid increasing the repo test-file growth count.
- `TestPipelineBoundaryMuValidation::test_pipeline_accepts_valid_mu` still invokes the public `run_engine_pipeline` boundary for all four valid Mu values, but stubs the internal engine loop so the proof does not pay four full production engine executions.
- Scoped L4 hotspot review did not identify a safe same-output test-only rewrite beyond the existing `engine_evidence_cache` sharing. Top L4 durations remain actual production evidence runs, so runtime/projection speed work remains a separate L4_STRUCTURAL route.

Local validation results:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_check_gate_behavioral_pairs.py::TestSpeedEnforcer mu/tests/structural/test_engine_pipeline_discipline.py::TestPipelineBoundaryMuValidation::test_pipeline_accepts_valid_mu --tb=short --durations=10` -> PASS, `4 passed in 0.14s`.
- Focused target timing: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/structural/test_engine_pipeline_discipline.py::TestPipelineBoundaryMuValidation::test_pipeline_accepts_valid_mu --tb=short --durations=5` -> PASS, `1 passed in 0.02s`.
- `bash tools/checks/check_test_speed.sh` -> PASS, no speed violations found.
- `PYTHONHASHSEED=0 python3 -m pytest -n auto --dist worksteal -m "not slow and not fuzzer" --ignore=tests/stress/ --ignore=tests/parity/test_js_parity_automated.py --timeout=300 --durations=50 -q` -> LOCAL LIMITATION, `2 failed, 8528 passed, 4 skipped, 1 warning in 71.97s`. Failures were dirty-worktree/idempotency checks that require no tracked diff (`test_orbit_artifacts_idempotent.py`, `test_replay_gate_idempotent.py`). The earlier growth-cap failure was fixed by consolidating the speed tests into an existing file and `mu/tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap` now passes.
- General-suite duration evidence from that run: top nodes included `tests/tools/test_run_review.py::test_adversary_timeout_blocks_merge` at `30.46s`, `tests/l4_gates/test_stage0_vm_cutover.py::TestCutoverIntegration::test_engine_pipeline_cutover` at `17.14s`, and `tests/parity/test_hemisphere_routing.py::TestHemisphereInit::test_init_passes_hemispheres_through` at `13.70s`.
- `PYTHONHASHSEED=0 python3 -m pytest -m "slow and not l4_expensive" tests/l4_gates/ --timeout=300 --durations=50 -q` -> PASS, `145 passed, 1813 deselected in 334.21s`.
- L4 slow-suite duration evidence: `test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity` `30.02s`; `test_boot1_structural_iteration_gate.py::TestRegressionLock::test_different_id_cycle_no_freeze` `15.07s`; `test_engine_transition_gate.py::TestObserverEventParity::test_stall_parity` `13.96s`; Python re-entry fixture setup `13.91s`; Boot1 step monotonicity re-entry setup `13.90s`.
- `python3 tools/checks/enforce_l4_execution_contract.py --range HEAD --wave-id ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27 --wave-class L4_ENABLER` -> PASS, `Changed files: 6`, `Runtime files: 0`, `Control-plane files: 1`.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` -> PASS, baseline and current counts unchanged.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` -> PASS, no unaccepted new total-inventory or authority-subset sites detected.
- `./tools/checks/check_docs_consistency.sh` -> PASS, all checks passed; STATUS freshness warning only.
- `git diff --check` -> PASS.

GitHub Actions evidence:

- Not run inside this Phase B implementer. Local timing evidence above must not be treated as CI-green proof; commit executor / PR CI remains responsible for the seven-check surface.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27`
- Active packet: `reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/structural/test_engine_pipeline_discipline.py`
  - `mu/tests/tools/test_check_gate_behavioral_pairs.py`
  - `mu/tools/checks/check_test_speed.sh`
  - `reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md`
  - `reports/deferred/non_blocking/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27`
- Active packet: `reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `90fe0452d9cbd00e2d8ac7ea60bf2791e22a9a9df6b1ef43cba7329dc2445b30`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/structural/test_engine_pipeline_discipline.py mu/tests/tools/test_check_gate_behavioral_pairs.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/structural/test_engine_pipeline_discipline.py`
  - `mu/tests/tools/test_check_gate_behavioral_pairs.py`
  - `mu/tools/checks/check_test_speed.sh`
  - `reports/control_plane/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.md`
  - `reports/deferred/non_blocking/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
