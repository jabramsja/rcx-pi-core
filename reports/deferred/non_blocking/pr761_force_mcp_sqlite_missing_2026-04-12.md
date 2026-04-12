# PR #761 P1: Missing force-mcp-sqlite.sh hook script

Date: 2026-04-12
PR: #761
Classification: BLOCKING (P1) — pipeline bot remediation actively attempting fix

## Finding
- **File:** `.claude/settings.json:25`
- **Issue:** Settings reference `.claude/hooks/force-mcp-sqlite.sh` but script does not exist in `.claude/hooks/`
- **Impact:** bridge.db enforcement hook silently fails (no sqlite3 restriction active)
- **Origin:** Reference exists on origin/dev HEAD (`2d90c53a`) prior to this commit — not introduced by this wave

## Required action
Create `.claude/hooks/force-mcp-sqlite.sh` that enforces MCP SQLite for bridge.db access per hard rule in `~/.claude/hard-rules.txt`. Pipeline Step 15 bot remediation is attempting this fix now. If remediation fails, P1→recovery path at `commit_executor.py:1622` routes to recovery gate.
