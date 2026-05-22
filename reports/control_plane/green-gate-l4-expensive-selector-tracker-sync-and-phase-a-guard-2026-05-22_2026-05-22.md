# Green-Gate-L4-Expensive-Selector-Tracker-Sync-And-Phase-A-Guard-2026-05-22

Date: 2026-05-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED

Purpose: Create and lock a bounded control-plane pipeline repair packet for the
green-gate L4 expensive-selector tracker-sync blocker and the missing Phase A
guard that allowed strict staged L4 acceptance to depend on a wave id absent
from TASKS tracker authority.

## Scope

Files/directories in scope for the implementation wave:

- `TASKS.md`, only for detector-visible tracker sync notes required by this
  wave and by the prior selector-budget repair wave id
  `green-gate-l4-expensive-selector-budget-repair-2026-05-22`.
- This governing packet:
  `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`.
- Same-wave L4 indicator artifacts required by the declared tracker notes:
  `reports/l4_wave_indicators/green-gate-l4-expensive-selector-budget-repair-2026-05-22.json`
  and
  `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`.
- `reports/control_plane/` and `reports/deferred/` bookkeeping only when needed
  to record this tracker-sync/guard wave or a precise blocker.
- Narrow control-plane pipeline code/tests under `mu/tools/executors`,
  `tools/checks`, or `mu/tests/tools` when needed for the Phase A guard.

This Phase A rewrite is a plan-only repair. It does not assert that the
underlying implementation work is already landed, and it does not inspect
downstream implementation files to decide that question.

- `reports/deferred/non_blocking/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Add TASKS tracker authority for
   `green-gate-l4-expensive-selector-budget-repair-2026-05-22` so the existing
   strict staged L4 command can bind the prior selector-budget repair to a
   detector-visible tracker note.
2. Ensure this wave carries same-wave L4 authorization before implementation
   dispatch: `FOUNDER_OVERRIDE:green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22`.
3. Add a narrow deterministic automated fail-closed guard in an existing
   Phase A builder, receipt, check, executor, or L4 checker surface so Phase A
   cannot lock a control-plane packet that makes strict staged L4 `--wave-id`
   acceptance mandatory while omitting tracker-sync authority, TASKS scope, or
   same-wave authorization.
4. Add focused regression coverage for the guard in the existing control-plane
   pipeline test surface. The negative regression must execute the mechanical
   guard and prove the missing-authority case fails before Phase A lock; prompt,
   reviewer, checklist, or documentation hardening alone does not satisfy this
   requirement. The positive regression must prove that a properly grounded
   same-wave packet can proceed.
5. If an existing builder, receipt, check, executor, or L4 checker surface
   already owns this policy, wire the guard and regression there rather than
   adding a parallel policy path.

## Constraints

- Do not change runtime, substrate, Stage0, engine, seed, scheduler, registry,
  projection, loader, host-oracle, or Mu semantic files.
- Do not hand-author runtime behavior or Mu semantics.
- Do not use baseline-only cleanup, broad docs edits, or unrelated refactors as
  a substitute for the tracker sync and Phase A guard.
- Do not edit Claude-related files.
- Do not manually bypass strict L4, repeat-finding, or tracker-governance
  failures.
- Do not treat prompt, reviewer, checklist, or documentation hardening as the
  Phase A guard unless deterministic automated fail-closed enforcement rejects
  the malformed packet before lock.
- Do not relist already-landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- If a blocking finding or allowed acceptance proof shows a listed work item is
  already implemented in current code, remove it from pending work and
  acceptance instead of re-implementing it.

## Stop Conditions

- Stop if the required TASKS tracker sync cannot be expressed as a bounded,
  detector-visible note under `[NEXT-CODEX-POST-REDTEAM]`.
- Stop if the strict staged L4 command for
  `green-gate-l4-expensive-selector-budget-repair-2026-05-22` still fails for a
  reason outside tracker authority after the tracker-sync repair.
- Stop if the Phase A guard cannot be added in an existing control-plane
  builder, receipt, check, executor, or L4 checker surface without touching
  forbidden runtime/Mu semantic files.
- Stop if the only available repair is prompt, reviewer, checklist, or
  documentation hardening without same-wave deterministic automated
  fail-closed enforcement before Phase A lock.
- Stop if the work would require widening beyond the scoped files or changing
  unrelated docs, reports, tests, or executor behavior.
- Stop with a precise blocker instead of hand-editing around pipeline governance
  if automation cannot safely express the policy in this wave.

## Acceptance Criteria

1. `TASKS.md` contains a detector-visible tracker sync note for
   `green-gate-l4-expensive-selector-budget-repair-2026-05-22` under
   `[NEXT-CODEX-POST-REDTEAM]`.
2. The prior selector-budget repair satisfies:
   `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id green-gate-l4-expensive-selector-budget-repair-2026-05-22 --wave-class L4_ENABLER`.
3. A focused regression proves deterministic automated Phase A builder,
   receipt, check, executor, or L4 checker enforcement rejects a packet that
   requires strict staged L4 `--wave-id` acceptance while omitting TASKS
   tracker authority or same-wave authorization, and does so before Phase A
   lock.
4. A matching positive regression or focused acceptance path through the same
   deterministic enforcement proves a properly grounded same-wave
   control-plane packet is accepted.
5. No runtime, substrate, Stage0, engine, seed, scheduler, registry,
   projection, loader, host-oracle, or Mu semantic files change.
6. This packet retains the required Phase A sections: Scope, Work Items,
   Constraints, Stop Conditions, Acceptance Criteria, and Grounding /
   Authorization.

## Grounding / Authorization

- TASKS.md is canonical authority: `TASKS.md:3` states it is the single source
  of truth for authorized work, and `TASKS.md:4` states unlisted tasks are not
  to be implemented.
- Current task authority: `TASKS.md:625` marks `[NEXT-CODEX-POST-REDTEAM]` as
  unparked and founder-authorized; `TASKS.md:627` keeps the Phase A -> Phase B
  -> Phase C -> Phase D sequence; `TASKS.md:628` keeps the queue open for
  separate bounded packets.
- Pipeline-governance authority: `TASKS.md:633` requires every wave to carry a
  control-plane packet plus a `TASKS.md` tracker entry, and allows manual
  pipeline repair only as a bounded unblocker paired with a same-wave
  mechanical/automated fix in dispatcher, builder, recovery, commit,
  pre-commit, or another appropriate pipeline surface, or with a precise
  follow-up automation packet. Prompt, reviewer, checklist, or documentation
  hardening alone is not a same-wave mechanical/automated fix and cannot
  satisfy this packet's Phase A guard.
- Governing packet for this wave:
  `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`.
- Prior wave to unblock:
  `green-gate-l4-expensive-selector-budget-repair-2026-05-22`.
- FOUNDER_OVERRIDE:green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.
- Authorization: standing pipeline-bug-fix authorization for a bounded
  control-plane L4_ENABLER tracker-sync and Phase A guard repair under
  `[NEXT-CODEX-POST-REDTEAM]`; this authorization does not permit runtime/Mu
  semantic changes or unrelated repo edits.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22`
- Active packet: `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`
- Indicator artifact: `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
  - `mu/tests/l4_gates/test_metabolize_cycle_gate.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/green-gate-l4-expensive-selector-budget-repair-2026-05-22_2026-05-22.md`
  - `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`
  - `reports/deferred/non_blocking/green-gate-l4-expensive-selector-budget-repair-2026-05-22_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/green-gate-l4-expensive-selector-budget-repair-2026-05-22.json`
  - `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22`
- Active packet: `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `45fd4b1c9d39fbe8ac7cafcefe86450071c3e65a44464e7edf211b52530f09a0`
- Indicator artifact: `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/tools/test_executor_dispatch.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`
  - `mu/tests/l4_gates/test_metabolize_cycle_gate.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/green-gate-l4-expensive-selector-budget-repair-2026-05-22_2026-05-22.md`
  - `reports/control_plane/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_2026-05-22.md`
  - `reports/deferred/non_blocking/green-gate-l4-expensive-selector-budget-repair-2026-05-22_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/green-gate-l4-expensive-selector-budget-repair-2026-05-22.json`
  - `reports/l4_wave_indicators/green-gate-l4-expensive-selector-tracker-sync-and-phase-a-guard-2026-05-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
