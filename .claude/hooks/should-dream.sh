#!/bin/bash
# Claude Code Stop hook: check if memory consolidation (/dream) is overdue.
# Fires at conversation end. If 24+ hours since last dream, tells Claude to run /dream.
MEMORY_DIR="$HOME/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory"

# If memory dir doesn't exist, skip silently (non-standard checkout path)
if [ ! -d "$MEMORY_DIR" ]; then
  exit 0
fi
TIMESTAMP_FILE="$MEMORY_DIR/.last_dream"
DREAM_INTERVAL_SECONDS=86400  # 24 hours

# If no timestamp file, dream has never run — trigger it
if [ ! -f "$TIMESTAMP_FILE" ]; then
  jq -n '{
    "decision": "block",
    "reason": "Memory consolidation has never run. Run /dream before ending session."
  }'
  exit 0
fi

LAST_DREAM=$(cat "$TIMESTAMP_FILE" 2>/dev/null || echo "0")
NOW=$(date +%s)
ELAPSED=$(( NOW - LAST_DREAM ))

if [ "$ELAPSED" -ge "$DREAM_INTERVAL_SECONDS" ]; then
  HOURS=$(( ELAPSED / 3600 ))
  jq -n --arg hours "$HOURS" '{
    "decision": "block",
    "reason": ("Memory consolidation is overdue (" + $hours + "h since last /dream). Run /dream before ending session.")
  }'
else
  # Not overdue — allow stop
  exit 0
fi
