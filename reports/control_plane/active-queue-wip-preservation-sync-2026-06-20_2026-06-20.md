# Active Queue WIP Preservation Sync 2026-06-20

Date: 2026-06-20
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: active-queue-wip-preservation-sync-2026-06-20
Phase-A-Lock: UNLOCKED
Purpose: Refresh the visible autonomous TASKS.md queue after PR #1129, PR #1130, and PR #1131 landed, and make WIP preservation, dirty-worktree recovery, Stage0 blocked reduction, StructuralNumbers next steps, and easy-switch propagation explicit queued work rather than session memory.

## Scope

Docs/control-plane queue cleanup only. Update TASKS.md and STATUS.md so current work, preserved WIP, and discovered pipeline follow-ups are visible and ordered. Do not touch runtime, substrate, Stage0 implementation code, StructuralNumbers implementation tests, role/pager code, autoping, tmux scripts, or dirty WIP worktrees in this wave.

Files and surfaces in scope:

- TASKS.md (MODIFY) -- refresh the NOW active Codex autonomous queue with completed StructuralNumbers rationals, Stage 4 design as current next, WIP preservation, Stage0 contradiction recovery, easy-switch propagation, and pipeline fix backlog.
- STATUS.md (MODIFY) -- update the last-updated / next-milestone pointer to this queue packet while leaving Phase 8c and debt-count truth unchanged.
- reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_wave_config.json (NEW) -- launcher config for this docs/control-plane cleanup.
- reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_2026-06-20.md (GENERATED) -- launcher-created control packet.
- reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json (GENERATED) -- same-wave L4 indicator artifact.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `active-queue-wip-preservation-sync-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Ground completed work in direct merge evidence: PR #1129 structural-numbers-rationals, PR #1130 phase-b blocking convergence hardening, and PR #1131 primary ff-sync tracked-WIP preservation.
2. Move STRUCTURAL-NUMBERS-RATIONALS-2026-06-19 from remaining work to completed queue work and set STRUCTURAL-NUMBERS-STAGE4-DESIGN-2026-06-19 as CURRENT NEXT.
3. Add explicit queued WIP-preservation work: preserve main dirty worktree, lane1 Stage0 staged work, lane3 observability work, stash contents, and the local preservation snapshot path before any rebase/sync/cleanup.
4. Add explicit queued Stage0 recovery work: resolve the n3-stage0-content-addressed-mu-typedispatch Phase A contradiction before committing or rebasing its staged implementation.
5. Add explicit queued easy-switch hardening: propagate orchestrator/implementer/reviewer/pager/autoping/tmux switch state through launch_wave, routing, Phase B handoff, commit_executor, and dashboards instead of relying on process env.
6. Preserve the remaining pipeline fix order and parallelization rule, including that StructuralNumbers gate waves are sequential while non-overlapping pipeline fixes may use parallel waves.

## Constraints

- Use launch_wave.py for packet/tracker setup.
- Do not edit or normalize dirty WIP worktrees in this docs sync wave.
- Do not commit, stash, rebase, reset, or clean the Stage0 lane from this wave.
- Do not touch runtime, substrate, seed, scheduler, registry, projection, Stage0 implementation, StructuralNumbers implementation tests, role agent config, pager route code, autoping watcher code, or tmux scripts.
- Do not claim Stage0 or dirty-worktree recovery is complete; this wave only makes the queued work visible and preservation-bound.
- Do not launch the Stage 4, Stage0 recovery, or easy-switch implementation waves from inside this docs cleanup wave.

## Stop conditions

- Stop done when TASKS.md and STATUS.md agree on the refreshed queue, docs consistency and focused docs tests pass, strict staged L4 validation passes, the indicator artifact is collected, and follow-up implementation waves remain queued.
- Halt as DOC_ACCURACY if direct git evidence does not prove PR #1129, PR #1130, and PR #1131 are merged on the branch being updated.
- Halt as WIP_RISK if the edit requires mutating dirty WIP lanes or reordering Stage0 staged files.
- Do not commit without a real tracked source artifact and gate-green evidence.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id active-queue-wip-preservation-sync-2026-06-20 --output reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`

## Acceptance criteria

- TASKS.md marks STRUCTURAL-NUMBERS-RATIONALS-2026-06-19 as landed and names STRUCTURAL-NUMBERS-STAGE4-DESIGN-2026-06-19 as CURRENT NEXT.
- TASKS.md explicitly lists WIP preservation / dirty-worktree recovery, Stage0 blocked reduction decision/recovery, easy-switch propagation, and pipeline fix backlog as remaining work.
- TASKS.md preserves the StructuralNumbers sequential rule and conditional parallel-pipeline rule.
- STATUS.md references this refreshed queue and packet while leaving Phase 8c/debt truth unchanged.
- No runtime/substrate/seed/parity files are touched.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `active-queue-wip-preservation-sync-2026-06-20`.
- Governing packet: this file, `reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `active-queue-wip-preservation-sync-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder-directed request on 2026-06-20: put WIP issues, Stage0 reduction, StructuralNumbers progress, commit/dirty-worktree fixes, and future easy-switch hardening in TASKS.md so the autonomous queue remains explicit.

FOUNDER_OVERRIDE:active-queue-wip-preservation-sync-2026-06-20 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id active-queue-wip-preservation-sync-2026-06-20 --output reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id active-queue-wip-preservation-sync-2026-06-20 --output reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`.
- `evidence_delta`: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) No wave-owned pytest module was staged in this ad hoc handoff, so indicator collection is the mechanical evidence surface. (3) Indicator artifact binds the wave to reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: active-queue-wip-preservation-sync-2026-06-20 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `active-queue-wip-preservation-sync-2026-06-20`
- Active packet: `reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7429cb415a60acfb2229306175a3aebda0bf7a2887fe62d3dcec5fffd7f19f89`
- Indicator artifact: `reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id active-queue-wip-preservation-sync-2026-06-20 --output reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) No wave-owned pytest module was staged in this ad hoc handoff, so indicator collection is the mechanical evidence surface. (3) Indicator artifact binds the wave to reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`
- Current staged files:
  - `STATUS.md`
  - `TASKS.md`
  - `reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_2026-06-20.md`
  - `reports/control_plane/active-queue-wip-preservation-sync-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/active-queue-wip-preservation-sync-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
