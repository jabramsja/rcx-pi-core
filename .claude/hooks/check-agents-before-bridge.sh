#!/usr/bin/env bash
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
# PreToolUse hook on Bash: check agents ran recently before bridge_supervisor.py review/submit.
# Catches the "skipped agents, went straight to bridge" protocol violation.
# NOTE: Setup/diagnostic subcommands (init, status, render, events, doctor) are NOT gated.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# Collapse newlines to single line for regex matching (catches multiline commands)
CMD_ONELINE=$(echo "$CMD" | tr '\n' ' ')

# Only gate SUBMISSION subcommands (review, run, continue, submit)
# Setup/diagnostic subcommands (init, status, render, events, doctor) do NOT require evidence
SUBMISSION_CMDS="review|run|continue|submit"

# Match bridge_supervisor submission invocations:
# - Script + optional flags + submission subcommand: bridge_supervisor.py [--flag...] review|run|continue|submit
# - Module invocation: -m [mu.]tools.agents.bridge_supervisor [--flag...] + submission subcommand
# Note: (\s+--[^\s]+)* allows --repo-root, --verbose, etc before the subcommand
# Excludes:
# - echo bridge_supervisor.py (no subcommand)
# - python3 -m pytest tests/...bridge_supervisor.py (different module path)
# - python3 -m tools.agents.bridge_supervisor --help (no executable subcommand)
# - bridge_supervisor.py init/status/doctor (setup/diagnostic, not gated)
if ! echo "$CMD_ONELINE" | grep -qE "bridge_supervisor\.py(\s+--[^\s]+)*\s+($SUBMISSION_CMDS)|-m\s+(mu\.)?tools\.agents\.bridge_supervisor(\s+--[^\s]+)*\s+($SUBMISSION_CMDS)"; then
  exit 0
fi

# Fail closed: reject empty/unset CLAUDE_PROJECT_DIR before cd attempt
# cd "" succeeds (stays in cwd), so explicit check is required for fail-closed behavior
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  echo '{"decision": "block", "reason": "CLAUDE_PROJECT_DIR not set - blocking for safety"}'
  exit 0
fi
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || {
  echo '{"decision": "block", "reason": "Cannot cd to project directory - blocking for safety"}'
  exit 0
}

# Check for agent output in last 2 hours from REPO-LOCAL sources only:
# 1. SDK review ledger (.agent_memory/findings.json) - must be non-empty, recent
# 2. Bridge bus artifacts (.agent_bus/raw/*.txt) - must be non-empty
# 3. SDK run_review.py reports (reports/*review*.md) - must be non-empty
#
# NOTE: Global /private/tmp/claude-*/ removed - caused cross-repo leakage.
# NOTE: Only *review*.md files count - plan files do NOT satisfy the gate.
# NOTE: All evidence must be non-empty to prevent zero-byte file bypass.
# Use || true to prevent crash under set -euo pipefail when directories are absent

# Check .agent_memory/findings.json (SDK default output) - must be non-empty
RECENT_MEMORY=0
if [ -f ".agent_memory/findings.json" ] && [ -s ".agent_memory/findings.json" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    MEMORY_AGE=$(( $(date +%s) - $(stat -f %m ".agent_memory/findings.json") ))
  else
    MEMORY_AGE=$(( $(date +%s) - $(stat -c %Y ".agent_memory/findings.json") ))
  fi
  # 2 hours = 7200 seconds
  if [ "$MEMORY_AGE" -lt 7200 ]; then
    RECENT_MEMORY=1
  fi
fi

# Check .agent_bus/raw/*.txt (non-empty files only)
RECENT_BUS=$( (find .agent_bus/raw/ -name "*.txt" -size +0 -mmin -120 2>/dev/null || true) | wc -l | tr -d ' ')

# Check reports/*review*.md (non-empty files only)
RECENT_REPORTS=$( (find reports/ -maxdepth 1 -name "*review*.md" -size +0 -mmin -120 2>/dev/null || true) | wc -l | tr -d ' ')

if [ "$RECENT_MEMORY" -eq 0 ] && [ "$RECENT_BUS" -eq 0 ] && [ "$RECENT_REPORTS" -eq 0 ]; then
  cat <<EOF
{"decision": "block", "reason": "No recent agent review found. Per Phase A/B protocol, run agents before bridge.\nChecked: .agent_memory/findings.json, .agent_bus/raw/*.txt, reports/*review*.md (all non-empty)\nRun agents now, or use run_review.py --output reports/<name>_review.md"}
EOF
fi
