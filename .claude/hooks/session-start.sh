#!/bin/bash
# session-start.sh — SessionStart
#
# Writes the current Claude Code session id to
# $CLAUDE_PROJECT_DIR/.agent_bus/observability/orchestrator_session_id
# so that mu/tools/observability/pipeline_agent_pager.py
# _read_orchestrator_session_id() (at :656-693) can later resolve it for
# `claude --resume <id>` deterministic dispatch.
#
# DEDICATED-MONITOR leg: when RCX_CLAUDE_MONITOR=1, this same session id is
# instead written to the SIBLING claude_monitor_session_id file -- the dedicated
# Claude monitor conversation that the pager's _read_claude_monitor_session_id()
# resumes (NEVER the live orchestrator session). A dedicated monitor sets that
# env var so its own SessionStart lands the id the pager's claude leg requires;
# without the var the live-orchestrator behavior above is unchanged.
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
# Pipeline-owned SUB-sessions (bridge_adapters.py sets RCX_PIPELINE_SESSION=1 for
# every adapter invocation) must NOT clobber the live orchestrator_session_id
# with a transient sub-session id -- so the orchestrator writer leg stays
# suppressed for them. But the DEDICATED-MONITOR writer leg (RCX_CLAUDE_MONITOR=1)
# targets a DISTINCT file (claude_monitor_session_id) and MUST still fire even
# inside a pipeline-owned monitor session; otherwise the pager's claude leg has
# no --resume target. So suppress ONLY the orchestrator leg here, and let a
# dedicated-monitor session fall through to its writer below.
if [ "${RCX_PIPELINE_SESSION:-}" = "1" ] && [ "${RCX_CLAUDE_MONITOR:-}" != "1" ]; then
  exit 0
fi

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
# Dedicated Claude monitor sessions set RCX_CLAUDE_MONITOR=1 so their session id
# lands in the DISTINCT claude_monitor_session_id file (the pager's
# _read_claude_monitor_session_id resume target), never the live
# orchestrator_session_id. Any other session keeps the orchestrator behavior.
if [ "${RCX_CLAUDE_MONITOR:-}" = "1" ]; then
  TARGET_FILE="$TARGET_DIR/claude_monitor_session_id"
else
  TARGET_FILE="$TARGET_DIR/orchestrator_session_id"
fi

mkdir -p "$TARGET_DIR" 2>/dev/null || exit 0

if printf '%s\n' "$SESSION_ID" > "$TARGET_FILE.tmp" 2>/dev/null; then
  mv -f "$TARGET_FILE.tmp" "$TARGET_FILE" 2>/dev/null || rm -f "$TARGET_FILE.tmp" 2>/dev/null
fi

exit 0
