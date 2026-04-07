#!/bin/bash
# PostToolUse hook: injects a protocol reminder every 5th tool call.
# Counters drift in long tool-call sequences where I optimize for completion
# over verification. This hook creates friction at regular intervals.
#
# Uses a counter file in /tmp — session-scoped, resets on restart.

COUNTER_FILE="/tmp/.rcx_tool_call_counter"

# Increment counter
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(cat "$COUNTER_FILE")
  COUNT=$((COUNT + 1))
else
  COUNT=1
fi
echo "$COUNT" > "$COUNTER_FILE"

# Every 5th call, inject protocol reminder
if [ $((COUNT % 5)) -eq 0 ]; then
  echo '{"additionalContext":"TOOL-CALL CHECKPOINT (#'"$COUNT"'): Are you following override #7 (diagnosis first)? Are you verifying assumptions (#4) or shortcutting? If you are about to claim something works without running it, STOP."}'
fi

exit 0
