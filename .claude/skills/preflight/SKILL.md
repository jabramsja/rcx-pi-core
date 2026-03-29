---
name: preflight
description: RCX Session Preflight Check
---

# /preflight — RCX Session Preflight Check

Run this at the START of every session. It reads canonical sources and reports current state.

## Steps

1. Read `STATUS.md` — extract current phase, debt counts (THRESHOLD, CURRENT, FLOOR), and testing tier status.

2. Read `TASKS.md` (first 200 lines) — identify active NEXT items, any promoted/demoted tasks since last session.

3. Run `./tools/checks/check_docs_consistency.sh` — validate STATUS.md matches reality. Report any failures.

4. Run `./tools/checks/check_agent_review_needed.sh` — check for uncommitted core changes needing agent review.

5. Run `python3 mu/tools/checks/check_host_semantics_ratchet.py` — verify host debt ratchet is clean.

6. Run `python3 tools/checks/check_host_authority_inventory_ratchet.py` — verify authority inventory ratchet.

7. Run `node mu/host/js/eval_step.js 2>&1 | tail -3` — verify JS substrate is healthy.

8. Check `git status` — report any uncommitted changes, untracked files in runtime dirs.

9. Check `git log --oneline -5` — show recent commits for context.

10. Clean stale bridge lock — if `.agent_bus/meta/meta_bridge.lock` exists and the PID is dead, remove it.

11. Start pipeline monitor — run `tools/observability/pipeline_monitor.sh start --detach` to launch the tmux dashboard in the background. If already running, skip. Tell the user to open a second terminal and run `tmux attach-session -t rcx-pipeline` to see the live dashboard.

12. Check dream staleness — read `~/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory/.last_dream`. If missing or older than 24 hours, run `/dream` before starting work.

## Output Format

Produce a concise summary:
```
PREFLIGHT COMPLETE
Phase: <phase>
Debt: <CURRENT>/<THRESHOLD> (tracked markers)
Authority: <current>/<baseline> (inventory)
Active NEXT: <list items>
Ratchets: <pass/fail>
JS Parity: <pass/fail>
Uncommitted: <count files> / Agent review needed: <yes/no>
Bridge lock: <clean/stale-cleared>
Monitor: <started/already running>
Dream: <fresh (Nh ago) / STALE — running /dream>
Recent: <last 3 commits one-line>
```

Flag any issues that need attention before starting work.

**ALWAYS** end preflight output with the tmux attach command for the user to copy-paste, regardless of whether the monitor was just started or was already running:

```
Pipeline monitor: tmux attach-session -t rcx-pipeline
```
