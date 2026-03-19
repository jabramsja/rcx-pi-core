#!/usr/bin/env bash
# PreToolUse hook on Bash: check agents ran recently before bridge_supervisor.py.
# Catches the "skipped agents, went straight to bridge" protocol violation.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")
[[ "$CMD" != *bridge_supervisor.py* ]] && exit 0

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Check for agent output in last 2 hours from any source:
# 1. Bridge bus artifacts (.agent_bus/raw/)
# 2. Native subagent traces (/private/tmp/claude-*/)
# 3. SDK run_review.py reports (reports/*.md)
RECENT_BUS=$(find .agent_bus/raw/ -name "*.txt" -mmin -120 2>/dev/null | wc -l | tr -d ' ')
RECENT_TASKS=$(find /private/tmp/claude-*/ -name "*.output" -mmin -30 2>/dev/null | wc -l | tr -d ' ')
RECENT_REPORTS=$(find reports/ -maxdepth 1 -name "*.md" -mmin -120 ! -name "README.md" 2>/dev/null | wc -l | tr -d ' ')

if [ "$RECENT_BUS" -eq 0 ] && [ "$RECENT_TASKS" -eq 0 ] && [ "$RECENT_REPORTS" -eq 0 ]; then
  cat <<EOF
{"continue": false, "stopReason": "No recent agent review found. Per Phase A/B protocol, run agents before bridge.\nChecked: .agent_bus/raw/, /tmp/claude-*/, reports/*.md\nRun agents now, or use run_review.py --output reports/<name>.md"}
EOF
fi
