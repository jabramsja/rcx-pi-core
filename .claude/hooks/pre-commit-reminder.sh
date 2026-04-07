#!/bin/bash
# Claude Code PreToolUse hook: targeted compliance checklist before commits.
#
# Instead of dumping full MEMORY.md/CLAUDE.md (already in context), this hook
# runs quick compliance checks and only surfaces violations or warnings.
#
# First attempt: blocks with targeted checklist.
# Second attempt (within 5 minutes): allows through to git pre-commit hook.
set -e

# Read hook input from stdin (JSON with tool_input)
INPUT=$(cat)

# Extract the Bash command
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only act on git commit commands
if [[ "$COMMAND" =~ git[[:space:]]+commit ]]; then
  MARKER_FILE="/tmp/.rcx_commit_reminder_shown"

  # Check if we already showed the reminder recently (within 5 minutes)
  if [ -f "$MARKER_FILE" ]; then
    MARKER_AGE=$(( $(date +%s) - $(stat -f %m "$MARKER_FILE" 2>/dev/null || stat -c %Y "$MARKER_FILE" 2>/dev/null || echo 0) ))
    if [ "$MARKER_AGE" -lt 300 ]; then
      # Already shown recently — allow through to git pre-commit hook
      exit 0
    fi
  fi

  # First attempt: block and run targeted checklist
  touch "$MARKER_FILE"

  cd "$(git rev-parse --show-toplevel)"

  WARNINGS=""
  CHECKS=""

  # 1. Core files changed? Check if agent review was run
  STAGED_CORE=$(git diff --cached --name-only 2>/dev/null | grep -E '^(rcx_pi/selfhost/|mu/host/)' || true)
  if [ -n "$STAGED_CORE" ]; then
    MEMORY_FILE=".agent_memory/findings.json"
    if [ -f "$MEMORY_FILE" ]; then
      MEMORY_AGE=$(( $(date +%s) - $(stat -f %m "$MEMORY_FILE" 2>/dev/null || stat -c %Y "$MEMORY_FILE" 2>/dev/null || echo 0) ))
      if [ "$MEMORY_AGE" -lt 3600 ]; then
        CHECKS="${CHECKS}\n  ✅ Core files changed + agent review run (<1h ago)"
      else
        WARNINGS="${WARNINGS}\n  ⚠️  Core files changed but agent review is stale (>1h ago). Consider: run_review.py --pr --depth quick"
      fi
    else
      WARNINGS="${WARNINGS}\n  ⚠️  Core files changed but NO agent review detected. Consider: run_review.py --pr --depth quick"
    fi
  else
    CHECKS="${CHECKS}\n  ✅ No core runtime files staged — agent review not required"
  fi

  # 2. STATUS.md or TASKS.md in staged files (if core files changed)?
  STAGED_STATUS=$(git diff --cached --name-only 2>/dev/null | grep -E '^(STATUS\.md|TASKS\.md)' || true)
  if [ -n "$STAGED_CORE" ] && [ -z "$STAGED_STATUS" ]; then
    WARNINGS="${WARNINGS}\n  ⚠️  Core files changed but STATUS.md/TASKS.md not staged. Update tracker note if needed."
  elif [ -n "$STAGED_STATUS" ]; then
    CHECKS="${CHECKS}\n  ✅ STATUS.md/TASKS.md included in commit"
  fi

  # 3. Check for test failures dismissed (look for recent pytest runs)
  LAST_TEST=$(find /tmp -maxdepth 1 -name '.rcx_last_test_result' -newer "$MARKER_FILE" 2>/dev/null || true)
  CHECKS="${CHECKS}\n  ℹ️  Pre-commit hook will run doc consistency + governance tests automatically"

  # 4. Bridge status (check for recent bridge jobs)
  BRIDGE_DB="$HOME/.rcx_bridge/bridge.db"
  if [ -f "$BRIDGE_DB" ] && [ -n "$STAGED_CORE" ]; then
    BRIDGE_AGE=$(( $(date +%s) - $(stat -f %m "$BRIDGE_DB" 2>/dev/null || stat -c %Y "$BRIDGE_DB" 2>/dev/null || echo 0) ))
    if [ "$BRIDGE_AGE" -lt 3600 ]; then
      CHECKS="${CHECKS}\n  ✅ Bridge activity detected (<1h ago)"
    else
      WARNINGS="${WARNINGS}\n  ⚠️  No recent bridge activity. Wave protocol requires bridge convergence before commit."
    fi
  fi

  # 5. Summary line count
  STAGED_COUNT=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
  CHECKS="${CHECKS}\n  ℹ️  ${STAGED_COUNT} file(s) staged for commit"

  # Build output — only BLOCK if there are warnings. Clean checklists pass through.
  if [ -n "$WARNINGS" ]; then
    RESULT="PRE-COMMIT COMPLIANCE CHECKLIST:\n${CHECKS}\n\nWARNINGS:${WARNINGS}\n\nVerify warnings are intentional, then re-run git commit."
    jq -n --arg msg "$RESULT" '{
      "decision": "block",
      "reason": $msg
    }'
  else
    # No warnings — allow through (display checklist as info, don't block)
    echo ""
    exit 0
  fi
else
  exit 0
fi
