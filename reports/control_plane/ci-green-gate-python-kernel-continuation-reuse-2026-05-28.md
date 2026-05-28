# CI Green-Gate Python Kernel Continuation Reuse 2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-green-gate-python-kernel-continuation-reuse-2026-05-28
Class: L4_STRUCTURAL
Category: production Mu runtime hot-path optimization with Python/JS parity proof
Lane: /mu structural runtime and CI duration reduction
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Reduce green-gate runtime by removing repeated Python kernel continuation normalization/validation work that current profile evidence ties to production `run_engine_pipeline` cost, while preserving public omitted-fuel compatibility, continuation security binding, host-semantics ratchets, and Python/JS behavior parity.

## Scope

Files and directories in implementation scope:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - Bounded change only: reuse already validated/normalized kernel continuation context inside the public omitted-fuel compatibility driver instead of re-entering the whole `step_kernel_mu()` boundary for each returned continuation.
  - Keep `step_kernel_mu()` as the marked public transition surface. Do not remove or demote its `@host_iteration` marker.
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - Add focused behavioral/negative-control coverage proving continuation resume security, public omitted-fuel compatibility, and reduced repeated normalization/validation calls.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - Update source-shape locks only if the implementation preserves the anti-laundering contract while changing the public compatibility loop internals.
- `mu/tests/parity/test_exhaustion_parity.py` and focused JS parity smoke only if required by the runtime change.
- `reports/control_plane/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.md`
- `TASKS.md` and `reports/l4_wave_indicators/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.json` only for same-wave tracker/indicator binding.

Out of scope:

- JavaScript runtime edits unless Phase B proves a required parity mirror. Current JS source already normalizes once and drives continuation packets through `_stepKernelCore`.
- Seed content, Stage0 VM semantics, scheduler/registry/loader/checksum/binary/TLV paths, ratchet baseline edits, branch protection, GitHub workflow check-surface changes, Claude files, and test skip/xfail/deletion/marker weakening.
- Broad N3 closure. This wave may reduce CI/runtime cost and improve Python/JS implementation parity, but the active N3 broad host-surface advisory remains open unless a separate bounded packet proves closure.

## Direct Evidence

- Preflight on current `dev` passed with host-semantics ratchet unchanged: JavaScript `host_builtin=2`, `host_iteration=1`, `host_mutation=0`, `host_recursion=0`; Python `host_builtin=1`, `host_iteration=1`, `host_mutation=0`, `host_recursion=0`; `passed=true`.
- Preflight host-authority inventory passed with current `309 total (181 Python + 128 JS)` and `212 authority (119 Python + 93 JS)`, with no unaccepted new total-inventory or authority-subset sites.
- Direct timing on current `dev`:
  `PYTHONHASHSEED=0 /usr/bin/time -p python3 - <<'PY' ... run_engine_pipeline([], {"test": True}, max_steps=10, max_engine_iterations=20, max_algorithm_iterations=50, observer=[]) ... PY`
  printed `real 6.88`.
- cProfile of that same `run_engine_pipeline([], {"test": True}, ...)` call reported `127,808,188 function calls` in `24.554 seconds` under cProfile. The cumulative stack was `engine_pipeline.py:1178(run_engine_pipeline)` -> `engine_pipeline.py:1003(_run_engine_recursive)` -> `engine_pipeline.py:781(_service_boundary_effect)` -> `engine_pipeline.py:744(_boundary_op_run_algorithm)` -> `step_mu.py:2940(_run_sub_algorithm)` -> `step_mu.py:2467(run_algorithm_meta_circular)`.
- In that profile, `mu_type.py:275(assert_mu)` / `mu_type.py:91(is_mu)` consumed `12.159s` cumulative; `step_mu.py:649(normalize_projection)` consumed `4.149s`; `match_mu.py:232(normalize_for_match)` consumed `4.224s`.
- A direct monkeypatch counter on current `dev` showed `run_engine_pipeline([], {"test": True}, ...)` calls `normalize_projection` `25,818` times and `normalize_for_match` `54,204` times.
- A direct monkeypatch counter on current `dev` showed one successful Python `step_kernel_mu([{"pattern":{"x":1},"body":{"x":2}}], {"x":1}, return_meta=True, max_steps=100)` calls `normalize_projection` `22` times and `normalize_for_match` `66` times.
- Python source evidence: `step_mu.py:1419-1425` normalizes domain projections/input before fresh and resumed continuation handling; `step_mu.py:2448-2458` drives public omitted-fuel compatibility by repeatedly calling `step_kernel_mu(... continuation_state=packet["continuation"], return_packet=True)`.
- JavaScript parity reference: `kernel.js:2175-2187` normalizes once and builds `kernelInput`; `kernel.js:2210-2222` drives returned continuations by calling `_stepKernelCore(...)` with the same `kernelInput`, not by re-entering the public `stepKernel()` normalization boundary.
- Current CI evidence after #1032 still has a large runtime bucket: final #1032 green-gate reported `[PY 10/17]` `8518 passed ... in 399.39s`, `[PY 10c/17]` `514 passed in 65.58s`, and `[PY 10d/17]` `145 passed in 332.28s`.

## Work Items

1. Route through dispatcher/Phase B/pre-commit supervisor/commit executor only. Do not use `run_review.py`.
2. Implement a Python prepared-continuation path that validates and normalizes the caller projections/input once for the public omitted-fuel compatibility driver, then drives returned continuation packets without re-running the entire public `step_kernel_mu()` boundary on every continuation.
3. Preserve all existing continuation security binding:
   - `continuation_state` must remain bound to the current call's supplied input and projection cursor.
   - Forged terminal metadata, unsupplied projection state, broader matching prefix projections, forged later-phase projection state, malformed projection cursors, and null/bad subst bindings must still fail closed.
4. Preserve the public `step_kernel_mu()` API and `return_packet=True` direct-resume semantics for external/test callers.
5. Preserve the anti-laundering kernel-driver contract:
   - no synthetic compatibility fuel,
   - no host-counted fuel list,
   - no marker deletion or ratchet baseline edit,
   - `max_steps` remains a watchdog, not the semantic loop owner.
6. Prove Python/JS behavior parity remains intact with focused L4 parity/smoke tests, including JS eval smoke if no JS code changes are needed.
7. Record before/after focused timing for:
   - one direct `run_engine_pipeline([], {"test": True}, ...)` call,
   - `mu/tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity`,
   - the changed focused kernel contract tests.

## Constraints

- Do not skip, xfail, delete, rename, or weaken any test to improve timing.
- Do not change public omitted-fuel behavior without explicit focused parity proof and caller compatibility evidence.
- Do not move transition authority into a hidden helper that makes the ratchet marker untruthful. A private prepared helper is allowed only if `step_kernel_mu()` remains the public marked host-transition surface and tests prove the helper does not own separate semantic authority.
- Do not change Stage0 VM behavior, seed content, or algorithm semantics.
- Do not add host authority sites or host-semantics ratchet increases.
- Do not claim CI is fixed from local timing alone. GitHub Actions green-gate evidence remains final merge evidence.

## Stop Conditions

- Stop if the implementation cannot preserve continuation forgery rejection and public direct-resume behavior.
- Stop if the implementation requires a JavaScript semantic change that cannot be mirrored and tested in the same wave.
- Stop if focused timing does not improve in a same-session comparison or if the improvement cannot be tied to the repeated Python normalization/validation path described above.
- Stop if host-semantics ratchet or host-authority inventory increases, or if a baseline edit is needed.
- Stop if the only viable change would weaken merge-time L4 evidence or alter the seven-check PR surface.

## Acceptance Criteria

- Focused source/behavior tests prove public `step_kernel_mu()` compatibility still works and direct `return_packet=True` continuation resumes still reject forged or unbound continuations.
- A focused regression proves public omitted-fuel compatibility no longer calls `normalize_projection` once per continuation step for the same caller projections. The direct one-projection success case should drop from the current `22` `normalize_projection` calls to a bounded small count consistent with one prepared caller context.
- `run_engine_pipeline([], {"test": True}, ...)` focused timing improves against the current `real 6.88` local baseline, and the command output is recorded.
- `test_simple_terminal_parity` remains green and records a local duration comparison against the current `29.89s` focused baseline.
- Python/JS parity smoke passes: `node mu/host/js/eval_step.js` and the focused Python L4/parity selectors required by the implementation.
- Ratchet checks pass with no unapproved increases:
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- Strict L4 contract passes:
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id ci-green-gate-python-kernel-continuation-reuse-2026-05-28 --wave-class L4_STRUCTURAL`
- The final tracker note must state that this is a focused Python runtime hot-path/parity improvement, not N3 broad host-surface closure and not proof that all CI runtime cost is eliminated.

## Grounding / Authorization

- `TASKS.md:648-656` keeps `[NEXT-CODEX-POST-REDTEAM]` open for future bounded structural work and requires dispatcher/pipeline progression with a control-plane packet plus `TASKS.md` tracker entry for every wave.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175` keeps N3 broad host-surface boundary active as a retained architectural boundary and forbids implementing broad host-surface reduction without a separate bounded packet.
- This packet is the separate bounded packet for a focused production runtime hot-path optimization discovered during CI root-cause profiling. It does not claim broad N3 closure.
- Existing landed CI waves are not replayed:
  - #1026 `n3-ci-runtime-mu-algorithm-hotpath-2026-05-27` landed a prior runtime hot-path pass.
  - #1030 `ci-green-gate-runtime-hotspot-speed-enforcer-2026-05-27` landed the speed-enforcer/test leak pass.
  - #1032 `ci-green-gate-l4-runtime-harness-optimization-2026-05-28` landed the L4 evidence-cache harness pass.

FOUNDER_OVERRIDE:ci-green-gate-python-kernel-continuation-reuse-2026-05-28

Authorization: bounded L4_STRUCTURAL runtime optimization and parity repair for the Python kernel continuation hot path, with no ratchet-baseline edit, no test weakening, no CI check-surface change, and no N3 closure claim.

## Phase B Implementation Note

Status: IMPLEMENTED / LOCAL EVIDENCE

Implemented the Python prepared-continuation compatibility path in
`mu/host/python/rcx_pi/selfhost/step_mu.py`. The public `step_kernel_mu()`
transition marker remains in place. `return_packet=True` direct-resume callers
still enter the existing public continuation validation path; the optimization
only applies after a validated non-packet public call has already produced an
internal continuation packet. That internal driver now reuses the prepared
caller projections, normalized input, validator, kernel bundles, and watchdog
state instead of recursively re-entering the public normalization boundary.

Focused tests added or updated:

- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - locks reduced normalization for public omitted-fuel compatibility;
  - locks that direct packet resume still uses the public boundary;
  - retains existing continuation forgery and malformed-state rejection probes.
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - updates the anti-laundering source lock to reject recursive
    `step_kernel_mu()` driving while preserving the marked public transition
    surface, no synthetic compatibility fuel, and watchdog-only `max_steps`.

No JavaScript runtime edit was made. The JS reference already normalizes once
and drives returned continuations through `_stepKernelCore`.

## Local Timing Evidence

Locked-plan baseline vs local Phase B result:

| Probe | Before | After |
| --- | ---: | ---: |
| `run_engine_pipeline([], {"test": True}, max_steps=10, max_engine_iterations=20, max_algorithm_iterations=50, observer=[])` | `real 6.88` | `real 2.07` |
| `mu/tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity` | `29.89s` focused baseline | `real 10.42` / `1 passed in 10.16s` |
| one-projection `step_kernel_mu(... return_meta=True, max_steps=100)` normalization counter | `normalize_projection=22`, `normalize_for_match=66` | `normalize_projection=1`, `normalize_for_match=3` |
| changed kernel contract/source-lock tests | no locked pre-change selector duration in packet | `91 passed in 3.01s`, `real 3.27` |

This is focused local timing evidence only. GitHub Actions green-gate evidence
remains the final merge signal.

## Phase B Local Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_kernel_run_result_contract.py mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestPythonOuterLoopBoundary::test_step_kernel_mu_is_single_step_packet_boundary --tb=short`
  - PASS: `91 passed in 3.01s`, `real 3.27`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_engine_transition_gate.py::TestObserverEventParity::test_simple_terminal_parity --tb=short`
  - PASS: `1 passed in 10.16s`, `real 10.42`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_exhaustion_parity.py --tb=short`
  - PASS: `38 passed in 2.41s`, `real 2.66`
- `node mu/host/js/eval_step.js`
  - PASS: summary reported `All tests passed: true`, `real 1.59`
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - PASS: `passed: true`; JavaScript `host_builtin=2`, `host_iteration=1`, `host_mutation=0`, `host_recursion=0`; Python `host_builtin=1`, `host_iteration=1`, `host_mutation=0`, `host_recursion=0`
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - PASS: current total inventory `309 total (181 Python + 128 JS)`; current authority subset `212 total (119 Python + 93 JS)`; no unaccepted new total-inventory or authority-subset sites
- `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id ci-green-gate-python-kernel-continuation-reuse-2026-05-28 --output reports/l4_wave_indicators/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.json`
  - PASS: indicator artifact written
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id ci-green-gate-python-kernel-continuation-reuse-2026-05-28 --wave-class L4_STRUCTURAL`
  - PASS: `L4 Execution Contract v2: L4_STRUCTURAL compliant`; staged package reported `Changed files: 6`, `Runtime files: 1`

## Proof Limit

This wave is a focused Python runtime hot-path/parity improvement. It is not
N3 broad host-surface closure and not proof that all CI runtime cost is
eliminated.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `ci-green-gate-python-kernel-continuation-reuse-2026-05-28`
- Active packet: `reports/control_plane/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `reports/control_plane/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.md`
  - `reports/l4_wave_indicators/ci-green-gate-python-kernel-continuation-reuse-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
