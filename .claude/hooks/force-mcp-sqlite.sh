#!/usr/bin/env bash
# force-mcp-sqlite.sh — PreToolUse:Bash hook
# Blocks direct sqlite3 CLI access to bridge.db.
# Hard rule: "ALWAYS use MCP SQLite for main repo bridge.db inspection."
#
# This hook fires on every Bash tool call. If the command references
# bridge.db with sqlite3 (not via MCP), it blocks with a JSON decision.

set -euo pipefail

# Read the tool input from stdin (Claude Code PreToolUse protocol)
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)

if [ -z "$CMD" ]; then
  exit 0  # Not a Bash call or no command — allow
fi

# Check for direct sqlite3 access to bridge.db
if echo "$CMD" | grep -qE 'sqlite3\s+.*bridge\.db|sqlite3\s+.*\.agent_bus'; then
  jq -n --arg reason "BLOCKED: Direct sqlite3 access to bridge.db is not allowed. Use MCP SQLite (mcp__sqlite__read_query / mcp__sqlite__write_query) for all bridge.db inspection. Hard rule: ~/.claude/hard-rules.txt" \
    '{"decision":"block","reason":$reason}'
  exit 0
fi

# Allow everything else
exit 0
