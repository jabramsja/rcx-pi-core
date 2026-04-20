#!/bin/bash
# session-start.sh — SessionStart
#
# Writes the current Claude Code session id to
# $CLAUDE_PROJECT_DIR/.agent_bus/observability/orchestrator_session_id
# so that mu/tools/observability/pipeline_agent_pager.py
# _read_orchestrator_session_id() (at :656-693) can later resolve it for
# `claude --resume <id>` deterministic dispatch.
#
# Input: JSON on stdin with fields
#   { "session_id": "<uuid>", "hook_event_name": "SessionStart",
#     "source": "startup|resume|clear|compact", ... }
#   (per https://code.claude.com/docs/en/hooks.md SessionStart section)
#
# The pager tolerates every absent/malformed case with None, so this hook
# fail-OPEN on any error — we never want to block session start because
# the pager wiring is not strictly required for session usability.
#
# Enabled on all SessionStart sources (startup, resume, clear, compact)
# because each case produces a new or refreshed session id that the pager
# should track for subsequent `--resume` dispatch.

set -u
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0

INPUT=$(cat 2>/dev/null || echo "")
if [ -z "$INPUT" ]; then
  exit 0
fi

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -z "$SESSION_ID" ]; then
  exit 0
fi

case "$SESSION_ID" in
  *[[:space:]]*) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
[ -z "$PROJECT_DIR" ] && exit 0

TARGET_DIR="$PROJECT_DIR/.agent_bus/observability"
TARGET_FILE="$TARGET_DIR/orchestrator_session_id"

mkdir -p "$TARGET_DIR" 2>/dev/null || exit 0

if printf '%s\n' "$SESSION_ID" > "$TARGET_FILE.tmp" 2>/dev/null; then
  mv -f "$TARGET_FILE.tmp" "$TARGET_FILE" 2>/dev/null || rm -f "$TARGET_FILE.tmp" 2>/dev/null
fi

exit 0
