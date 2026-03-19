#!/usr/bin/env bash
# PreToolUse hook on Bash: block git commit/push on protected branches (dev, main).
# Catches the "committed on dev, had to create branch after" mistake.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# Match git commit/push anywhere in command (handles && chains, env prefixes)
if ! echo "$CMD" | grep -qE '\bgit\s+(commit|push)\b'; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

case "$BRANCH" in
  dev|main|master)
    cat <<EOF
{"continue": false, "stopReason": "Cannot ${CMD%% *} on protected branch '$BRANCH'. Create a feature branch first:\n  git checkout -b jabramsja/<wave-name>\nor for closeouts:\n  git checkout -b closeout/<wave-name>"}
EOF
    ;;
esac
