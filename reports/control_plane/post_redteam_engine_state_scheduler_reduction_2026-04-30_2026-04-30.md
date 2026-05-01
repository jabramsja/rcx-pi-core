# Post Redteam Engine State Scheduler Reduction 2026-04-30

Date: 2026-04-30
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-redteam-engine-state-scheduler-reduction-2026-04-30
Class: L4_STRUCTURAL
Authorization: FOUNDER_OVERRIDE:post-redteam-engine-state-scheduler-reduction-2026-04-30
Phase-A-Lock: LOCKED

Purpose: Convert the post-redteam structural authorization into the first bounded downstream implementation plan. This packet targets only the first-sequenced F-1/F-2 reduction from the locked Phase A sweep: formal engine state plus scheduler/operator-pool boundary. It does not implement the reduction in this turn.

Evidence boundary for this rewrite: this packet was rewritten from the target file, TASKS.md lines 364-369, the governing structural queue, and the locked Phase A sweep findings F-1/F-2. No downstream implementation files were inspected for this rewrite.

## 1. Scope

This Phase A packet governs the next implementation pass for the F-1/F-2 engine-state and scheduler reduction only.

Files and directories in scope for the future implementation pass:

- `mu/programs/rcx_engine_state.v1.json` -- new formal engine-state seed/schema artifact.
- `mu/programs/rcx_engine_scheduler.v1.json` -- new scheduler/operator-pool seed artifact.
- `mu/programs/rcx_engine.v1.json` -- limited integration only if needed to reference the new structural state/scheduler artifacts.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` -- limited to the existing `run_algorithm` scheduler-entry boundary/allowlist wiring cited by F-2.
- `mu/host/js/engine/pipeline.js` -- parity wiring for the same scheduler-entry boundary/allowlist.
- `mu/closures/exhaustion.v1.json` -- read-only reference for existing operator/freeze/pool semantics; write only if the implementation proves a projection handoff is required, otherwise stop and replan.
- `mu/tests/structural/test_rcx_engine_state_seed.py` -- new structural tests for the engine-state artifact.
- `mu/tests/structural/test_rcx_enginenew_scheduler.py` -- new structural tests for the scheduler artifact.
- `mu/tests/fixtures/rcx_engine_state_minimal.json` -- new minimal state fixture.
- `mu/tests/fixtures/rcx_enginenew_scheduler_operator_pool.json` -- new scheduler/operator-pool fixture.
- `tests/parity/test_rcx_engine_scheduler_parity.py` -- new Python/JS parity test for the scheduler seed path.
- Existing engine parity gates may be run but not broadened beyond engine scope: `tests/parity/test_rcx_engine_parity.py` and `tests/parity/test_rcx_engine_workload_contract_parity.py`.

Wave-bound Phase B bootstrap exception:

- `BOOTSTRAP_PHASE_B_EXCEPTION: post-redteam-engine-state-scheduler-reduction-2026-04-30` authorizes only the self-validating control-surface files staged with this implementation: `.claude/skills/wave/SKILL.md`, `mu/tools/agents/meta_bridge_supervisor.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_commit_executor_receipt.py`, and `mu/tests/tools/test_recovery_gate.py`.
- Rationale: these files are the Phase B/L4 validation and commit-path package surfaces that classify, package, or locally test this same wave. The exception is limited to passing wave identity into the L4 contract gate, preserving staged commit-bound package truth, excluding non-Python fixtures from Phase B pytest file selection, making protected-branch dirty-worktree stashing recoverable and fail-closed, and suppressing founder override tokens from structural supervisor packages.
- Boundary: this exception does not authorize runtime/seed semantics outside F-1/F-2, PR automation, executor dispatch behavior outside the named self-validating surfaces, bridge/supervisor behavior beyond the package-validation gate and structural package-token schema fix, or any F-3/F-4 work.

## 2. Work Items

### WI-1: Open with code-truth checks for F-1/F-2

Before implementing, verify whether the missing artifacts named by TASKS.md and F-1/F-2 are still absent:

```bash
ls mu/programs/rcx_engine_state* mu/substrate/engine_state* 2>/dev/null
ls mu/programs/rcx_engine_scheduler* mu/programs/rcx_engine_supervisor* 2>/dev/null
```

If these commands prove that the engine-state or scheduler artifacts have already landed, remove that item from pending work and stop for a narrower replan instead of re-listing stale work as unresolved.

### WI-2: Add the formal engine-state artifact

Create `mu/programs/rcx_engine_state.v1.json` as the smallest loadable structural artifact for the PDF kernel state model cited by F-1:

- graph state `G=(V,E)`
- bookkeeping maps `Omega`, `Lambda`, and `Xi`
- rank `rho`
- `NextID(G)`
- validation projections for shape, identity stability, and monotone ID allocation

Do not move this model into Python-only or JS-only host logic. If a `mu/substrate/engine_state*` placement is required instead of `mu/programs/`, stop and replan before writing a second artifact family.

### WI-3: Add the scheduler/operator-pool artifact

Create `mu/programs/rcx_engine_scheduler.v1.json` as the smallest loadable scheduler artifact for the PDF scheduler model cited by F-2:

- `seedOps`
- Godel-coded unary maps for scheduler operators
- finite operator pool per step
- strict lexicographic operator ordering, not a generic deterministic sort
- identity-map safeguard
- promotion/freeze lifecycle hooks that align with the existing exhaustion seed semantics

Do not create `mu/programs/rcx_engine_supervisor.v1.json` in this slice. If a supervisor seed proves necessary before a scheduler seed can be honest, stop and replan.

### WI-4: Wire scheduler entry through the existing boundary only

Use the existing `run_algorithm` chokepoint as the scheduler-entry boundary. The only permitted host changes are parity-preserving allowlist/dispatch wiring in:

- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/js/engine/pipeline.js`

No new boundary operation, host scheduler loop, Python-only scheduling branch, or JS-only scheduling branch is in scope.

### WI-5: Add structural fixtures and tests

Add fixtures and tests that prove the state and scheduler artifacts are executable structural artifacts rather than doc-only JSON:

- state fixture covers minimal graph, bookkeeping maps, rank, and next-id behavior
- scheduler fixture covers at least two Godel-coded unary-map operators, strict lexicographic ordering, identity safeguard, promotion, and freeze handling
- negative structural test rejects invalid state shape, non-Godel-coded scheduler operators, or non-lexicographic scheduler ordering
- parity test proves Python and JS agree on the scheduler seed-path result
- tests prove the scheduler path runs through the seed path, not a host fallback

### WI-6: Validate and record implementation evidence

The implementation pass must run these commands after the new tests/files exist:

```bash
PYTHONHASHSEED=0 python3 -m pytest \
  mu/tests/structural/test_rcx_engine_state_seed.py \
  mu/tests/structural/test_rcx_enginenew_scheduler.py \
  tests/parity/test_rcx_engine_scheduler_parity.py \
  tests/parity/test_rcx_engine_parity.py \
  tests/parity/test_rcx_engine_workload_contract_parity.py \
  -q
node mu/host/js/eval_step.js
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_bootstrap_purity_ratchet.py
```

Record command output in the implementation closeout. Do not expand this packet into terminal-semantics or workload-corpus work to make unrelated checks green.

## 3. Constraints

This packet is intentionally narrow. The following are not in scope:

- F-3 terminal semantics work: no `terminal_classify` projections for `hash_error`, `globalstall`, or restart semantics.
- F-4 workload corpus work: no new workload vectors, negative-control corpus, ablation/removal suite, or given-for-free ledger.
- No broad Phase C bundle beyond the F-1/F-2 engine-state/scheduler reduction.
- No default runtime flip.
- No host-power widening. The only allowed host change is admitting the new scheduler seed through the existing parity-preserving `run_algorithm` boundary.
- No new Python-only or JS-only semantics.
- No new control-surface automation, executor behavior, commit workflow changes, or bridge/supervisor changes outside the wave-bound `BOOTSTRAP_PHASE_B_EXCEPTION: post-redteam-engine-state-scheduler-reduction-2026-04-30`.
- No docs-only closure. JSON artifacts must be loadable and covered by tests.
- No edits outside the files/directories listed in Scope unless a stop condition triggers and a new packet is written.

## 4. Stop Conditions

Stop the implementation pass and return for replan if any condition is met:

1. Opening code-truth checks show `rcx_engine_state*` or `rcx_engine_scheduler*` has already landed.
2. A required change falls outside the scoped files/directories.
3. The state model cannot be represented as a loadable structural artifact without adding host-only semantics.
4. The scheduler cannot execute through the existing `run_algorithm` boundary without adding a new host boundary operation.
5. Python and JS require different scheduler semantics.
6. F-3 terminal semantics or F-4 workload corpus work becomes a prerequisite for F-1/F-2 tests to pass.
7. Host authority inventory, host semantics ratchet, bootstrap purity ratchet, JS parity, or engine-scoped parity fails for reasons introduced by this slice.
8. The implementation needs `rcx_engine_supervisor.v1.json` before `rcx_engine_scheduler.v1.json` can be honest.

## 5. Acceptance Criteria

This packet is ready for implementation when bridge review accepts it as a concrete Phase A plan.

The future implementation is acceptable only when all of the following are true:

- `mu/programs/rcx_engine_state.v1.json` exists and encodes the F-1 state model as loadable structural projections.
- `mu/programs/rcx_engine_scheduler.v1.json` exists and encodes the F-2 scheduler/operator-pool model as loadable structural projections: `seedOps`, Godel-coded unary maps, finite operator pool per step, strict lexicographic order, identity-map safeguard, and promotion/freeze lifecycle.
- The scheduler seed is admitted through the existing `run_algorithm` boundary in both Python and JS with parity-preserving allowlist/dispatch changes only.
- No new host scheduler semantics are introduced outside the existing boundary wiring.
- Structural fixtures and tests exist for engine state and scheduler behavior, including at least one negative structural case.
- Python/JS scheduler parity is tested.
- Existing engine parity tests still pass.
- Host authority inventory, host semantics ratchet, and bootstrap purity ratchet still pass.
- F-3 terminal semantics and F-4 workload corpus remain explicitly deferred and are not claimed as resolved by this slice.

## 6. Grounding / Authorization

TASKS.md authorization:

- `TASKS.md:364`: `[NEXT-CODEX-POST-REDTEAM]` is UNPARKED and founder-authorized as of 2026-03-28.
- `TASKS.md:365`: structural follow-on queue is `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- `TASKS.md:366`: sequence is Phase A -> Phase B -> Phase C -> Phase D.
- `TASKS.md:367`: current phase is OPEN; downstream structural reduction remains unimplemented.
- `TASKS.md:368`: current code truth says PR #701 landed findings/evidence only and did not land runtime/seed structural reductions; missing items include `rcx_engine_state`, scheduler structural tests/fixtures, workload contract metadata, and terminal-classify projections.
- `TASKS.md:369`: lane is structural post-control-surface.

Governing packet refs:

- This file is the governing Phase A packet for wave `post-redteam-engine-state-scheduler-reduction-2026-04-30`.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:3-6` marks the structural queue ACTIVE and points to the canonical locked Phase A sweep.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:38-70` defines the phase sequence: Phase A gap sweep, Phase B host/boundary unification, Phase C structural reduction into Mu.
- `reports/control_plane/next_codex_post_redteam_phase_a_structural_gap_swe_2026-03-30.md:588-620` records F-1 as a DEFECT: no engine-state schema artifact.
- `reports/control_plane/next_codex_post_redteam_phase_a_structural_gap_swe_2026-03-30.md:624-697` records F-2 as a DEFECT: no scheduler seed or operator-pool artifact; existing `run_algorithm` is a boundary but not scheduler semantics.
- `reports/control_plane/next_codex_post_redteam_phase_a_structural_gap_swe_2026-03-30.md:863-864` classifies F-1/F-2 as confirmed downstream structural-reduction work.

Authorization for automation:

- `Authorization: FOUNDER_OVERRIDE:post-redteam-engine-state-scheduler-reduction-2026-04-30`
- The override is wave-bound to this packet and does not authorize unrelated control-surface, executor, bridge, terminal-semantics, workload-corpus, or broad Phase C work. Structural commit/supervisor packages must not carry a non-empty founder override token.