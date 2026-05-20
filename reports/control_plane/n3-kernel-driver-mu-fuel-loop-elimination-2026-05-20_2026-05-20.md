# N3-Kernel-Driver-Mu-Fuel-Loop-Elimination-2026-05-20

Date: 2026-05-20
Status: Phase B (implementation-complete, bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20
Class: L4_STRUCTURAL
Category: /mu structural host-semantics reduction
Target gate: G8
Phase-A-Lock: LOCKED
Governing packet: `reports/control_plane/n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20_2026-05-20.md`
Source authorization: `TASKS.md:581-589`, including `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`
Same-wave authorization: `FOUNDER_OVERRIDE:n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20`
Purpose: Plan a bounded L4_STRUCTURAL wave for the remaining kernel-driver host_iteration sites after PR #1008. The post-merge supervisor evidence for this packet states that `mu/host/js/engine/kernel.js` still marks `_stepKernelCore` with `@host_iteration` over `for (let i = 0; i < maxSteps; i++)`, and `mu/host/python/rcx_pi/selfhost/step_mu.py` still marks `step_kernel_mu` with `@host_iteration` over `range(max_steps)`. PRs #1006/#1008 moved production exhaustion authority to Mu linked-list fuel but did not remove those mechanical host loops. The objective is to remove host semantic authority, preferably by eliminating the remaining markers through a Mu/fuel structural driver or a proven smaller bootstrap primitive; if that is not architecturally bounded in one wave, the wave must produce the smallest honest split that narrows host authority and adds a failing gate for the residual gap.

## Scope

- Code surfaces in scope for the downstream implementation wave:
  - `mu/host/js/engine/kernel.js`: `_stepKernelCore` kernel-driver loop and its `maxSteps` boundary.
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`: `step_kernel_mu` kernel-driver loop and its `max_steps` boundary.
- Test and gate surfaces in scope:
  - Focused Python/JS parity coverage for equivalent kernel-driver behavior.
  - Focused structural coverage proving host loop authority is eliminated or narrowed.
  - Host-semantics ratchet and host-authority inventory evidence.
- Control-plane/evidence surfaces in scope:
  - This governing packet.
  - The active `[NEXT-CODEX-POST-REDTEAM]` TASKS authorization and same-wave tracker/override requirements.
  - Existing repo builder, receipt, dispatcher, and L4 execution-contract surfaces only as needed to package and validate the bounded wave.

## Work items

1. Before implementation, re-check the two cited target sites and remove any item from pending work if current code already proves it landed. TASKS.md authorizes bounded future structural work; it does not prove that every packet item remains unlanded.
2. Close the control-plane authorization gap before code changes or commit packaging: the active TASKS directive requires every wave to have a control-plane packet plus a TASKS tracker entry, and reviewer evidence reports no current exact `TASKS.md` hit for `n3-kernel-driver-mu-fuel-loop-elimination`.
3. Replace or strictly narrow the JavaScript `_stepKernelCore` host iteration driver so Mu/fuel structure, not a host loop counter, owns semantic progress. Keep `maxSteps` only as a hard boundary/watchdog if it remains necessary.
4. Mirror the same structural reduction in Python `step_kernel_mu`, preserving Python/JS behavior and proof shape instead of making either substrate smarter.
5. Add or update focused tests that fail if the removed/narrowed host_iteration authority returns, including parity evidence for the JS and Python kernel-driver paths.
6. Run and record host-semantics ratchet evidence and host-authority inventory evidence. A successful wave must not hide new host authority behind marker relabeling, baseline-only cleanup, or looser tests.
7. If full host_iteration elimination is not bounded, stop with the smallest honest split: land only a real authority reduction, add a failing residual gate for the remaining host loop, and write the next precise packet rather than claiming closure.

## Phase B implementation result

Current source truth at Phase B start confirmed both cited sites still existed:

- `mu/host/js/engine/kernel.js::_stepKernelCore` carried `@host_iteration`
  over `for (let i = 0; i < maxSteps; i++)`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py::step_kernel_mu` carried
  `@host_iteration` over `for step_i in range(max_steps)`.

Full marker elimination was not bounded without moving host authority into an
unreviewed helper, host recursion, or a broader bootstrap-driver redesign. The
implemented split therefore narrows both loops:

- when Mu linked-list fuel is supplied, each kernel step consumes one fuel node;
- `maxSteps` / `max_steps` is checked before the next step as a hard watchdog;
- the legacy no-fuel compatibility path remains explicit residual
  `@host_iteration` debt;
- focused tests fail if the old maxSteps-owned kernel-driver loop returns.

Residual follow-up packet:
`reports/control_plane/n3-kernel-driver-residual-host-loop-elimination-followup-2026-05-20.md`.

## Constraints

- Do not merely relabel markers, move comments, loosen tests, or edit ratchet baselines as a substitute for structural reduction.
- Do not add host-only semantic interpretation in Python or JavaScript.
- Do not broaden into Stage0, seed, registry, scheduler, loader, binary/TLV, checksum, integrity-chain, or unrelated runtime refactors.
- Do not change Claude files or unrelated docs.
- Do not treat the landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not use this Phase A packet rewrite as authorization to implement runtime changes in this turn.
- Do not proceed past Phase A if same-wave tracker authority remains detector-invisible to the pipeline gate that requires it.

## Stop conditions

- Current code truth, checked at Phase B start, proves either cited target no longer exists or no longer carries host semantic authority. Remove that item from the implementation scope and reroute instead of preserving stale packet work.
- Eliminating both loops requires broad Stage0/seed/registry/scheduler or substrate redesign. Stop and split the work; do not smuggle the broad refactor into this wave.
- The proposed change would make Python and JS semantically divergent or would rely on one substrate becoming smarter than the other.
- `maxSteps`/`max_steps` remains a semantic progress driver rather than a watchdog boundary after the proposed change.
- Required evidence cannot distinguish real authority reduction from marker movement, baseline edits, or test weakening.
- The TASKS tracker/same-wave authorization gap blocks packaging or commit automation. Stop for tracker sync rather than implementing through an authorization hole.

## Acceptance criteria

- The downstream wave either eliminates both cited kernel-driver `@host_iteration` sites or lands a smaller structural reduction with an explicit failing residual gate and next-wave packet.
- `maxSteps` and `max_steps`, if retained, are documented and tested as hard watchdog boundaries only, not semantic termination authority.
- Python and JS kernel-driver behavior remain parity-preserving under focused tests.
- Host-semantics ratchet evidence shows no increase and records any legitimate decrease from removed host_iteration markers.
- Host-authority inventory evidence shows no unaccepted new authority site or total-inventory increase.
- Focused structural tests fail if the JS `_stepKernelCore` or Python `step_kernel_mu` host loop authority is reintroduced.
- L4 execution-contract validation for `n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20` passes for the staged implementation wave with the correct class and same-wave authorization.
- The control-plane package remains grounded in this packet plus TASKS authorization and does not claim a same-wave TASKS tracker entry exists until one is actually present.

## Grounding / Authorization

- `TASKS.md:581` marks `[NEXT-CODEX-POST-REDTEAM]` as unparked and founder-authorized.
- `TASKS.md:583-584` keeps the sequence open for bounded downstream structural reduction.
- `TASKS.md:585` warns not to relist the landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration items as unresolved.
- `TASKS.md:589` is the active founder-ordered directive: every wave requires a control-plane packet plus a `TASKS.md` tracker entry; manual pipeline repair must be paired with a same-wave mechanical fix or precise follow-up packet. Source authorization: `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- `TASKS.md:599-600` records the immediately preceding marker-truth and debt-summary sync waves, including the current JS `_stepKernelCore` maxSteps loop as the next true structural-reduction target.
- Reviewer evidence for this rewrite is authoritative that the prior packet was a stub and that an exact `TASKS.md` search did not find `n3-kernel-driver-mu-fuel-loop-elimination`.
- This packet is the governing Phase A packet for `n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20`.
- Same-wave override for this packet and downstream automation: `FOUNDER_OVERRIDE:n3-kernel-driver-mu-fuel-loop-elimination-2026-05-20`.