#!/bin/bash
# PreToolUse:Bash hook — mechanically requires deep thinking before high-risk actions.
#
# CANNOT be skipped. Fires on every Bash tool call matching high-risk patterns.
# Injects category-specific thinking requirements + relevant learnings.
#
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
#
# Categories:
#   PIPELINE — dispatch, phase executors, commit executor
#   COMMIT   — git commit, git push, merge
#   STRUCTURAL — mu/ runtime edits, rcx_pi/selfhost
#
# Integration with learning.md:
#   Pulls entries matching the detected category and injects them
#   as context for deep thinking. Past mistakes inform future decisions.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

# Skip empty commands
[ -z "$CMD" ] && exit 0

# Detect high-risk categories
CATEGORY=""
if echo "$CMD" | grep -qE 'executor_dispatch|phase_[ab]_executor|commit_executor'; then
  CATEGORY="PIPELINE"
elif echo "$CMD" | grep -qE 'git commit |git push |merge_pr|gh pr merge'; then
  CATEGORY="COMMIT"
fi

# Only fire for genuinely high-risk patterns (not grep/ls/status checks)
[ -z "$CATEGORY" ] && exit 0

LEARNING_FILE="$CLAUDE_PROJECT_DIR/.claude/rules/learning.md"

# Pull category-specific learnings (and related categories)
RELEVANT=""
if [ -f "$LEARNING_FILE" ]; then
  case "$CATEGORY" in
    PIPELINE)
      RELEVANT=$(grep -B0 -A1 "^\- \[.*\] \(PIPELINE\|DISPATCH\|BOOTSTRAP\|WORKTREE\|BRIDGE\)" "$LEARNING_FILE" 2>/dev/null | head -12)
      ;;
    COMMIT)
      RELEVANT=$(grep -B0 -A1 "^\- \[.*\] \(COMMIT\|PIPELINE\|HOOK\)" "$LEARNING_FILE" 2>/dev/null | head -8)
      ;;
  esac
fi

# Check for prior pipeline failure (requires root-cause fix before restart)
FAILURE_WARN=""
if [ "$CATEGORY" = "PIPELINE" ]; then
  # Search for failed dispatch logs in common worktree locations
  for log in /private/tmp/workingrcx_*/.scratch/dispatch_live.log; do
    if [ -f "$log" ] && grep -q '"status": "failed"\|Status: failed\|status.*error' "$log" 2>/dev/null; then
      FAIL_REASON=$(grep -o '"error": "[^"]*"' "$log" 2>/dev/null | tail -1 | cut -c10-120)
      FAILURE_WARN="PRIOR PIPELINE FAILURE DETECTED in $(dirname "$log"). Error: ${FAIL_REASON:-unknown}. You MUST show: (1) Root cause identified (not guessed). (2) Fix applied (show diff or file changed). (3) Why this fix prevents recurrence. Band-aids (increasing timeouts, skipping gates) are NOT acceptable unless the structural fix is also included."
      break
    fi
  done
fi

# Escape for JSON
ESCAPED_RELEVANT=$(echo "$RELEVANT" | sed 's/"/\\"/g' | tr '\n' '|' | sed 's/|/\\n/g')
ESCAPED_FAILURE=$(echo "$FAILURE_WARN" | sed 's/"/\\"/g')

FAILURE_BLOCK=""
if [ -n "$FAILURE_WARN" ]; then
  FAILURE_BLOCK="\\n\\n--- PIPELINE FAILURE ENFORCEMENT ---\\n${ESCAPED_FAILURE}"
fi

cat <<HOOKEOF
{"systemMessage":"ultrathink\\n\\nULTRATHINK REQUIRED — ${CATEGORY} action detected. This triggers extended thinking mode (~32K token reasoning budget).\\n\\nBefore proceeding, you MUST reason through and STATE visibly:\\n1. What are the 3 most likely failure modes for this action?\\n2. What preconditions have you verified? What have you NOT verified?\\n3. What is the rollback plan if this fails?\\n4. What learnings from .claude/rules/learning.md apply here?\\n5. What is the SIMPLEST correct approach? (reject complexity)\\n\\nRelevant learnings from prior sessions:\\n${ESCAPED_RELEVANT:-none captured yet}${FAILURE_BLOCK}\\n\\nDo NOT execute the action without visible ultrathink reasoning first."}
HOOKEOF

exit 0
