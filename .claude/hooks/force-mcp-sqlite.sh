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
  # Allow sqlite3 in linked worktrees (MCP SQLite may not be configured there).
  # The hard rule "ALWAYS use MCP SQLite" applies to the MAIN repo only.
  GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || true)
  GIT_COMMON=$(git rev-parse --git-common-dir 2>/dev/null || true)
  IS_LINKED=false
  if [ -n "$GIT_DIR" ] && [ -n "$GIT_COMMON" ]; then
    RESOLVED_DIR=$(cd "$GIT_DIR" 2>/dev/null && pwd -P)
    RESOLVED_COMMON=$(cd "$GIT_COMMON" 2>/dev/null && pwd -P)
    [ "$RESOLVED_DIR" != "$RESOLVED_COMMON" ] && IS_LINKED=true
  fi
  if [ "$IS_LINKED" = "true" ]; then
    exit 0  # Allow sqlite3 in linked worktrees
  fi
  jq -n --arg reason "BLOCKED: Direct sqlite3 access to bridge.db is not allowed in the main repo. Use MCP SQLite (mcp__sqlite__read_query / mcp__sqlite__write_query) for all bridge.db inspection. Hard rule: ~/.claude/hard-rules.txt" \
    '{"decision":"block","reason":$reason}'
  exit 0
fi

# Allow everything else
exit 0
