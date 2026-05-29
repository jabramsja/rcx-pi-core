# JS Stage0 VM Trusted Run Hot Path

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `js-stage0-vm-trusted-run-hotpath-2026-05-29`
Wave class: `L4_STRUCTURAL`
Target gate: `G8`
Phase-A-Lock: LOCKED
Governing packet: `reports/control_plane/js-stage0-vm-trusted-run-hotpath-2026-05-29_2026-05-29.md`

## Scope

This Phase A packet authorizes design for a bounded JavaScript Stage0 VM trusted-run hot-path optimization. The candidate implementation surface is limited to:

- `mu/host/js/core/stage0_vm.js`
- `mu/host/js/engine/kernel.js`
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
- Additional focused JS parity or L4 test files only if Phase B proves a direct need for trusted-run source-lock, `options.vmConfig` fail-closed proof, or behavior proof.
- `TASKS.md`, as grounding/validation evidence only for the existing same-wave tracker entry required by `TASKS.md:663` and present at `TASKS.md:742`; this packet does not relist tracker creation as pending work.
- `reports/control_plane/js-stage0-vm-trusted-run-hotpath-2026-05-29_2026-05-29.md`
- `reports/l4_wave_indicators/js-stage0-vm-trusted-run-hotpath-2026-05-29.json`
- A same-wave generated non-blocking bridge findings packet only if the pipeline produces one.

The work targets repeated public JS Stage0 VM bundle validation on production trusted kernel, bridge, match, and substitution paths. Current code truth from the reviewer-cited files is:

- `mu/host/js/core/stage0_vm.js:996` through `mu/host/js/core/stage0_vm.js:998` show public `stage0VmStep()` calling `validateBundle(bundle)` before delegating to `_stage0VmStepTrusted(...)`.
- `mu/host/js/core/stage0_vm.js:1004` through `mu/host/js/core/stage0_vm.js:1013` show public `stage0VmRun()` calling public `stage0VmStep()` on every VM step, which explains the repeated validation hot path.
- `mu/host/js/engine/kernel.js:39` through `mu/host/js/engine/kernel.js:43` currently document caller-side prevalidation for custom `vmConfig`, but comments are not mechanical fail-closed proof.
- `mu/host/js/engine/kernel.js:45` through `mu/host/js/engine/kernel.js:62` show `_stepKernelWithVM(...)` receives `kernelBundle`, `bridgeBundle`, `matchBundle`, and `substBundle`, then calls `_stage0VmStepTrusted(...)` on each provided bundle.
- `mu/host/js/engine/kernel.js:1913` through `mu/host/js/engine/kernel.js:1923` show cutover and shadow execution pass custom `vmConfig.kernelBundle`, `vmConfig.bridgeBundle`, `vmConfig.matchBundle`, and `vmConfig.substBundle` into `_stepKernelWithVM(...)`.
- `mu/host/js/engine/kernel.js:2206` through `mu/host/js/engine/kernel.js:2215` accept `options.vmConfig || null` and pass it into `_stepKernelCore(...)`, so any trusted-run bypass must account for every custom `options.vmConfig` bundle entry path before using a private trusted helper.

## Work Items

1. Keep the wave bound to the active `[NEXT-CODEX-POST-REDTEAM]` authority before implementation: `TASKS.md` carries a same-wave tracker sync note for `js-stage0-vm-trusted-run-hotpath-2026-05-29`, and the packet must continue to cite the same-wave `FOUNDER_OVERRIDE:js-stage0-vm-trusted-run-hotpath-2026-05-29` authorization before any runtime change can be accepted.
2. Add a private trusted JS multi-step Stage0 VM helper, or an equivalent bounded trusted helper, for already-trusted bundles. It must call `_stage0VmStepTrusted(...)` internally and must not call public `stage0VmStep()` once per VM step.
3. Before any `options.vmConfig` bundle reaches the private trusted run helper, add a mechanical fail-closed trust boundary in `mu/host/js/engine/kernel.js`: either validate every accepted `vmConfig.kernelBundle`, provided `vmConfig.bridgeBundle`, `vmConfig.matchBundle`, and `vmConfig.substBundle` exactly once at the `options.vmConfig` acceptance boundary, or replace the comment-only contract with a mechanically provenance-bound loader-validated bundle path that arbitrary custom callers cannot forge for any of those bundle slots. Phase B must choose one path and record why it is fail-closed for all four trusted VM inputs.
4. Use the trusted run helper only at the existing JS production trusted VM call sites for `vmConfig.kernelBundle`, `vmConfig.bridgeBundle`, `vmConfig.matchBundle`, and `vmConfig.substBundle` in `mu/host/js/engine/kernel.js`, and only after the trust boundary from work item 3 has executed or been mechanically proven for every accepted bundle slot.
5. Preserve public `stage0VmRun()` and public `stage0VmStep()` fail-closed validation behavior. The default public API must continue to reject malformed public bundles, and the trusted helper must not become a public substitute for validation.
6. Update trusted-path source locks so the helper remains a private trusted surface and is allowed only from `mu/host/js/engine/kernel.js` plus focused tests. The source lock must also prove the helper is not reachable from arbitrary `options.vmConfig` values without the trust boundary.
7. Add focused behavioral proof that trusted JS run output matches public JS run for valid loader-cached bundles, public malformed bundles still reject, and malformed custom `options.vmConfig.kernelBundle`, provided `options.vmConfig.bridgeBundle`, `options.vmConfig.matchBundle`, and `options.vmConfig.substBundle` values fail closed before any trusted multi-step helper can bypass validation.
8. Collect before/after timing for JS Paxos `run_engine_pipeline` and `run_engine_with_routing` JSON API actions, tied specifically to the repeated JS Stage0 VM validation path. Treat the current-dev baselines as approximately 14.65s and 16.83s respectively, not as broad CI closure.

## Constraints

- Do not implement the runtime change in this packet rewrite turn.
- Do not treat this packet as proof that every listed implementation item is still unlanded; this rewrite inspected only the target packet, exact `[NEXT-CODEX-POST-REDTEAM]` TASKS lines, and reviewer-cited code lines.
- Do not use `run_review.py`.
- Route implementation through dispatcher Phase A, Phase B, pre-commit supervisor, and commit executor.
- Do not weaken, skip, xfail, delete, or marker-move tests.
- Do not edit ratchet baselines, seed content, Stage0 semantics, workflows, branch protection, or Claude surfaces.
- Do not edit Python unless Phase B proves a direct parity or safety need; the Python trusted bounded helper is reference evidence, not edit authorization.
- Do not expose a new public trust or copy-laundering path. The trusted helper must remain private to mechanically validated or mechanically provenance-bound production use.
- Do not treat caller comments, loader naming, or existing public malformed-bundle rejection as sufficient proof that custom `options.vmConfig` bundles are fail-closed.
- Do not claim broad CI closure from local timings.
- Manual pipeline recovery is allowed only as a bounded unblocker and must be paired with a same-wave mechanical pipeline fix or a precise follow-up automation packet with evidence.

## Stop Conditions

- Stop before implementation or commit review if `TASKS.md` lacks the same-wave tracker entry for `js-stage0-vm-trusted-run-hotpath-2026-05-29`.
- Stop if the trusted helper changes accepted Mu values, weakens public fail-closed validation, exposes a new public trust/copy-laundering path, or broadens trusted access beyond `mu/host/js/engine/kernel.js` and focused tests.
- Stop if custom `options.vmConfig` can still reach the trusted multi-step helper through comment-only caller prevalidation, unvalidated `kernelBundle` / `bridgeBundle` / `matchBundle` / `substBundle` values, or forgeable provenance.
- Stop if malformed custom `options.vmConfig.kernelBundle`, provided `options.vmConfig.bridgeBundle`, `options.vmConfig.matchBundle`, and `options.vmConfig.substBundle` negative controls are missing, or if they only exercise public `stage0VmRun()` / `stage0VmStep()` instead of the production kernel `options.vmConfig` entry path.
- Stop if measured before/after timing does not meet the acceptance threshold below, or if the improvement cannot be tied to the repeated JS Stage0 VM validation path.
- Stop if host-semantics or authority ratchets increase.
- Stop if the required fix is really a larger `isValidMu`, `muCopy`, or container-allocation redesign; emit a follow-up bounded packet with profile evidence instead of overreaching.
- Stop if Phase B requires runtime, seed, scheduler, registry, workflow, branch-protection, Claude-surface, or ratchet-baseline changes outside this packet.

## Acceptance Criteria

The wave is not done until all of the following are true:

- Authorization is mechanically derivable: `TASKS.md` has a same-wave tracker entry for `js-stage0-vm-trusted-run-hotpath-2026-05-29`, and this governing packet cites the `[NEXT-CODEX-POST-REDTEAM]` source authorization below.
- Public fail-closed behavior is preserved: malformed bundles still reject through public `stage0VmRun()` / `stage0VmStep()` coverage, and valid loader-cached trusted bundles produce the same JS outputs through trusted run and public run paths.
- Custom `options.vmConfig` fail-closed behavior is mechanically proven: malformed `kernelBundle`, provided malformed `bridgeBundle`, malformed `matchBundle`, and malformed `substBundle` values passed through the kernel `options.vmConfig` entry path reject before trusted multi-step execution, or every accepted `options.vmConfig` bundle is mechanically loader-validated/provenance-bound in a way arbitrary callers cannot forge.
- Trusted access is bounded: source-lock coverage proves the new trusted run helper is private, is used only by `mu/host/js/engine/kernel.js` and focused tests, and cannot be called for custom `options.vmConfig` bundles before the one-time validation/provenance gate.
- If Phase B chooses one-time validation, evidence must show validation happens once per accepted `kernelBundle`, provided `bridgeBundle`, `matchBundle`, and `substBundle` before trusted multi-step use, not once per VM step and not zero times for custom callers. If Phase B chooses provenance binding instead, evidence must show all accepted `options.vmConfig` entry paths are loader-validated and unforgeable by custom callers.
- Performance success is meaningful and repeatable: on the same machine and command shape, after one warm-up, collect at least five before runs and five after runs for JS Paxos `run_engine_pipeline` and `run_engine_with_routing`. Each action must show both a median improvement of at least 10 percent and an absolute median improvement of at least 1.0s versus the same-session before baseline, and at least four of five after runs must be faster than the before median. If runtime budget forces fewer samples, Phase B must record why and must not claim performance closure from fewer than three before and three after runs.
- The timing report must compare against the current-dev reference values in this packet, approximately 14.65s for JS `run_engine_pipeline` Paxos and 16.83s for JS `run_engine_with_routing` Paxos, but the pass/fail threshold is same-session before/after to avoid noise-level wins.
- Focused validation passes, including `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py --tb=short`.
- Focused Paxos parity selectors pass or are explicitly recorded as runtime-budget deferred before broad claims: `TestEnginePipelineCrossSubstrateParity::test_engine_pipeline_paxos_parity`, `TestEnginePipelineCrossSubstrateParity::test_full_pipeline_with_routing_parity`, and `TestBoot1FourWayParity::test_paxos_freeze_four_way`.
- Required runtime and governance checks pass before commit review: `node mu/host/js/eval_step.js`, `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`, `python3 tools/checks/check_host_authority_inventory_ratchet.py`, `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id js-stage0-vm-trusted-run-hotpath-2026-05-29 --wave-class L4_STRUCTURAL`, `./tools/checks/check_docs_consistency.sh`, and `git diff --check`.
- Commit executor pre-push-fast and the GitHub seven-check PR surface are green before merge.

## Grounding / Authorization

TASKS.md authorization: `TASKS.md:655` marks `[NEXT-CODEX-POST-REDTEAM]` as `UNPARKED` and founder-authorized. `TASKS.md:658` keeps the current phase open for remaining structural reduction through separate bounded packets. `TASKS.md:663` orders autonomous dispatcher/pipeline execution, requires every wave to have a control-plane packet plus a `TASKS.md` tracker entry, orders `/mu` structural remediation last with a hard stop before implementation, and carries `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.

TASKS.md tracker entry status: `TASKS.md:742` carries the detector-visible same-wave tracker sync note for `js-stage0-vm-trusted-run-hotpath-2026-05-29`. The note binds the wave id, Class `L4_STRUCTURAL`, target gate `G8`, governing packet, structural artifact refs, strict staged L4 evidence command, same-wave override, indicator artifact metadata, invariant metadata, bootstrap policy, and Boot0 metadata required by strict staged L4 validation.

Reviewer-cited runtime grounding: `mu/host/js/core/stage0_vm.js:996` through `mu/host/js/core/stage0_vm.js:1013` prove public run currently validates through public step on every VM step. `mu/host/js/engine/kernel.js:39` through `mu/host/js/engine/kernel.js:43` prove custom `vmConfig` prevalidation is currently documented as a caller obligation. `mu/host/js/engine/kernel.js:45` through `mu/host/js/engine/kernel.js:62` prove `_stepKernelWithVM(...)` feeds `kernelBundle`, `bridgeBundle`, `matchBundle`, and `substBundle` into `_stage0VmStepTrusted(...)`. `mu/host/js/engine/kernel.js:1913` through `mu/host/js/engine/kernel.js:1923` prove cutover and shadow execution pass all four custom `vmConfig` bundle slots into that trusted path. `mu/host/js/engine/kernel.js:2206` through `mu/host/js/engine/kernel.js:2215` prove `options.vmConfig` is accepted and passed into kernel core, so the trusted-run optimization must add one-time validation or provenance-bound loader proof before helper use for every accepted `vmConfig` bundle slot.

Governing packet: this file, `reports/control_plane/js-stage0-vm-trusted-run-hotpath-2026-05-29_2026-05-29.md`, is the Phase A packet for wave `js-stage0-vm-trusted-run-hotpath-2026-05-29`.

Source authorization: `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.

Same-wave authorization: `FOUNDER_OVERRIDE:js-stage0-vm-trusted-run-hotpath-2026-05-29`.

## Phase B Implementation Evidence

Phase B chose one-time validation rather than provenance-only binding. `mu/host/js/engine/kernel.js` now strict-copies each accepted custom `vmConfig.kernelBundle`, provided `vmConfig.bridgeBundle`, `vmConfig.matchBundle`, and `vmConfig.substBundle` into a private Mu snapshot, validates that snapshot through `validateBundle(...)` before any trusted VM helper is used, freezes the accepted bundle snapshots, returns a frozen validated `vmConfig` wrapper, records only that wrapper in a private `WeakSet`, and keeps `_stepKernelCore(...)` as a backstop for direct internal callers. This closes the bridge-identified live-reference gap: accessor-backed or caller-mutated source bundles cannot be read again by trusted execution after validation. Public `stage0VmRun(...)` and `stage0VmStep(...)` also strict-copy and validate caller bundles before delegating to trusted execution, while the private `_stage0VmRunTrusted(...)` helper calls `_stage0VmStepTrusted(...)` directly and does not call public `stage0VmStep(...)` per VM step.

Focused source-lock and behavior evidence live in `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`. The gate now proves the trusted run helper is allowed only in `mu/host/js/core/stage0_vm.js`, `mu/host/js/engine/kernel.js`, and the focused gate; public malformed JS run rejects through `stage0VmRun(...)`; public accessor-backed `stage0VmRun(...)` and `stage0VmStep(...)` reject before live bundle accessors can swap data; trusted JS run output matches public run output on a valid loader-cached bundle; malformed `options.vmConfig.kernelBundle`, provided `bridgeBundle`, `matchBundle`, and `substBundle` fail at the production `stepKernel(..., { vmConfig })` entry path before patched trusted helpers can run; accessor-backed custom `vmConfig` bundle slots fail before trusted helpers can read live references; caller-owned `vmConfig` slot mutation after an initial validation pass revalidates and fails closed for all four trusted bundle slots; and valid custom `vmConfig` validation is counted exactly once per four accepted bundle slots.

Same-session JS Paxos timing evidence, collected after one warm-up and five measured runs per action on this machine, is recorded in `reports/l4_wave_indicators/js-stage0-vm-trusted-run-hotpath-2026-05-29.json`.

| Action | Reference | Before samples | Before median | After samples | After median | Median improvement | Faster-than-before-median |
| --- | ---: | --- | ---: | --- | ---: | ---: | ---: |
| `run_engine_pipeline` | ~14.65s | 14.810, 14.970, 18.656, 14.707, 14.888 | 14.888s | 12.466, 12.729, 12.749, 12.555, 12.645 | 12.645s | 2.243s / 15.1% | 5/5 |
| `run_engine_with_routing` | ~16.83s | 17.181, 16.479, 16.189, 17.248, 16.350 | 16.479s | 14.254, 14.286, 14.457, 14.487, 14.125 | 14.286s | 2.193s / 13.3% | 5/5 |

Questions? Concerns? Thoughts? -- Think hard
