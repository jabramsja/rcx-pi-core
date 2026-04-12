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
    # Only allow sqlite3 on the WORKTREE's own bridge.db, NOT the main repo's.
    # Resolve the main repo path and check if the sqlite3 target resolves there.
    MAIN_REPO=$(cd "$GIT_COMMON" 2>/dev/null && cd .. && pwd -P)
    MAIN_AGENT_BUS="$MAIN_REPO/.agent_bus"
    # Extract the db path argument from the sqlite3 command robustly.
    # sqlite3 may have flags before the filename (e.g. sqlite3 -readonly /path/db).
    # Strategy: pull all tokens after 'sqlite3', skip option flags (leading -),
    # take the first positional argument as the DB path.
    DB_ARG=""
    for _tok in $(echo "$CMD" | grep -oE 'sqlite3\s+.*' | sed 's/sqlite3\s\+//'); do
      case "$_tok" in
        -*) continue ;;  # skip option flags
        *)  DB_ARG="$_tok"; break ;;
      esac
    done
    if [ -z "$DB_ARG" ]; then
      exit 0  # No db path found — allow (non-file sqlite3 usage)
    fi
    RESOLVED_DB=$(cd "$(dirname "$DB_ARG" 2>/dev/null)" 2>/dev/null && echo "$(pwd -P)/$(basename "$DB_ARG")" || echo "$DB_ARG")
    if echo "$RESOLVED_DB" | grep -qF "$MAIN_AGENT_BUS"; then
      jq -n --arg reason "BLOCKED: sqlite3 targets the MAIN repo bridge.db ($MAIN_AGENT_BUS) from a linked worktree. Use MCP SQLite for main-repo inspection. Direct sqlite3 is only allowed on the worktree's own .agent_bus/." \
        '{"decision":"block","reason":$reason}'
      exit 0
    fi
    exit 0  # Allow sqlite3 on worktree's own bridge.db
  fi
  jq -n --arg reason "BLOCKED: Direct sqlite3 access to bridge.db is not allowed in the main repo. Use MCP SQLite (mcp__sqlite__read_query / mcp__sqlite__write_query) for all bridge.db inspection. Hard rule: ~/.claude/hard-rules.txt" \
    '{"decision":"block","reason":$reason}'
  exit 0
fi

# Allow everything else
exit 0
