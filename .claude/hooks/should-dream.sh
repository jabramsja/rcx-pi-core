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

LAST_DREAM_RAW=$(cat "$TIMESTAMP_FILE" 2>/dev/null | tr -d '[:space:]')

# Support THREE formats:
#   1. YYYY-MM-DD                     — canonical per /dream SKILL.md Phase 4 (2026-04-10)
#   2. YYYY-MM-DDTHH:MM:SSZ (ISO 8601) — legacy from cross-session /dream runs that
#                                        freelanced a format (regression tracked in
#                                        .claude/rules/learning.md 2026-04-10)
#   3. all-digit epoch seconds        — legacy from older record-dream.sh writes
# Readers must be liberal; writers should stick to format #1 going forward.
if echo "$LAST_DREAM_RAW" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
  # BSD date on macOS: -jf parses with format, no date set
  LAST_DREAM_EPOCH=$(date -jf "%Y-%m-%d" "$LAST_DREAM_RAW" +%s 2>/dev/null)
  # GNU date fallback (Linux)
  if [ -z "$LAST_DREAM_EPOCH" ]; then
    LAST_DREAM_EPOCH=$(date -d "$LAST_DREAM_RAW" +%s 2>/dev/null || echo 0)
  fi
elif echo "$LAST_DREAM_RAW" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'; then
  # ISO 8601 UTC (legacy format from parallel worktree /dream runs)
  LAST_DREAM_EPOCH=$(TZ=UTC date -jf "%Y-%m-%dT%H:%M:%SZ" "$LAST_DREAM_RAW" +%s 2>/dev/null)
  if [ -z "$LAST_DREAM_EPOCH" ]; then
    LAST_DREAM_EPOCH=$(date -u -d "$LAST_DREAM_RAW" +%s 2>/dev/null || echo 0)
  fi
elif echo "$LAST_DREAM_RAW" | grep -qE '^[0-9]+$'; then
  LAST_DREAM_EPOCH="$LAST_DREAM_RAW"
else
  LAST_DREAM_EPOCH=0
fi

NOW=$(date +%s)
ELAPSED=$(( NOW - LAST_DREAM_EPOCH ))

# Block if the elapsed time since the last recorded /dream exceeds the interval.
# Note: YYYY-MM-DD parses to midnight local time, so a dream recorded at 23:59
# can appear "24h old" as soon as the clock ticks past the next midnight. That is
# acceptable: /dream is cheap and the nag is benign.
if [ "$ELAPSED" -ge "$DREAM_INTERVAL_SECONDS" ]; then
  HOURS=$(( ELAPSED / 3600 ))
  jq -n --arg hours "$HOURS" --arg raw "$LAST_DREAM_RAW" '{
    "decision": "block",
    "reason": ("Memory consolidation is overdue (" + $hours + "h since last /dream, last=" + $raw + "). Run /dream before ending session.")
  }'
else
  # Not overdue — allow stop
  exit 0
fi
