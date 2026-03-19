#!/usr/bin/env bash
# PreToolUse hook on Bash: check agents ran recently before bridge_supervisor.py.
# Catches the "skipped agents, went straight to bridge" protocol violation.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")
[[ "$CMD" != *bridge_supervisor.py* ]] && exit 0

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Check for agent output in last 2 hours (any .output file in agent bus or tasks)
RECENT_BUS=$(find .agent_bus/raw/ -name "*.txt" -mmin -120 2>/dev/null | wc -l | tr -d ' ')
RECENT_TASKS=$(find /private/tmp/claude-*/ -name "*.output" -mmin -30 2>/dev/null | wc -l | tr -d ' ')

if [ "$RECENT_BUS" -eq 0 ] && [ "$RECENT_TASKS" -eq 0 ]; then
  cat <<EOF
{"continue": false, "stopReason": "No recent agent review found. Per Phase A/B protocol, run agents before bridge.\nCheck .agent_bus/raw/ for recent output, or run agents now."}
EOF
fi
