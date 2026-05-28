# CI Green-Gate L4 Runtime Harness Optimization 2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-green-gate-l4-runtime-harness-optimization-2026-05-28
Class: L4_ENABLER
Category: CI test-runtime optimization without evidence weakening
Lane: control-surface
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Reduce merge-time `rcx-green-gate` runtime by removing L4 test harness/cache waste while preserving the same production evidence surface.

## Scope

Files and directories in scope:

- Governing packet: `reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md`
- L4 evidence cache/harness:
  - `tests/l4_gates/engine_evidence_cache.py` / `mu/tests/l4_gates/engine_evidence_cache.py`
- L4 test files that repeatedly invoke cached or uncached engine evidence:
  - `tests/l4_gates/test_js_observer_api_guard_gate.py`
  - `tests/l4_gates/test_engine_terminal_event_gate.py`
  - `tests/l4_gates/test_engine_exit_reason_gate.py`
  - `tests/l4_gates/test_observer_schema_lock_gate.py`
  - `tests/l4_gates/test_observer_type_guard_gate.py`
  - `tests/l4_gates/test_engine_transition_gate.py` only if Phase B can prove a no-weakening runtime reduction for the 29.99s observer parity case.
- Green-gate timing instrumentation only if implemented as no-op-on-semantics shell timing around existing steps:
  - `scripts/green_gate.sh`
- Focused workflow/docs tests only if needed to lock the timing/harness contract.
- `TASKS.md`, report indexes, and L4 indicator artifacts if strict L4/docs consistency requires them.

Out of scope:

- Production runtime semantics, seed content, Stage0 VM behavior, Python/JS parity semantics, ratchet baselines, branch protection settings, and Claude surfaces.
- Any skip, xfail, deletion, marker weakening, or movement of `slow and not l4_expensive` evidence out of merge-time green-gate.
- Any optimization claim that is not backed by command output from the same checkout.

## Direct Grounding

- PR `#1031` `gh run view 26560783177 --job 78243013071 --log | rg '\[PY |passed.* in |PY GREEN|Using parallel'` showed `Run green gate` from `2026-05-28T07:23:06Z` to `2026-05-28T07:38:10Z`.
- In that job log, `[PY 10/17] Python test suite` reported `8518 passed, 22 skipped, 1 warning in 392.91s (0:06:32)`.
- In that job log, `[PY 10c/17] Cross-substrate parity gate` reported `514 passed in 66.09s (0:01:06)`.
- In that job log, `[PY 10d/17] L4 gate evidence tests` reported `145 passed in 421.91s (0:07:01)`.
- `scripts/green_gate.sh:164-171` owns the L4 merge-bounded slow lane: `python3 -m pytest $PARALLEL_FLAG -m "slow and not l4_expensive" tests/l4_gates/ --timeout="$PYTEST_TIMEOUT" -q`.
- Local baseline on this checkout: `PYTHONHASHSEED=0 HYPOTHESIS_PROFILE=ci_fast RCX_CI=1 python3 -m pytest -q -m "slow and not l4_expensive" tests/l4_gates --timeout=300 --durations=50 --tb=short -p no:cacheprovider` reported `145 passed, 1813 deselected in 334.26s (0:05:34)`.
- The local baseline slow list included repeated 6-7s production engine evidence calls plus uncached JS helper calls:
  - `tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity` at `29.99s`.
  - `tests/l4_gates/test_js_observer_api_guard_gate.py::TestPipelineStrictObserverAcceptance::test_accepts_array_observer_strict` at `5.94s`.
  - `tests/l4_gates/test_js_observer_api_guard_gate.py::TestPipelineStrictObserverAcceptance::test_accepts_null_observer_strict` at `5.85s`.
  - `tests/l4_gates/test_js_observer_api_guard_gate.py::TestLegacyObserverBackwardCompat::test_observer_true_still_works` at `5.95s`.
  - `tests/l4_gates/test_js_observer_api_guard_gate.py::TestLegacyObserverBackwardCompat::test_observer_omitted_no_events` at `5.90s`.
  - `tests/l4_gates/test_js_observer_api_guard_gate.py::TestMetaStrictObserverGuard::test_meta_delta_count_with_prepopulated_strict_array` at `11.78s`.
- `tests/l4_gates/test_js_observer_api_guard_gate.py:43-59` defines a local `_js_request()` that calls `subprocess.run(["node", eval_step.js, "--json-api", ...])` directly, bypassing the shared cache in `tests/l4_gates/engine_evidence_cache.py:211-257`.
- `tests/l4_gates/engine_evidence_cache.py:211-257` already provides `cached_js_request()` with process-local and xdist shared-cache behavior for deterministic JS JSON API requests.
- A direct local benchmark showed one deterministic `run_engine_pipeline` JSON API call with empty projections takes about six seconds: `/usr/bin/time -p node mu/host/js/eval_step.js --json-api '{"action":"run_engine_pipeline","projections":[],"input":{"test":true},"maxSteps":10,"maxEngineIterations":20,"maxAlgorithmIterations":50,"observer":true}'` reported `real 6.14`.
- A direct local benchmark showed the equivalent Python production call is the same order: `/usr/bin/time -p python3 - <<'PY' ... run_engine_pipeline([], {"test": True}, ...) ... PY` reported `real 6.88`.
- A direct local benchmark showed JS entrypoint/seed loading is not the cause by itself: `node -e "require('./mu/host/js/cli/main')" -- --json-api '{"action":"mu_hash","value":{"test":true}}'` returned an unknown-action response in `real 0.06`.
- `cProfile` of one Python `run_engine_pipeline([], {"test": True}, ...)` call reported the production cost under `engine_pipeline.py:1178(run_engine_pipeline)`, `engine_pipeline.py:1003(_run_engine_recursive)`, `engine_pipeline.py:781(_service_boundary_effect)`, `step_mu.py:2940(_run_sub_algorithm)`, and `step_mu.py:2467(run_algorithm_meta_circular)`. This supports a test-harness optimization first: avoid repeating identical deterministic production evidence, do not weaken it.

## Work Items

1. Route through dispatcher/Phase B/pre-commit/commit executor. Do not use `run_review.py`.
2. Preserve the L4 merge evidence collection count for `python3 -m pytest --collect-only -q -m "slow and not l4_expensive" tests/l4_gates -p no:cacheprovider`: it must still collect 145 tests unless Phase B documents an equal-or-stronger replacement with no skipped evidence.
3. Replace uncached deterministic successful JS JSON API calls in `test_js_observer_api_guard_gate.py` with the shared evidence cache. Keep negative/error-path observer guard assertions direct or uncached where direct runtime execution is the proof.
4. Canonicalize semantically irrelevant engine inputs across L4 tests so equivalent Python/JS production evidence reuses cache keys. Do not canonicalize inputs where the input value itself is the behavior under test.
5. Convert direct positive Python observer acceptance calls to `cached_python_pipeline()` only where the assertion is successful engine execution/observer emission, not where the test specifically proves post-invalid-call state recovery by executing a fresh call.
6. Optionally reduce the 29.99s observer parity case only if Phase B proves the replacement still exercises both Boot1 and trampoline paths with non-vacuous observer events and parity assertions.
7. If adding timing instrumentation to `scripts/green_gate.sh`, it must wrap existing commands and preserve exit behavior, stdout/stderr, and step ordering.

## Constraints

- Do not remove assertions, skip tests, xfail tests, or change markers to hide slow evidence.
- Do not reduce `maxEngineIterations`, `maxAlgorithmIterations`, or `max_steps` unless direct command output proves the same terminal behavior and the test's stated invariant remains covered.
- Do not add production memoization or semantic shortcuts in this wave. If production Mu runtime optimization is indicated, leave a separate L4_STRUCTURAL packet with profiler evidence.
- Treat `tests/` as a symlink to `mu/tests/`; avoid duplicating edits across both paths.
- All duration claims in closeout must cite command output from this wave. Hypotheses must be labeled as hypotheses.

## Acceptance Criteria

- Focused tests pass for every changed L4 file.
- `python3 -m pytest --collect-only -q -m "slow and not l4_expensive" tests/l4_gates -p no:cacheprovider` still reports `145/1958 tests collected` or an explicitly justified equal-or-stronger count.
- The local L4 lane command with `--durations=50` is rerun after implementation and compared to the `334.26s` baseline from this packet.
- The slow list no longer shows deterministic successful `test_js_observer_api_guard_gate.py` calls paying repeated ~6s uncached subprocess cost.
- Strict L4 execution contract passes as `L4_ENABLER` with zero production runtime/substrate deltas unless a separate packet authorizes those deltas.
- Host-semantics and host-authority ratchets remain unchanged.

FOUNDER_OVERRIDE:ci-green-gate-l4-runtime-harness-optimization-2026-05-28

Authorization: bounded L4_ENABLER repair for CI green-gate test-runtime waste. Production runtime or Mu projection optimization is not authorized in this packet.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-green-gate-l4-runtime-harness-optimization-2026-05-28`
- Active packet: `reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `mu/tests/l4_gates/test_engine_exit_reason_gate.py`
  - `mu/tests/l4_gates/test_engine_terminal_event_gate.py`
  - `mu/tests/l4_gates/test_js_observer_api_guard_gate.py`
  - `mu/tests/l4_gates/test_observer_schema_lock_gate.py`
  - `mu/tests/l4_gates/test_observer_type_guard_gate.py`
  - `reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md`
  - `reports/l4_wave_indicators/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-green-gate-l4-runtime-harness-optimization-2026-05-28`
- Active packet: `reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b9596c6b6b935dc96f52b8237b68b352a30441b36f0e02737e1e9023a60573c3`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_engine_exit_reason_gate.py mu/tests/l4_gates/test_engine_terminal_event_gate.py mu/tests/l4_gates/test_js_observer_api_guard_gate.py mu/tests/l4_gates/test_observer_schema_lock_gate.py mu/tests/l4_gates/test_observer_type_guard_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md. (2) Final pytest gate covered 5 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_engine_exit_reason_gate.py`
  - `mu/tests/l4_gates/test_engine_terminal_event_gate.py`
  - `mu/tests/l4_gates/test_js_observer_api_guard_gate.py`
  - `mu/tests/l4_gates/test_observer_schema_lock_gate.py`
  - `mu/tests/l4_gates/test_observer_type_guard_gate.py`
  - `reports/control_plane/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.md`
  - `reports/l4_wave_indicators/ci-green-gate-l4-runtime-harness-optimization-2026-05-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
