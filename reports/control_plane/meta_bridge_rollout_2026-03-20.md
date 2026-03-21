# Meta-Bridge Rollout Packet

Date: 2026-03-20
Status: active tracked control-plane packet
Purpose: give Claude and the founder one canonical tracked packet for the
current control-surface/meta-bridge rollout order

## Current operating truth

- the active lane remains hooks / agents / bridge control-surface work
- the immediate implementation target is `META-BRIDGE-S1`, not broad
  remediation of every historical hook/control-surface finding
- the previously produced hook-hardening/control-surface summary package is the
  seeded corpus currently being used to exercise the pre-commit supervisor
- pre-existing hook/validator findings remain queued background truth and must
  not be forgotten, but they are not the immediate implementation target

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

1. Implement and test `META-BRIDGE-S1` as the standing pre-commit supervisor,
   using the seeded hook-hardening package first.
2. Keep the pre-commit supervisor as the standing gate before any commit flow.
3. Design and implement the post-merge supervisor follow-on.
4. Introduce real repo-local executors for:
   - Phase A
   - Phase B
   - commit / merge flow
5. During transition only, allow `/wave`, `/bridge`, `/checkpoint`, hook
   scripts, and `merge_pr.sh` as explicit fallback surfaces.
6. Reduce Claude memory to a pointer layer only after the tracked packets and
   repo-local executors exist.
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

- `META-BRIDGE-S1` in Phase B review (`mu/tools/agents/meta_bridge_supervisor.py` + template)
- the post-merge supervisor is not implemented yet
- real repo-local executors for Phase A / Phase B / commit do not exist yet
- Claude memory still duplicates protocol truth

## Advisory source packets

These remain useful working/advisory sources, but they are no longer the
canonical packet for `TASKS.md` to point at:

- `reports/codex/repo_audits/drift_2026-03-20_codex_redteam_phase_queue.md`
- `reports/codex/tooling/tooling_2026-03-20_codex_meta_bridge_supervisor_plan.md`
- `.scratch/meta_bridge_supervisor_slice1_plan.md`
