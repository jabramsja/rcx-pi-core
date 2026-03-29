# Phase A → Phase B Transition Gap

**Date:** 2026-03-28
**Status:** FIXED (2026-03-29, Option A: Phase A checkpoint commit)
**Source:** Live pipeline run attempting full Phase A → Phase B → commit flow
**Lane:** hooks/agents/bridge control-surface

## Problem

The pipeline assumes a merge between Phase A and Phase B. Phase A locks
a plan locally, but the pre-commit supervisor in Phase B requires the locked
plan to be in merged/tracked state. Since the commit executor is downstream
of Phase B, the locked plan can't be committed until Phase B produces a
handoff — chicken-and-egg.

## Observed Behavior

1. Post-merge supervisor routes ROUTE_PHASE_A
2. Phase A executor creates + locks plan locally (converges in 1 round)
3. Post-merge supervisor (re-run) won't route ROUTE_PHASE_B because the
   locked plan is local-only, not merged
4. Phase B with --bootstrap-exception runs implementer + bridge GO, but
   pre-commit supervisor rejects because the tracked plan file still says
   Phase-A-Lock: UNLOCKED

## Impact

Every normal (non-BOOTSTRAP_PHASE_B_EXCEPTION) Phase B path is blocked
when it follows a Phase A that hasn't been separately committed.

## Proposed Fix Options

1. **Phase A checkpoint commit:** Phase A executor auto-commits the locked
   plan as a standalone commit before Phase B starts. Minimal scope —
   just the plan file.

2. **Supervisor accepts local Phase A locks:** The pre-commit supervisor
   checks the local filesystem for the locked plan, not just git-tracked
   state. Requires a new validation mode.

3. **Inline Phase A into Phase B:** Phase B executor runs Phase A internally
   if the plan is UNLOCKED, locks it, then proceeds. Single-pass flow.

## Relationship to Existing Work

- Blocks: any normal Phase B wave following Phase A
- Does not block: BOOTSTRAP_PHASE_B_EXCEPTION waves (executor surface work)
- Related: commit_pipeline_automation_plan_2026-03-22.md (original pipeline design)
