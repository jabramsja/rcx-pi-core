# N3 JS Kernel Driver Mu Fuel Production Integration 2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL candidate
Target gate: G8
Workload target: host_debt_reduction
Authorization: FOUNDER_OVERRIDE:n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20

## Purpose

Lock the next bounded production wave for the remaining true JavaScript
host-iteration target: the active `_stepKernelCore` driver loop in
`mu/host/js/engine/kernel.js`.

This packet does not claim a host-semantics count reduction. PR #1005 proved
JavaScript D006 linked-list fuel parity in a test/control harness, but current
production truth still has a host loop at `_stepKernelCore`. The next wave must
turn that proof into production fuel data threading or stop with a proof-class
mismatch.

## Scope

Phase A write set:

- `reports/control_plane/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20_2026-05-20.md`
- `TASKS.md` same-wave tracker authority only

Bounded Phase B candidate write set:

- `mu/host/js/engine/kernel.js`
- `mu/host/js/api/json_handlers.js`
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`
- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `mu/tests/parity/test_exhaustion_parity.py`
- `TASKS.md` same-wave tracker/closeout note
- `reports/l4_wave_indicators/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20.json`
- same-wave generated bridge non-blocker packet only if the bridge emits one

Focused reference surfaces:

- `mu/host/js/engine/kernel.js:67-134`
- `mu/host/js/api/json_handlers.js:354-366`
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1178`
- `mu/tests/parity/test_exhaustion_parity.py:374-457`
- `mu/tests/parity/test_exhaustion_parity.py:529-538`
- `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`

## Work Items

1. Reproduce current source truth before editing: `_stepKernelCore` owns the
   single JS `@host_iteration` marker and currently drives execution with
   `for (let i = 0; i < maxSteps; i++)`.
2. Reproduce prerequisite proof limits: the D006 JS proof uses Mu linked-list
   fuel and one-node-per-step consumption, but its own source proof records a
   host `while` loop in the proof harness. That evidence is not sufficient to
   delete the production marker.
3. Add or select a production path that can thread caller-supplied Mu linked-list
   fuel through the JS kernel driver without changing default numeric
   `maxSteps` behavior.
4. Keep the current `maxSteps` path as the rollback/default path unless the
   same wave proves an equivalent Mu-fuel path for existing JSON API callers.
5. If a `kernelFuel` or equivalent option is added, validate it fail-closed as
   Mu head/tail data and consume exactly one fuel node per kernel step.
6. Preserve existing `KernelRunResult` fields for current callers and add any
   fuel-specific metadata or termination reason only with explicit Python/JS
   parity tests.
7. Add negative controls proving that single-step, fixed-unroll, recursion, and
   higher-order host composition do not satisfy production fuel semantics.
8. Keep `_stepKernelCore` marked as `@host_iteration` unless the production
   loop is genuinely no longer host iteration under the ratchet definitions.
9. Run focused JS/Python parity, marker-truth, host-semantics ratchet,
   host-authority inventory ratchet, and docs consistency checks before
   commit.

## Constraints

- Do not delete or demote the JS `@host_iteration` marker in this wave unless
  direct production-loop evidence and ratchet output prove a real accepted
  decrease.
- Do not replace `for (i < maxSteps)` with another host loop and call that a
  reduction.
- Do not edit host-semantics baselines as a substitute for production evidence.
- Do not add host timers, host exception tables, answer tables, host-only
  accepted sets, or substrate-specific shortcuts.
- Do not widen Python runtime behavior unless required for explicit parity, and
  if Python is touched then mirror the JS/Python contract with focused tests.
- Do not change seed registries, Stage0 VM cutover policy, scheduler behavior,
  projection-loader policy, binary/TLV surfaces, checksum/integrity surfaces,
  Claude files, or local Codex files.
- Do not use comment-only green status or source-lock-only tests to claim live
  production fuel behavior.

## Stop Conditions

- Stop with NO-GO if current source no longer shows `_stepKernelCore` as the
  single tracked JS host-iteration site.
- Stop with NO-GO if the proposed production edit cannot consume Mu linked-list
  fuel without adding unaccepted host-authority inventory sites.
- Stop with NO-GO if the implementation would only swap one host loop shape for
  another while deleting or demoting the marker.
- Stop with NO-GO if fuel exhaustion changes existing default `maxSteps`
  behavior for callers that do not opt into fuel data.
- Stop with NO-GO if `KernelRunResult` parity cannot be locked for both default
  numeric `maxSteps` and the fuel-backed path.
- Stop with NO-GO if focused tests cannot distinguish live production fuel
  threading from the PR #1005 test harness proof.

## Acceptance Criteria

- The Phase A packet contains scope, work items, constraints, stop conditions,
  acceptance criteria, and grounding/authorization, and bridge review returns
  GO before Phase B implementation begins.
- `TASKS.md` contains detector-visible same-wave authorization for
  `n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20`.
- Production JS exposes or internally accepts Mu linked-list fuel as data for
  the kernel driver path, with exactly one fuel node consumed per attempted
  kernel step when fuel is supplied.
- Existing `step_kernel_meta` / `stepKernel` behavior without supplied fuel is
  unchanged for projection success, kernel stall, hash stall, and
  `max_steps_exhausted`.
- Focused tests prove default behavior parity and fuel-backed behavior using
  live JS production entry points, not only the D006 proof harness.
- Marker-truth tests still identify `_stepKernelCore` as the active JS tracked
  iteration site unless the same wave produces direct ratchet-decrease evidence.
- Host-semantics ratchet passes with no increase. A decrease is permitted only
  if direct production evidence proves the marker is no longer truthful.
- Host-authority inventory ratchet reports no unaccepted new total-inventory or
  authority-subset sites.
- The final report explicitly classifies the wave as structural narrowing if
  the marker remains, or as count reduction only if direct production evidence
  and ratchet output support that claim.

## Required Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_kernel_run_result_contract.py --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_exhaustion_parity.py -k d006 --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py --tb=short`
- `node mu/host/js/eval_step.js`
- `bash mu/tools/checks/check_js_debt.sh`
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- `./tools/checks/check_docs_consistency.sh`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20`

## Last 10 PR Accountability

- Count-reduction waves: #996 removed Stage0 recursion marker debt, #997
  removed the stale Python VM-cutover iteration marker, and #1000 demoted the
  list-to-linked converter iteration markers. Those were real marker-count
  reductions.
- Enabler/truth/pipeline/proof waves: #998, #999, #1001, #1002, #1003, #1004,
  and #1005 did not reduce the current production host-loop count. They repaired
  routing, source-lock, marker truth, debt summaries, prerequisites, or D006
  parity proof.
- This wave must move the sequence back toward production host-semantics
  reduction. It may still honestly end as structural narrowing if the marker
  remains truthful.

## Grounding / Authorization

- `TASKS.md` is the single source of truth for authorized work and now carries
  the same-wave tracker authorization for this wave id.
- `reports/control_plane/n3-js-debt-summary-kernel-marker-truth-sync-2026-05-20.md`
  names the current single JS tracked iteration site in `_stepKernelCore` as
  the next true structural-reduction target.
- `mu/host/js/engine/kernel.js:72-77` carries the active JS
  `@host_iteration` marker and the production `maxSteps` loop.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1178` keeps the Python
  driver loop as an accepted bootstrap primitive and does not by itself justify
  deleting the JS marker.
- `mu/tests/parity/test_exhaustion_parity.py:374-457` contains the D006 JS
  linked-list fuel proof harness, and `mu/tests/parity/test_exhaustion_parity.py:529-538`
  records that proof harness still has host loop structure.
- `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`
  classifies PR #1005 as `L4_ENABLER` and says it is not a production-loop
  reduction.

FOUNDER_OVERRIDE:n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20`
- Active packet: `reports/control_plane/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/api/json_handlers.js`
  - `mu/host/js/engine/kernel.js`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `reports/control_plane/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
