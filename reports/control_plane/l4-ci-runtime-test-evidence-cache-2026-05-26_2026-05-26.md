# L4 CI Runtime Test Evidence Cache

Date: 2026-05-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: l4-ci-runtime-test-evidence-cache-2026-05-26
Class: L4_ENABLER
Category: CI/test runtime optimization with L4 evidence preservation
Target gate: G8
Phase-A-Lock: LOCKED

Purpose: reduce merge-gate wall time caused by repeated deterministic L4 engine
evidence tests without weakening the tests, skipping evidence, changing
production Mu semantics, changing runtime behavior, or changing CI selectors.

## Diagnostic Evidence

Current live GitHub evidence for PR #1022:

- `gh pr checks 1022 --json name,workflow,state,startedAt,completedAt,link --repo jabramsja/rcx-pi-core` returned seven successful checks: `test`, `green-gate`, `orbit-dot`, `orbit-provenance`, `engine-run-schema`, `orbit-svg`, and `orbit-index`.
- `gh run view 26462569117 --job 77914156583 --log --repo jabramsja/rcx-pi-core | rg -n "PY 10d|L4 gate evidence|143 passed"` showed the CI `test` job's `[PY 10d/17] L4 gate evidence tests (merge-bounded slow lane)` segment completed `143 passed in 1055.12s (0:17:35)`.
- `gh run view 26462571846 --job 77914117413 --log --repo jabramsja/rcx-pi-core | rg -n "PY 10d|L4 gate evidence|143 passed"` showed the `green-gate` job's same segment completed `143 passed in 967.38s (0:16:07)`.
- `scripts/green_gate.sh:164-170` defines that segment as `python3 -m pytest $PARALLEL_FLAG -m "slow and not l4_expensive" tests/l4_gates/`, so the measured slow portion is the merge-bounded L4 gate evidence lane.

Current code evidence for the Mu path involved:

- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:744-758` routes the `run_algorithm` boundary operation to `_run_sub_algorithm(...)`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:2755-2775` implements `_run_sub_algorithm(...)` as a bounded loop that repeatedly calls `run_algorithm_meta_circular(...)`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:2289-2333` implements `run_algorithm_meta_circular(...)` in structural mode by calling `step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")`.
- A focused runtime wrapper around `run_algorithm_meta_circular(...)` measured:
  - `CASE empty: total=11.9851s run_algorithm_meta_circular_calls=13 run_algorithm_meta_circular_seconds=11.9812s`
  - `CASE cycle: total=83.6903s run_algorithm_meta_circular_calls=48 run_algorithm_meta_circular_seconds=83.3027s`

Conclusion from the evidence above: the CI wall-time regression is in the L4
gate evidence segment, and the expensive deterministic evidence cases spend
nearly all measured local wall time inside the structural Mu algorithm runtime
path. This packet does not claim the production Mu algorithm runtime is fast
enough. It authorizes a test-evidence cache/refactor first because the observed
test files rerun identical deterministic evidence cases many times, and because
the requested repair can preserve assertions without production semantic edits.

## Scope

Implementation files in scope:

- `mu/tests/l4_gates/engine_evidence_cache.py`
- `mu/tests/l4_gates/test_boot1_default_pipeline_gate.py`
- `mu/tests/l4_gates/test_boot1_default_routing_gate.py`
- `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
- `mu/tests/l4_gates/test_boot1_structural_iteration_gate.py`
- `mu/tests/l4_gates/test_engine_exit_reason_gate.py`
- `mu/tests/l4_gates/test_engine_terminal_event_gate.py`
- `mu/tests/l4_gates/test_engine_transition_gate.py`
- `mu/tests/l4_gates/test_observer_schema_lock_gate.py`

Same-wave governance and generated artifacts in scope during Phase B and commit
packaging:

- `TASKS.md`
- `reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md`
- `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
- `reports/deferred/non_blocking/l4-ci-runtime-test-evidence-cache-2026-05-26_bridge_nonblockers.md`, only if Phase B or commit automation generates same-wave non-blocking findings

## Work Items

1. Add a shared deterministic evidence helper for expensive Python
   `run_engine_pipeline(...)` cases and JavaScript JSON API requests.
2. Key cached evidence by full request payload and return isolated deep copies
   so test bodies cannot mutate shared evidence.
3. Support xdist workers with a per-test-run temporary cache using atomic writes
   and a lock file; fall back to process-local caching outside xdist.
4. Replace repeated identical Python and JS evidence runs in the scoped tests
   with cached helper calls while preserving semantic assertions.
5. Preserve direct, uncached negative/error-path execution where the test is
   proving typed failure behavior rather than deterministic success evidence.
6. Replace routing-only tests that do not need real metabolization with mocks
   that still assert metabolization was invoked with the expected local routing
   result.
7. Collapse duplicated mock-injected re-entry runs into module-scoped fixtures
   where multiple assertions inspect the same deterministic observer evidence.
8. Keep real re-entry, Python/JS parity, observer schema, terminal event, exit
   reason, and transition assertions active. Do not skip, xfail, delete, narrow
   selectors, or mark tests out of the merge-bounded lane.
9. Add same-wave tracker, indicator, and validation evidence through the normal
   Phase B and commit executor path.

## Constraints

- Do not edit production runtime, substrate, Stage0, seed, scheduler, registry,
  projection, loader, host-oracle, or Mu semantic files in this wave.
- Do not change `.github/workflows/*`, `scripts/green_gate.sh`, pytest marker
  definitions, branch protection, or CI check selection in this wave.
- Do not weaken assertions, skip tests, add xfails, lower timeouts to hide cost,
  or move evidence out of the merge-bounded L4 lane.
- Do not replace the real cross-substrate parity assertions with source-only
  checks.
- Do not mutate cached evidence objects in place; callers must receive isolated
  copies.
- Do not use manual commit, push, or PR operations. Route this wave through
  `executor_dispatch.py` to Phase B, pre-commit supervisor receipt generation,
  and commit executor.
- If handoff or receipt recovery is required, use dispatcher/builder/API-backed
  recovery paths. Do not hand-author commit handoff or receipt JSON.
- Do not use `run_review.py`.

## Stop Conditions

Stop and return to Phase A or bridge review if any of the following occurs:

- A necessary optimization requires production Mu runtime/projection changes.
- A test can only be made fast by skipping, xfail, deletion, selector removal,
  assertion weakening, or timeout masking.
- Shared caching cannot be keyed by the complete request payload.
- Cached evidence can be mutated by a caller and reused by another test.
- xdist cache coordination flakes, deadlocks, or reuses evidence across
  separate pytest test runs.
- The repair requires touching CI workflow or selector files.
- The dispatcher, Phase B, pre-commit supervisor, or commit executor path breaks
  in a way that cannot be recovered through existing builder/API-backed
  recovery.

## Acceptance Criteria

- Focused L4 gate evidence command passes and shows a material wall-time
  reduction:

```bash
PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast python3 -m pytest -n auto --dist worksteal -m "slow and not l4_expensive" mu/tests/l4_gates/ --timeout=300 --durations=80 --durations-min=0.10 -q
```

- `python3 -m py_compile` passes for the helper and all changed L4 gate test
  files.
- `git diff --check` passes.
- `tools/pre-push-fast` passes.
- `python3 tools/session/check_codex_startup_state.py` passes, proving the
  Codex-local contradiction patch remains clean.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id l4-ci-runtime-test-evidence-cache-2026-05-26 --wave-class L4_ENABLER` passes after Phase B adds the same-wave tracker and indicator package.
- Bridge/pre-commit review returns a commit-capable decision for the current
  staged state and writes a receipt through the meta-bridge API.
- No host semantics ratchet or host authority inventory increases are accepted.
- Final changed-file set remains within `Scope`, plus same-wave generated
  non-blocking findings only if Phase B or commit automation emits them.

## Proof Limits

This wave proves that repeated deterministic L4 evidence tests no longer
recompute the same expensive Mu algorithm evidence within one test run. It does
not prove that a single `run_engine_pipeline(...)` cycling evidence case is
fast. The focused runtime wrapper above measured expensive single-run behavior
inside `run_algorithm_meta_circular(...)`; if post-cache CI remains over budget,
the next wave must profile and optimize the structural Mu algorithm/projection
runtime itself under a separate L4_STRUCTURAL or L4_ENABLER packet, depending on
the touched surface.

## Grounding / Authorization

- Founder/user instruction in this session explicitly requested non-interactive
  automatic waves through dispatcher/Phase B/pre-commit executor and explicitly
  prohibited `run_review.py`.
- Founder/user instruction in this session explicitly requested proof of slow
  CI cause and authorized optimizing tests or Mu projection/runtime depending
  on diagnostic evidence.
- The current live PR check surface and CI logs above prove the slow lane is
  `[PY 10d/17] L4 gate evidence tests`, not the Fixture Gates check surface.
- The focused runtime wrapper above proves the measured local expensive cases
  spend nearly all wall time inside `run_algorithm_meta_circular(...)`, which
  calls `step_kernel_mu(..., validation_mode="algorithm_runtime")`.
- This packet chooses the test-evidence-cache repair because current dirty code
  evidence shows repeated identical deterministic evidence runs across the
  scoped tests, and because that repair preserves runtime semantics.
- FOUNDER_OVERRIDE:l4-ci-runtime-test-evidence-cache-2026-05-26

Human-facing output footer: `Questions? Concerns? Thoughts? -- Think hard`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `l4-ci-runtime-test-evidence-cache-2026-05-26`
- Active packet: `reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md`
- Indicator artifact: `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/engine_evidence_cache.py`
  - `mu/tests/l4_gates/test_boot1_default_pipeline_gate.py`
  - `mu/tests/l4_gates/test_boot1_default_routing_gate.py`
  - `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
  - `mu/tests/l4_gates/test_boot1_structural_iteration_gate.py`
  - `mu/tests/l4_gates/test_engine_exit_reason_gate.py`
  - `mu/tests/l4_gates/test_engine_terminal_event_gate.py`
  - `mu/tests/l4_gates/test_engine_transition_gate.py`
  - `mu/tests/l4_gates/test_observer_schema_lock_gate.py`
  - `reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md`
  - `reports/deferred/non_blocking/l4-ci-runtime-test-evidence-cache-2026-05-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `l4-ci-runtime-test-evidence-cache-2026-05-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/l4-ci-runtime-test-evidence-cache-2026-05-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `l4-ci-runtime-test-evidence-cache-2026-05-26`
- Active packet: `reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0ede29ff5ae10f33a26d08f37b70d96c51ce8fb27e3fbb29dab486559feecd7b`
- Indicator artifact: `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/engine_evidence_cache.py mu/tests/l4_gates/test_boot1_default_pipeline_gate.py mu/tests/l4_gates/test_boot1_default_routing_gate.py mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py mu/tests/l4_gates/test_boot1_structural_iteration_gate.py mu/tests/l4_gates/test_engine_exit_reason_gate.py mu/tests/l4_gates/test_engine_terminal_event_gate.py mu/tests/l4_gates/test_engine_transition_gate.py mu/tests/l4_gates/test_observer_schema_lock_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md. (2) Final pytest gate covered 9 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/engine_evidence_cache.py`
  - `mu/tests/l4_gates/test_boot1_default_pipeline_gate.py`
  - `mu/tests/l4_gates/test_boot1_default_routing_gate.py`
  - `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
  - `mu/tests/l4_gates/test_boot1_structural_iteration_gate.py`
  - `mu/tests/l4_gates/test_engine_exit_reason_gate.py`
  - `mu/tests/l4_gates/test_engine_terminal_event_gate.py`
  - `mu/tests/l4_gates/test_engine_transition_gate.py`
  - `mu/tests/l4_gates/test_observer_schema_lock_gate.py`
  - `reports/control_plane/l4-ci-runtime-test-evidence-cache-2026-05-26_2026-05-26.md`
  - `reports/deferred/non_blocking/l4-ci-runtime-test-evidence-cache-2026-05-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/l4-ci-runtime-test-evidence-cache-2026-05-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
