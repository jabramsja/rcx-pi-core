---
name: wave
description: RCX Wave Protocol Executor
---

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
4. **Fix blockers** from bridge. NEVER demote blockers to non-blockers. Only TRUE non-blockers go to `reports/deferred/non_blocking/`.
5. **Loop steps 3-4** until bridge returns only non-blockers.
6. Report: "Phase A converged. Plan locked. Ready for Phase B."

## Phase B: Implementation + Agent Review + Bridge Convergence

### `/wave implement`
1. **Implement** the locked plan.
2. **Run `/audit fast`** — MANDATORY after implementation, before agents.
3. **Run agents** on the implementation: `python tools/runners/run_review.py --pr --depth full --output .scratch/<name>_phase_b_review.md`
4. **If JS or Python runtime files changed**: Run `/parity` — MANDATORY.
5. **If debt markers changed**: Run `/audit ratchets` — MANDATORY.
6. **Send to bridge** (implementation review, WITH diff): `/bridge review "<summary>"`
7. **Fix ALL findings** from bridge. Blockers → fix inline. Non-blockers → `reports/deferred/non_blocking/`. NEVER demote blockers.
8. **Loop steps 2-7** until bridge returns GO.
9. **Run `/checkpoint`** — verify no skipped skills, no deflection.
10. **Commit protocol** runs automatically (no ask needed in wave context).

## After Convergence: Commit Protocol

Per `user_founder_preferences.md`, wave convergence triggers the autonomous commit protocol:
1. Stage specific files → commit (pre-commit hook) → push (pre-push hook) → PR → CI → merge_pr.sh --sweep
2. If L4 wave: Run `/tracker` before commit.

## Critical Rules (NEVER VIOLATE)
- **Never collapse the loop**: The commit ONLY happens after the bridge loop converges. A single pass is NOT convergence.
- **Bridge sees the diff**: Always include code changes for Phase B, not just agent summaries.
- **Bridge bootstrap**: Every bridge invocation must instruct Codex to read FOUNDER_SESSION_BOOTSTRAP.md first.
- **Both are red-teamers**: Claude and bridge are both active adversaries, not just executing.
- **Fix ALL findings**: Don't defer blockers. Don't demote blockers to non-blockers. Fix them.
- **Auto-invoke skills**: `/audit fast` after implementation, `/parity` after runtime changes, `/audit ratchets` after debt changes, `/tracker` for L4 waves, `/checkpoint` before commit.

## Wave Status

### `/wave status`
Report:
- Current wave name
- Current phase (A or B)
- Bridge round number
- Blocker count from last bridge response
- Non-blocker count
- Convergence status (converged / N blockers remaining)
- Skills run: /audit, /parity, /debt, /tracker (ran/skipped/N/A)
