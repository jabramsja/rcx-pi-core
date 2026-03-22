<!-- DOC_STATUS: REFERENCE -->
<!-- DOC_ROLE: Historical archive of manual wave protocol before executor-based workflow -->

# Manual Wave Protocol (Archived 2026-03-22)

**Status:** ARCHIVED — Replaced by executor-based workflow (mu/tools/executors/)
**Reason:** Executors now own Phase A/B/commit orchestration. This file preserves
the manual protocol for historical reference.

---

## Wave Protocol (Two Phases)

### Phase A: Design + Agent Review + Bridge Convergence
1. Design the plan (scope, files, depth, focus)
2. Run `run_review.py` once on the plan (agent red-team of the design)
3. Send plan + agent findings to bridge (`--task-file plan.md --no-diff`) -> Codex red-teams
4. Fix blockers, defer non-blockers to `reports/deferred/`
5. Loop until bridge returns only non-blockers -> plan is locked

### Phase B: Agent Execution + Bridge Convergence
1. Implement the locked plan
2. Run `run_review.py` on implementation
3. Send agent findings + diff to bridge (bridge MUST see the diff)
4. Fix blockers, defer non-blockers
5. Loop until converged -> commit protocol runs automatically

### Commit Protocol (Autonomous after convergence)
1. Stage specific files (by name, never `git add .`)
1b. Run pre-commit supervisor: `python3 mu/tools/agents/meta_bridge_supervisor.py --package <path> --json`
2. `git commit` — pre-commit hook verifies supervisor receipt
3. `git push` — pre-push hook runs `audit_fast.sh`
4. `gh pr create` targeting `dev`
5. Wait for CI (`gh pr checks <PR#>`)
6. Read bot comments — fix real issues
7. `bash mu/tools/hooks/merge_pr.sh <PR#> --sweep`
8. Post-merge verify

### Anti-patterns (never repeat)
- Collapsing the loop — single pass is not convergence
- Bridge without diff — Codex needs actual code changes to red-team
- Skip bridge after agents — always send findings to bridge
- Jump to commit after tests pass — skipping agents AND bridge

### Critical Mistakes (from feedback_wave_discipline.md)
- Repeatedly saying "fix blockers, then commit" instead of looping through bridge
- Sending only agent findings without the code changes (bridge needs the diff)
- Skipping Phase B step 3 — going straight from agent findings to fixing
- Jumping to "Ready to commit?" after tests pass, skipping agent review AND bridge

### Bridge Bootstrap Protocol
Every bridge invocation MUST include instructions requiring Codex to:
1. Read `FOUNDER_SESSION_BOOTSTRAP.md` first
2. Confirm it read the file and summarize key points
3. Only THEN proceed with the assigned review/task

---

## XML Protocol Block (as it appeared in CLAUDE.md)

```xml
<wave_protocol>
  <phase_a name="Design + Agent Review + Bridge Convergence">
    <step_1>Design the plan (scope, files, depth, focus)</step_1>
    <step_2>Run run_review.py on plan (agent red-team of design)</step_2>
    <step_3>Send plan + agent findings to bridge (--no-diff) — Codex red-teams design</step_3>
    <step_4>Fix blockers, defer non-blockers to reports/deferred/</step_4>
    <step_5>Loop until bridge returns only non-blockers — plan is locked</step_5>
  </phase_a>
  <phase_b name="Implementation + Agent Review + Bridge Convergence">
    <step_1>Implement the locked plan</step_1>
    <step_2>Run run_review.py on implementation</step_2>
    <step_3>Send agent findings + diff to bridge — Codex red-teams implementation (bridge MUST see the diff)</step_3>
    <step_4>Fix blockers, defer non-blockers</step_4>
    <step_5>Loop until converged — only non-blockers remain</step_5>
  </phase_b>
  <commit_protocol name="After Convergence (Autonomous)">
    <step_1>Stage specific files (never git add .)</step_1>
    <step_1b>Run pre-commit supervisor: python3 mu/tools/agents/meta_bridge_supervisor.py --package <path> --json</step_1b>
    <step_2>git commit (pre-commit hook runs — verifies supervisor receipt)</step_2>
    <step_3>git push (pre-push hook runs audit_fast.sh)</step_3>
    <step_4>gh pr create targeting dev</step_4>
    <step_5>Wait for CI (gh pr checks)</step_5>
    <step_6>Read bot comments — fix real issues</step_6>
    <step_7>merge_pr.sh --sweep</step_7>
    <step_8>Post-merge verify</step_8>
  </commit_protocol>
  <bridge_bootstrap>Every bridge invocation MUST require Codex to read FOUNDER_SESSION_BOOTSTRAP.md first.</bridge_bootstrap>
  <anti_patterns>
    <never>Collapse the loop — single pass is not convergence</never>
    <never>Bridge without diff — Codex needs actual code changes to red-team</never>
    <never>Skip bridge after agents — always send findings to bridge</never>
    <never>Jump to commit after tests pass — skipping agents AND bridge</never>
  </anti_patterns>
</wave_protocol>
```
