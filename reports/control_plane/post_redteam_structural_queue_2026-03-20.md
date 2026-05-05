# Post-Red-Team Structural Queue

Date: 2026-03-20
Status: ACTIVE (unparked 2026-03-28, founder-authorized)
Phase-A-Lock: LOCKED
Canonical-Plan: reports/control_plane/next_codex_post_redteam_phase_a_structural_gap_swe_2026-03-30.md
Purpose: founder-directed structural sequence following the
control-surface/meta-bridge rollout (all 7 rollout steps complete)

## Current truth

- Queue UNPARKED (2026-03-28). All parking conditions satisfied:
  - the pre-commit supervisor is live as the standing commit gate ✓
  - the post-merge supervisor has gone through its own Phase A and Phase B ✓
  - Claude has explicit repo-local executors for Phase A, Phase B, and commit flow ✓
  - pipeline proven end-to-end (9 PRs, #673-#681) ✓
- Current phase: OPEN only for future bounded structural-reduction packets not
  already proven by landed work. The `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]`
  entry records that PR #701 landed the Phase A structural gap sweep
  packet/evidence artifacts and that the first downstream
  `post-redteam-engine-state-scheduler-reduction-2026-04-30` slice has also
  landed.
- Canonical historical Phase A sweep packet:
  `reports/control_plane/next_codex_post_redteam_phase_a_structural_gap_swe_2026-03-30.md`
  (bridge-converged findings/evidence record). Do not read its old F-1/F-2
  "missing artifact" findings as current unresolved work after the `TASKS.md`
  `[NEXT-CODEX-POST-REDTEAM]` entry records the engine-state/scheduler slice as
  landed.
- Old control-surface packets that reused `[NEXT-CODEX-POST-REDTEAM]` as a
  procedural Gate 8 anchor are not substantive closure evidence for this
  structural queue.

## Immediate pre-production gates

1. `deferred-findings-fix-sweep-2026-05-04`
   (`reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`)
   runs first and is the current Phase B cleanup packet. It fixes or routes blocker/non-blocker findings in
   `reports/deferred/blocking/`, `reports/deferred/non_blocking/`,
   `reports/l4_wave_indicators/`, and `reports/control_plane/`. Stale or
   code-closed findings must be checked against current code/tests/command
   evidence, then moved to the appropriate archive or resolved lane instead of
   remaining in active finding folders.
2. `mu-preproduction-redteam-2026-05-04`
   (`reports/control_plane/mu_preproduction_redteam_2026-05-04.md`) runs after
   the deferred findings sweep lands. It red-teams all production-relevant `/mu` code
   and proof surfaces: Python, JavaScript, Stage0/lowering/runtime paths,
   seeds/registries, tests, tooling, and docs. Blockers route to
   `reports/deferred/blocking/`; non-blockers route to
   `reports/deferred/non_blocking/`.

Production-forward movement is blocked until both gates are complete or any
remaining findings are explicitly routed with evidence and founder-visible
status.

## Governing sequence

1. finish the control-surface/meta-bridge lane honestly
2. run a code/runtime structural gap phase on Mu / Stage0 / runtime surfaces
3. unify remaining host and boundary semantics into a narrow set of explicit
   checkpoints
4. then reduce both:
   - the explicit host/boundary chokepoints
   - any host semantics still hiding inside Stage0 / Mu that should already
     have been structuralized

The governing idea is:

- first make the remaining host power legible
- then shrink it
- keep semantic meaning moving toward Mu / meta-circular / self-hosting truth,
  not toward a smarter host

## Phase sequence

### Phase A. Code/runtime structural gap sweep

Goal:

- find and fix real Mu / Stage0 / runtime structure gaps, behavioral errors,
  proof gaps, and hidden host-side drift beyond the control-surface lane

Primary supporting packets:

- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_full_spec_gap_map.md`
- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_seed_implementation_packet_v0.md`

### Phase B. Host/boundary unification

Goal:

- compress remaining host and boundary semantics into a small, explicit set of
  chokepoints so the residual bootstrap surface is honest and reviewable

Primary supporting packets:

- `reports/codex/self_hosting/vector_2026-03-11_p7_host_semantics_reduction_plan.md`
- `reports/codex/meta_circular/vector_2026-03-12_structuralization_research_bootstrap_surface.md`
- `reports/codex/meta_circular/vector_2026-03-12_stage0_vm_execution_contract_v0.md`

### Phase C. Structural reduction into Mu

Goal:

- reduce the narrowed host surface into Mu where the reduction is honest,
  parity-preserving, and production-justified

Primary supporting packets:

- `reports/codex/self_hosting/vector_2026-03-11_p7_host_semantics_reduction_plan.md`
- `reports/codex/self_hosting/vector_2026-03-12_evaluator_self_regeneration_contract_v0.md`
- `reports/codex/self_hosting/vector_2026-03-12_self_hosting_cutover_proof_plan_v0.md`

### Phase D. Interior host-semantics sweep

Goal:

- inspect Stage0 / Mu internals for host semantics that still live "inside" the
  substrate or kernel where they should already have been structuralized

Primary supporting packets:

- `reports/codex/meta_circular/vector_2026-03-12_stage0_cutover_replacement_plan_v0.md`
- `reports/codex/meta_circular/vector_2026-03-12_stage0_microcode_v0.md`
- `reports/codex/meta_circular/vector_2026-03-12_source_vs_stage0_diff_harness_contract_v0.md`

## Operating notes

- before this queue resumes, Claude should be running:
  - the pre-commit supervisor before commit flow
  - the post-merge supervisor after merge
  - the real Phase A / Phase B / commit executors those supervisors point at
- keep the north-star order honest: unify host semantics first, remove dead code
  and scattered host residue after unification, then reduce the unified
  bootstrap into Mu
- when Phase A begins, treat new defects as red-team findings first, not as
  automatic implementation work
