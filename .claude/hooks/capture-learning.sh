#!/bin/bash
# PostToolUse:Bash hook — captures learning opportunities from errors.
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
#
# Mechanical learning system:
# 1. On Bash error (non-zero exit): extract error text from tool output
# 2. Search .claude/rules/learning.md for matching fingerprint
# 3. MATCH: inject known fix as systemMessage (instant recall)
# 4. NO MATCH: inject learning capture prompt (forces new entry)
#
# Also fires on PreToolUse:Bash for high-risk commands (dispatch, commit, merge)
# to inject relevant learnings as pre-action checklists.

LEARNING_FILE="$CLAUDE_PROJECT_DIR/.claude/rules/learning.md"
HOOK_EVENT="${HOOK_EVENT_NAME:-PostToolUse}"

# Ensure learning file exists
if [ ! -f "$LEARNING_FILE" ]; then
  exit 0
fi

# Read tool input from stdin
INPUT=$(cat)

if [ "$HOOK_EVENT" = "PreToolUse" ]; then
  # --- PRE-ACTION CHECKLIST INJECTION ---
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

  # Check for high-risk dispatch commands
  if echo "$CMD" | grep -q 'executor_dispatch\|commit_executor'; then
    # Extract DISPATCH and BOOTSTRAP learnings
    RELEVANT=$(grep -E '^\- \[.*\] (DISPATCH|BOOTSTRAP|WORKTREE):' "$LEARNING_FILE" 2>/dev/null | head -5)
    if [ -n "$RELEVANT" ]; then
      # Escape for JSON
      ESCAPED=$(echo "$RELEVANT" | sed 's/"/\\"/g' | tr '\n' '|' | sed 's/|/\\n/g')
      echo "{\"systemMessage\":\"LEARNING CHECKLIST (pre-action injection from .claude/rules/learning.md):\\n${ESCAPED}\\nVerify these before proceeding.\"}"
    fi
  fi
  exit 0
fi

# --- POST-TOOL ERROR DETECTION ---
# Check if exit code was non-zero
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_output.exit_code // .tool_output.exitCode // "0"' 2>/dev/null)

# Only trigger on actual errors (not grep returning 1 for no match, etc.)
# Skip exit code 1 for grep-like commands
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)
if [ "$EXIT_CODE" = "1" ]; then
  if echo "$CMD" | grep -qE '^(grep|rg|kill|test |\[)'; then
    exit 0
  fi
fi

if [ "$EXIT_CODE" != "0" ] && [ -n "$EXIT_CODE" ]; then
  # Extract error text (first 200 chars of output for fingerprinting)
  ERROR_TEXT=$(echo "$INPUT" | jq -r '.tool_output.output // .tool_output.stderr // ""' 2>/dev/null | head -5 | cut -c1-200)

  if [ -z "$ERROR_TEXT" ]; then
    exit 0
  fi

  # Search for matching fingerprint in learning file
  # Extract fingerprint fields and check if any match the error text
  MATCH=""
  while IFS= read -r fingerprint; do
    if echo "$ERROR_TEXT" | grep -qF "$fingerprint"; then
      # Found a match — extract the full entry
      MATCH=$(sed -n "/fingerprint: .${fingerprint}./,+2p" "$LEARNING_FILE" 2>/dev/null | head -3)
      break
    fi
  done < <(sed -n 's/.*fingerprint: `\([^`]*\)`.*/\1/p' "$LEARNING_FILE" 2>/dev/null)

  if [ -n "$MATCH" ]; then
    # KNOWN PATTERN — inject the fix
    ESCAPED=$(echo "$MATCH" | sed 's/"/\\"/g' | tr '\n' '|' | sed 's/|/\\n/g')
    echo "{\"systemMessage\":\"KNOWN ERROR PATTERN (from .claude/rules/learning.md):\\n${ESCAPED}\\nApply the fix above instead of re-diagnosing.\"}"
  else
    # NEW PATTERN — force learning capture
    SHORT_ERR=$(echo "$ERROR_TEXT" | head -1 | cut -c1-80)
    echo "{\"systemMessage\":\"NEW ERROR PATTERN (exit $EXIT_CODE). After resolving: append to .claude/rules/learning.md with fingerprint. Format:\\n- [DATE] CATEGORY | fingerprint: \`key error text\` | refs: 1\\n  Description. **Fix:** steps.\\nError preview: ${SHORT_ERR}\"}"
  fi
fi

exit 0
