# /bridge — RCX Bridge Review Shorthand

Wraps bridge_supervisor.py with the bootstrap protocol baked in. Codex MUST read FOUNDER_SESSION_BOOTSTRAP.md before reviewing.

## Usage
- `/bridge review <summary>` — review mode with diff (implementation review)
- `/bridge design <file>` — no-diff deliberation (design review)
- `/bridge plan <file>` — Phase A plan review (no-diff)

## Steps

### `/bridge review <summary>`
1. Write a task file to `.scratch/bridge_task.md` that includes:
   - "REQUIRED BOOTSTRAP: Read FOUNDER_SESSION_BOOTSTRAP.md first, confirm, then proceed"
   - Context about what changed and why
   - What to red-team
   - Evidence commands already run
2. Run: `python3 tools/agents/bridge_supervisor.py review --task-file .scratch/bridge_task.md --summary "<summary>" --reviewer codex -v`
3. Parse the output for GO/NO_GO/REQUEST_CHANGES
4. If NO_GO: identify blockers, fix them, re-submit (this is the loop)
5. If REQUEST_CHANGES: fix non-blocking issues, re-submit
6. If GO: proceed to commit

### `/bridge design <file>`
Run: `python3 tools/agents/bridge_supervisor.py review --task-file <file> --summary "design review" --reviewer codex -v --no-diff`

### `/bridge plan <file>`
Same as design but for Phase A plan review.

## Critical Rules (from wave protocol memory)
- **Bridge MUST see the diff** for implementation reviews (not just a summary)
- **Never collapse the loop** — keep sending until only non-blockers remain
- **Both bridge and Claude are active red-teamers** — not just executing
- Every invocation MUST instruct Codex to read FOUNDER_SESSION_BOOTSTRAP.md first
