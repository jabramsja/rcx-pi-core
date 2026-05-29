# P7W5-Metabolization-Source-Lock-Repair-2026-05-28

Date: 2026-05-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: p7w5-metabolization-source-lock-repair-2026-05-28
Class: L4_ENABLER
Target Gate ID: G8
Phase-A-Lock: LOCKED
Authorization: standing pipeline-bug-fix authorization for p7w5-metabolization-source-lock-repair-2026-05-28, scoped to repair the stale P7W5 source-lock/pre-push failure after the JS metabolization continuation-reuse change.
FOUNDER_OVERRIDE:p7w5-metabolization-source-lock-repair-2026-05-28

Purpose: build a bounded Phase A packet for the P7W5 source-lock contradiction after the JS metabolization continuation-driver optimization. Use founder protocol and the current Codex pipeline only; do not use `run_review.py`.

## Scope

Files/directories in scope for this repair wave if this packet is accepted:

- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
- `TASKS.md`, only for same-wave tracker/authorization sync required by strict staged L4 validation or commit packaging
- `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`
- `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`

The repair target is the stale P7W5 test/source-lock expectation that still treats JS routing continuation drivers as explicit packet-return boundaries. The JS runtime optimization itself is not pending work in this packet: current `mu/host/js/engine/routing.js` code truth has both `runHemisphereRouting` and `runMetabolizationCycle` calling `stepKernel(...)` with `validateDomainBoundary(...)`, `maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG`, `validationMode: 'algorithm_runtime'`, and `returnMeta: true`, with no `returnPacket`, `continuationState`, or packet-continuation loop.

No predecessor packet or prior-wave report is in scope for this repair, including commit-packaging cleanup.

## Work Items

1. Repair `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py` without weakening the gate:
   - keep `runHemisphereRouting` and `runMetabolizationCycle` locked as validated `stepKernel(... returnMeta: true)` public boundaries;
   - require both functions to reject `returnPacket`, `continuationState`, and packet-continuation loop reintroduction.
2. Preserve existing P7W5 assertions for watchdog bounding, validation mode, domain-boundary validation, and no security imports.
3. If commit packaging requires same-wave control-surface sync, bind this repair wave only to `TASKS.md` and `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json` without broadening implementation scope.
4. Route execution through dispatcher/Phase A/Phase B/commit executor surfaces; do not hand-route with `run_review.py`.

## Constraints

- Do not revert or weaken the JS routing/metabolization continuation-driver optimization in `mu/host/js/engine/routing.js`.
- Do not make runtime semantic changes. A need for runtime/substrate edits is a stop condition for this packet.
- Do not edit predecessor packets, prior-wave reports, seeds, Python runtime, ratchet baselines, workflows, branch protection, Claude files, or unrelated docs.
- Do not skip, xfail, delete, or weaken tests.
- Do not broaden beyond the P7W5/source-lock contradiction and same-wave control-surface packaging authorized by `TASKS.md:457`.
- Do not claim the TASKS grounding proves every implementation item is still unlanded; current source-lock/runtime evidence controls when it conflicts with stale packet wording.

## Stop Conditions

Stop and return to Phase A/bridge review if:

- the repair requires changing `mu/host/js/engine/routing.js`, `mu/host/js/engine/kernel.js`, seeds, Python runtime, or any substrate/runtime semantics;
- the only way to pass the P7W5 gate is to reintroduce `returnPacket`, `continuationState`, or manual packet continuation loops into `runHemisphereRouting` or `runMetabolizationCycle`;
- required validations fail for reasons outside the scoped P7W5 source-lock contradiction;
- commit packaging requires write scope outside the four files listed in this packet's Scope section;
- pre-push/CI would need to be bypassed.

## Acceptance Criteria

- `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py` locks the current JS routing boundary shape:
  - `runHemisphereRouting` and `runMetabolizationCycle` remain validated public `stepKernel(... returnMeta: true)` boundaries;
  - both functions explicitly lack `returnPacket`, `continuationState`, and packet-continuation loop handling.
- P7W5 watchdog, `algorithm_runtime` validation mode, domain-boundary validation, and no-security-import assertions remain enforced.
- The packet path in all control-surface references is `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`.
- Same-wave control-surface automation can mechanically derive authorization from this packet's `Authorization: standing pipeline-bug-fix authorization...` line and `FOUNDER_OVERRIDE:p7w5-metabolization-source-lock-repair-2026-05-28`.
- Strict same-wave L4 validation can derive the authorized staged file set from `TASKS.md:457` and this packet without any predecessor-packet dependency.
- Required validation before commit handoff:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py::TestJSOuterLoopBoundary::test_js_routing_continuation_drivers_use_bounded_return_meta --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py --tb=short --durations=20`
  - `node mu/host/js/eval_step.js`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id p7w5-metabolization-source-lock-repair-2026-05-28 --wave-class L4_ENABLER`
  - `./tools/checks/check_docs_consistency.sh`
  - `git diff --check`
  - eventual commit executor `pre-push-fast` passes before push.

## Grounding / Authorization

- `TASKS.md:457` is the governing `[NEXT-CODEX-POST-REDTEAM]` tracker entry for `p7w5-metabolization-source-lock-repair-2026-05-28`. It records a same-wave `L4_ENABLER` Phase B pre-commit supervisor package for `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`, with package-bound L4 authority and 4 wave-owned files.
- Together, `TASKS.md:457` and this packet bind the repair wave to exactly these structural artifact refs: `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`, `TASKS.md`, `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`, and `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`.
- This packet authorizes no runtime, substrate, seed, scheduler, registry, branch-protection, workflow, predecessor-packet, prior-wave report, or generated bridge nonblocker delta.
- Same-wave authorization: FOUNDER_OVERRIDE:p7w5-metabolization-source-lock-repair-2026-05-28
- Authorization: standing pipeline-bug-fix authorization for `p7w5-metabolization-source-lock-repair-2026-05-28`, bound to the current governing packet `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md` and the same-wave TASKS grounding above.
- Governing packet for this repair wave: `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`.
- Reviewer evidence fixed by this rewrite:
  - the allowed write scope no longer names the predecessor packet or permits prior-wave control-surface cleanup;
  - same-wave scope, work items, stop conditions, acceptance criteria, and grounding now match the four artifact refs authorized by `TASKS.md:457`;
  - this packet retains the dedicated grounding/authorization section and machine-readable same-wave authorization lines required for commit automation.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `p7w5-metabolization-source-lock-repair-2026-05-28`
- Active packet: `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`
- Indicator artifact: `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`
  - `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `p7w5-metabolization-source-lock-repair-2026-05-28`
- Active packet: `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a9fdb0e08a752dfd891fa15d6fd696e7eb89fcf04c8a4aab052246c73412f47d`
- Indicator artifact: `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`
  - `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`
  - `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
