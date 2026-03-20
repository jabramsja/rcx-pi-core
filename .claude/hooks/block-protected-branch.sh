#!/usr/bin/env bash
# PreToolUse hook on Bash: block git commit/push on protected branches (dev, main).
# Catches the "committed on dev, had to create branch after" mistake.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# Collapse newlines to single line for regex matching (catches multiline git commands)
CMD_ONELINE=$(echo "$CMD" | tr '\n' ' ')

# Match destructive git operations anywhere in command (handles && chains, env prefixes, git -c flags)
# Covers: commit, push, merge, rebase, cherry-pick, reset, revert, am
# Uses \bgit\b.*\b(subcommand)\b to allow arbitrary flags between git and subcommand (e.g., git -c key=val commit)
if ! echo "$CMD_ONELINE" | grep -qE '\bgit\b.*\b(commit|push|merge|rebase|cherry-pick|reset|revert|am)\b'; then
  exit 0
fi

# Fail closed: reject empty/unset CLAUDE_PROJECT_DIR before cd attempt
# cd "" succeeds (stays in cwd), so explicit check is required for fail-closed behavior
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  jq -n '{"decision": "block", "reason": "CLAUDE_PROJECT_DIR not set - blocking for safety"}'
  exit 0
fi
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || {
  jq -n '{"decision": "block", "reason": "Cannot cd to project directory - blocking for safety"}'
  exit 0
}

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

case "$BRANCH" in
  dev|main|master)
    jq -n --arg reason "Cannot ${CMD%% *} on protected branch '$BRANCH'. Create a feature branch first: git checkout -b jabramsja/<wave-name>" \
      '{"decision": "block", "reason": $reason}'
    ;;
esac
