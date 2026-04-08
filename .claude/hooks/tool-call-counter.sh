#!/bin/bash
# PostToolUse hook: BLOCKS every 20th tool call for a forced verification step.
# Injects friction reminder every 10th call (non-blocking).
#
# The blocking checkpoint forces a full stop and verification statement.
# The non-blocking reminder creates lighter friction between checkpoints.
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

# Every 20th call: BLOCK — force verification step
if [ $((COUNT % 20)) -eq 0 ]; then
  echo '{"decision":"block","reason":"VERIFICATION CHECKPOINT (#'"$COUNT"'): You have made 20 tool calls since the last checkpoint. Before continuing, you MUST state: (1) What you are trying to accomplish. (2) What you have verified so far. (3) What assumption you are about to act on. Resume after stating these."}'
  exit 0
fi

# Every 10th call (not 20th): non-blocking reminder
if [ $((COUNT % 10)) -eq 0 ]; then
  echo '{"additionalContext":"TOOL-CALL CHECKPOINT (#'"$COUNT"'): Are you following override #7 (diagnosis first)? Are you verifying assumptions (#4) or shortcutting? If you are about to claim something works without running it, STOP."}'
fi

exit 0
