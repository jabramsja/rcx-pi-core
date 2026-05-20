# N3-Kernel-Driver-Structural-Fuel-Source-Lock-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-structural-fuel-source-lock-2026-05-20
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
FOUNDER_OVERRIDE:n3-kernel-driver-structural-fuel-source-lock-2026-05-20

## Scope

This packet is a Phase A/source-lock decision for the remaining live
kernel-driver fuel/maxSteps host-iteration markers. It does not authorize
runtime, substrate, seed, registry, loader, binary, checksum, scheduler,
dispatcher, commit, push, PR, or closeout edits.

Writable surface for this implementation:

- `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
- `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`,
  only as the validation artifact required by the same-wave
  `TASKS.md:393` `indicator_artifact_ref`
- `TASKS.md`, only as the existing same-wave routing authority note at
  `TASKS.md:393`

Read-only evidence surfaces:

- `reports/control_plane/n3-js-debt-summary-kernel-marker-truth-sync-2026-05-20.md`
- `mu/docs/core/BootstrapPrimitives.v0.md`
- `mu/docs/core/L4ExitChecklist.v0.md`
- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/js/engine/kernel.js`
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/js/engine/pipeline.js`
- `mu/tools/checks/host_semantics_baseline.json`

## Decision

Decision: **NO-GO for immediate Phase B production reduction of the active
kernel-driver fuel/maxSteps loops.**

Smallest routed prerequisite:
`n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`.

Prerequisite class: `L4_ENABLER` unless its later locked packet proves a
runtime/substrate write set and reclassifies itself as `L4_STRUCTURAL`.

Prerequisite task: prove JavaScript fuel-threading parity for the D006
linked-list fuel model, with explicit parity and negative-control tests, before
any production packet attempts to remove or reduce the active Python
`step_kernel_mu` loop or JavaScript `_stepKernelCore` `maxSteps` loop. The
prerequisite must not change the production kernel loops, ratchet baselines, or
marker locations.

No structural reduction is claimed by this packet. No tracked marker is removed
or expected to decrease in this packet.

## Authorization Evidence

- `TASKS.md:393` supplies same-wave routing authority for this exact packet and
  carries `FOUNDER_OVERRIDE:n3-kernel-driver-structural-fuel-source-lock-2026-05-20`.
  That tracker note explicitly supplies routing authority only; it does not
  claim runtime implementation or marker reduction.
- `TASKS.md:573-581` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked/open, says
  remaining structural reduction requires separate bounded packets, and keeps
  the pipeline/control-plane route as the governing workflow.
- `TASKS.md:368` records
  `n3-max-steps-structural-fuel-production-lock-2026-05-14` as a commit-ready
  Phase B handoff. This packet treats the run_trace boundary-fuel narrowing
  wave as already landed context and does not relist it as pending.
- `reports/control_plane/n3-js-debt-summary-kernel-marker-truth-sync-2026-05-20.md:212-218`
  identifies the current JS target as `_stepKernelCore` over `maxSteps`, not
  `bootstrap_core.step`.

## Doctrine Reconciliation

The doctrine conflict is real, but it is reconcilable without editing doctrine
in this packet.

- `mu/docs/core/BootstrapPrimitives.v0.md:143-146` says `max_steps` is
  irreducible, cannot be structural because it would require arithmetic on
  fuel, and notes that linked-list fuel was rejected by prior review.
- `mu/docs/core/L4ExitChecklist.v0.md:77-90` classifies `max_steps` as an
  integer parameter that is expressible as Mu data, but says the linked-list
  structural-counter path is still unproven without CPS or explicit fuel
  threading.
- `mu/docs/core/L4ExitChecklist.v0.md:185-186` later classifies `max_steps` as
  `REDUCIBLE_WITH CPS fuel threading`, with D006 as research evidence.
- `mu/docs/core/L4ExitChecklist.v0.md:199-205` limits G8 PASS to primitive
  classification evidence and states that production reduction claims require
  separate productionization gates.
- `mu/docs/core/L4ExitChecklist.v0.md:207-214` says production `max_steps`
  reduction requires JS fuel-threading parity, performance profiling for
  O(fuel) space versus O(1) integer behavior, and production integration with
  fuel parameter threading.

Chosen interpretation: the later L4 checklist is the controlling adjudication
for classification. `max_steps` is not permanently impossible, but the current
active production loops cannot be claimed reduced from D006 research evidence.
The production gate blocks immediate GO until the missing prerequisites are
proven.

## Current Target Truth

The remaining active target is limited to the Python `step_kernel_mu` driver and
the JavaScript `_stepKernelCore` loop.

Python:

- `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1172` marks
  `step_kernel_mu` with `@host_iteration` and exposes `max_steps`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1304-1308` still documents the
  active max_steps guard as a bootstrap primitive.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1317-1319` performs the live
  `for step_i in range(max_steps)` driver loop and consumes one shared budget
  unit per iteration.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1390-1399` returns
  `max_steps_exhausted` when the loop exhausts its host integer budget.

JavaScript:

- `mu/host/js/engine/kernel.js:72-77` marks `_stepKernelCore` as the active
  kernel driver loop over `maxSteps` and runs `for (let i = 0; i < maxSteps; i++)`.
- `mu/host/js/engine/kernel.js:103-134` returns structural terminal, hash
  stall, or `max_steps_exhausted` metadata from that loop.
- `mu/host/js/engine/kernel.js:145-150` keeps the public `stepKernel` default
  `maxSteps = 10000`.

Already-landed boundary context, citation only:

- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:706-735` validates explicit
  `run_trace` `max_steps`, rejects dirty/non-integer/negative/over-cap values,
  and passes the resulting integer to `run_mu_structural`.
- `mu/host/js/engine/pipeline.js:243-261` mirrors the `run_trace` boundary
  validation and cap before calling `runStructural`.

That boundary behavior is not pending work here.

## Why Immediate GO Is Blocked

Immediate GO would need a locked disjoint implementation write set, exact
parity/structural/negative-control tests, rollback/default behavior, and an
expected ratchet decrease from the current baseline. The current evidence does
not support that without first satisfying production prerequisites.

Current ratchet baseline:

- `mu/tools/checks/host_semantics_baseline.json:2-20` records five tracked host
  markers total: JavaScript has one `host_iteration` marker and Python has one
  `host_iteration` marker, plus the remaining host_builtin markers.

Expected ratchet effect for this packet:

- before: total `5`, JavaScript `host_iteration=1`, Python
  `host_iteration=1`
- after: total `5`, JavaScript `host_iteration=1`, Python
  `host_iteration=1`

Because neither active kernel-driver marker is expected to decrease in this
packet, this packet must not claim structural reduction.

The stop condition that fires is the productionization prerequisite gate:
`L4ExitChecklist.v0.md:207-214` requires JS fuel-threading parity and further
productionization proof before a production `max_steps` reduction claim.
Without that prerequisite, a Phase B implementation would either be speculative
production work from research-only evidence or a marker/baseline wording change
that leaves active loop semantics unchanged.

## Routed Prerequisite

Exact prerequisite packet/task to create next:

- Wave ID: `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20`
- Task: `[NEXT-CODEX-POST-REDTEAM]`
- Target gate: `G8`
- Class: `L4_ENABLER` by default
- Purpose: prove cross-substrate fuel-threading parity for linked-list fuel
  before production max_steps reduction is attempted

Minimum future evidence requirements:

- Cite `L4ExitChecklist.v0.md:90` for the unresolved CPS or explicit fuel
  threading requirement.
- Cite `L4ExitChecklist.v0.md:185-186` for the D006 research classification
  basis.
- Cite `L4ExitChecklist.v0.md:207-214` for the production prerequisite lock.
- Add or select exact parity and negative-control tests that demonstrate the JS
  fuel-threading model matches the existing D006 fuel behavior without changing
  production kernel loops.
- Preserve the current active-loop truth in
  `step_mu.py:1163-1172`, `step_mu.py:1317-1319`, and
  `kernel.js:72-77`.
- State that performance profiling and production integration with fuel
  parameter threading remain later prerequisites even if JS parity passes.

Stop conditions for that prerequisite:

- Stop if the JS fuel model requires host timers, host exception tables,
  thread-state checks, substrate-specific shortcuts, or host-only accepted sets.
- Stop if the proof cannot be made parity-comparable with Python D006 behavior.
- Stop if the only available result is comment, marker, debt-map, or baseline
  adjustment while production loop behavior remains unchanged.
- Stop before production loop edits unless a later packet locks a full
  `L4_STRUCTURAL` write set, tests, rollback/default behavior, and ratchet
  expectation.

## Validation Plan

Phase B-local validation for this packet is limited to control-plane/doc and
ratchet checks. No focused runtime tests are selected because the decision is
NO-GO and no runtime/test implementation is authorized.

Commands:

- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-structural-fuel-source-lock-2026-05-20 --output reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json --range HEAD`
- `python3 tools/checks/enforce_l4_execution_contract.py --files TASKS.md reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json --wave-id n3-kernel-driver-structural-fuel-source-lock-2026-05-20 --wave-class L4_ENABLER`
- `./tools/checks/check_docs_consistency.sh`

## Proof Limits

- This packet proves only a NO-GO decision and a smallest next prerequisite.
- It does not prove production `max_steps` reduction.
- It does not reduce host-semantics markers.
- It does not reopen the already-landed run_trace boundary-fuel narrowing wave.
- It does not treat `bootstrap_core.step` as the current JS tracked iteration
  site.
- It does not change doctrine text; the doctrine conflict remains a documented
  historical/current-adjudication tension, with production claims governed by
  `L4ExitChecklist.v0.md:207-214`.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-structural-fuel-source-lock-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-structural-fuel-source-lock-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `48dd21cf9ab3b761c95c0c06bc0dbb7404aa1e90585eaadffc53908954434e01`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-kernel-driver-structural-fuel-source-lock-2026-05-20 --output reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-kernel-driver-structural-fuel-source-lock-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-structural-fuel-source-lock-2026-05-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
