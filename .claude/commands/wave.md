# /wave — RCX Wave Protocol Executor

Executes the Phase A/B wave protocol. This is the core development workflow.

## Usage
- `/wave plan <name>` — Start Phase A: design + agent review + bridge convergence
- `/wave implement` — Start Phase B: implement locked plan + agent review + bridge convergence
- `/wave status` — Show current wave state

## Phase A: Design + Agent Review + Bridge Convergence

### `/wave plan <name>`
1. **Design** the plan: scope, files, depth, focus. Write to `.scratch/<name>_plan.md`.
2. **Run agents** on the plan: `python tools/runners/run_review.py --pr --depth quick --output .scratch/<name>_phase_a_review.md`
3. **Send to bridge** (plan review, no diff): `/bridge plan .scratch/<name>_plan.md`
4. **Fix blockers** from bridge. Defer non-blockers to `reports/deferred/<name>_nonblockers.md`.
5. **Loop steps 3-4** until bridge returns only non-blockers.
6. Report: "Phase A converged. Plan locked. Ready for Phase B."

## Phase B: Implementation + Agent Review + Bridge Convergence

### `/wave implement`
1. **Implement** the locked plan.
2. **Run agents** on the implementation: `python tools/runners/run_review.py --pr --depth full --output .scratch/<name>_phase_b_review.md`
3. **Send to bridge** (implementation review, WITH diff): `/bridge review "<summary>"`
4. **Fix blockers** from bridge. Defer non-blockers.
5. **Loop steps 2-4** until bridge returns only non-blockers.
6. Report: "Phase B converged. Ready to commit."

## Critical Rules (NEVER VIOLATE)
- **Never collapse the loop**: The commit ONLY happens after the bridge loop converges (only non-blockers remain). A single pass is NOT convergence.
- **Bridge sees the diff**: Always include code changes for Phase B, not just agent summaries.
- **Bridge bootstrap**: Every bridge invocation must instruct Codex to read FOUNDER_SESSION_BOOTSTRAP.md first.
- **Both are red-teamers**: Claude and bridge are both active adversaries, not just executing.
- **Fix blockers inline**: Don't defer blockers. Fix them, re-send. Only non-blockers go to deferred.

## Wave Status

### `/wave status`
Report:
- Current wave name
- Current phase (A or B)
- Bridge round number
- Blocker count from last bridge response
- Non-blocker count
- Convergence status (converged / N blockers remaining)
