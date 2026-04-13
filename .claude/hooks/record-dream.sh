#!/bin/bash
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
# Claude Code PostToolUse hook: record timestamp when /dream skill completes.
# Matcher: Skill (fires after any skill invocation)
# Best-effort: never blocks, never fails the tool call.

INPUT=$(cat)

# Extract the skill name from tool_input
SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null) || true

# Only act on dream skill invocations
if [ "$SKILL" = "dream" ]; then
  MEMORY_DIR="$HOME/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory"
  mkdir -p "$MEMORY_DIR" 2>/dev/null || true
  # Write YYYY-MM-DD (human-readable canonical format, matches /dream SKILL.md Phase 4).
  # should-dream.sh parses this format and also supports legacy epoch-seconds for backward compat.
  date +%Y-%m-%d > "$MEMORY_DIR/.last_dream" 2>/dev/null || true
fi

# Never block — just record
exit 0
