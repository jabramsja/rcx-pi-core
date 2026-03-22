# Meta-Bridge Rollout Packet

Date: 2026-03-20
Status: active tracked control-plane packet
Purpose: give Claude and the founder one canonical tracked packet for the
current control-surface/meta-bridge rollout order

## Current operating truth

- the active lane remains hooks / agents / bridge control-surface work
- `META-BRIDGE-S1` (pre-commit supervisor) and `META-BRIDGE-S2` (post-merge
  supervisor) are both implemented and merged
- the immediate implementation target is `EXECUTOR-SURFACES` (rollout step 4):
  repo-local executor automation for Phase A, Phase B, commit, and dialectic
- pre-existing hook/validator findings remain queued background truth

## Seeded test corpus

Use the existing control-surface package as the first supervisor test input:

- `.scratch/hook_hardening_precommit_package.json`
- `.scratch/hook_hardening_precommit_package.md`

This corpus exists to test:

1. pre-commit supervisor ingestion and decision routing
2. tracked control-plane packet usage instead of memory-only narration
3. future Phase A / Phase B / commit executor handoff
4. post-merge supervisor handoff once that slice exists

## North-star invariants

These invariants are mandatory for every supervisor, executor, prompt, and doc
touch in this lane:

- meta-circular, self-hosting, and program-in-Mu remain the destination
- Python and JS are bootstrap substrates, not the semantic destination
- do not widen host semantics for workflow convenience
- first unify residual host/boundary semantics into a small explicit bootstrap
  surface
- then remove dead code and scattered host residue after that unification
- only then reduce the unified bootstrap into Mu

## Canonical rollout order

1. ~~Implement~~ `META-BRIDGE-S1` as the standing pre-commit supervisor **(done — merged PRs #641-#644)**.
   ~~Verify with seeded hook-hardening package~~ **(done 2026-03-21)**.
   Live Codex routing confirmed working: `NEEDS_PHASE_B` returned on stale package,
   no supervisor defects. Routing fix (PR #653) confirmed: failed-validation packages
   reach Codex, commit-capable decisions blocked, routing decisions pass through.
2. **Standing invariant:** Keep the pre-commit supervisor as the standing gate before any commit flow. *(not a discrete wave — verified continuously)*
3. ~~Design and implement the post-merge supervisor follow-on~~ **(done — PR #657 merged)**.
   Tracked packet: `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md`.
4. ~~Introduce real repo-local executors~~ **(done — PRs #659-#661)**.
   All 4 executors implemented: commit_executor, phase_b_executor, phase_a_executor, dialectic_executor.
   Dispatcher + config foundation in place. `/wave` skill updated to dispatch to executors.
   Tracked packet: `reports/control_plane/executor_surfaces_plan_2026-03-22.md`.
5. **Active next step:** Transition period — validate executors in production use,
   allow `/wave`, `/bridge`, `/checkpoint`, hook scripts, and `merge_pr.sh` as
   explicit fallback surfaces until executors are proven.
6. Reduce Claude memory to a pointer layer only after executors are proven in production.
7. Resume the parked structural queue only after steps 1-6 are in place.

## Required Claude behavior

- read this packet and `TASKS.md` before acting on the current control-plane
  lane
- treat this packet, not `.scratch/` and not ignored `reports/codex/` paths, as
  the canonical control-plane reference
- keep `TASKS.md` updated as slice/state transitions land
- update external Claude memory only after the real control-plane surfaces
  exist; memory remains Claude-owned
- preserve the pre-commit supervisor as a standing gate even after the
  post-merge supervisor is added

## Implementation status

- `META-BRIDGE-S1` **implemented and merged** (PRs #641-#644):
  `mu/tools/agents/meta_bridge_supervisor.py` + `mu/tools/agents/templates/meta_bridge_task.txt`
- **Seeded-package verification: complete** (2026-03-21). Live Codex routing confirmed.
- **Standing invariant:** pre-commit supervisor remains standing gate for commit flows
- **META-BRIDGE-S2:** post-merge supervisor Slice 1 **implemented and merged** (PR #657).
  Tracked packet: `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md`.
- All executor surfaces implemented (PRs #659-#661): dispatcher, commit_executor,
  phase_b_executor, phase_a_executor, dialectic_executor
- `/wave` skill updated to dispatch to executors
- Claude memory still duplicates protocol truth

## Advisory source packets

These remain useful working/advisory sources, but they are no longer the
canonical packet for `TASKS.md` to point at:

- `reports/codex/repo_audits/drift_2026-03-20_codex_redteam_phase_queue.md`
- `reports/codex/tooling/tooling_2026-03-20_codex_meta_bridge_supervisor_plan.md`
- `.scratch/meta_bridge_supervisor_slice1_plan.md`
