#!/usr/bin/env bash
# PreToolUse hook on Bash: block git commit/push on protected branches (dev, main).
# Catches the "committed on dev, had to create branch after" mistake.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# Collapse newlines to single line for regex matching (catches multiline git commands)
CMD_ONELINE=$(echo "$CMD" | tr '\n' ' ')

# Strip content inside quotes and bash comments to avoid false positives.
# e.g., echo "...git commit..." or # comment about git commit should NOT trigger.
# Order: strip comments first (# to end of logical line), then quoted strings.
CMD_STRIPPED=$(echo "$CMD_ONELINE" | sed -E 's/#[^;|&]*(;|&&|\|\||$)//g; s/'"'"'[^'"'"']*'"'"'//g; s/"[^"]*"//g')

# Extract git subcommands: find words immediately after "git" (skipping -c key=val style flags).
# Only block on actual git subcommands, not on branch names or other arguments that
# happen to contain words like "commit" (e.g., git checkout -b pre-commit-fix).
BLOCKED=false
EXPECT_FLAG_ARG=false
for word in $CMD_STRIPPED; do
  # After a flag that takes an argument (e.g., -C <path>, -c key=val), skip the argument
  if [ "$EXPECT_FLAG_ARG" = "true" ]; then
    EXPECT_FLAG_ARG=false
    continue
  fi
  case "$word" in
    git) NEXT_IS_GIT_SUB=true; continue ;;
  esac
  if [ "${NEXT_IS_GIT_SUB:-}" = "true" ]; then
    # Skip flags and their arguments (e.g., git -C /path commit, git -c key=val commit)
    # Long options with separate args: --git-dir, --work-tree, --namespace, --super-prefix
    case "$word" in
      -C|-c) EXPECT_FLAG_ARG=true; continue ;;
      --git-dir|--work-tree|--namespace|--super-prefix) EXPECT_FLAG_ARG=true; continue ;;
      --git-dir=*|--work-tree=*|--namespace=*|--super-prefix=*) continue ;;
      -*) continue ;;
      *=*) continue ;;
    esac
    # This is the actual git subcommand
    case "$word" in
      commit|push|merge|rebase|cherry-pick|reset|revert|am)
        BLOCKED=true ;;
    esac
    NEXT_IS_GIT_SUB=false
  fi
done
if [ "$BLOCKED" = "false" ]; then
  exit 0
fi

# Fail closed: reject empty/unset CLAUDE_PROJECT_DIR before cd attempt
# cd "" succeeds (stays in cwd), so explicit check is required for fail-closed behavior
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  jq -n '{"decision": "block", "reason": "CLAUDE_PROJECT_DIR not set - blocking for safety"}'
  exit 0
fi

# Determine the effective git directory: if the command cds to a worktree or
# uses git -C <path>, check the branch THERE, not in the main repo.
# This is critical for pipeline worktree operations where the main repo is on
# dev but the worktree is on a feature branch.
EFFECTIVE_GIT_DIR=""

# Pattern 1: cd <path> && git ...
if [[ "$CMD_ONELINE" =~ cd[[:space:]]+([^[:space:];&]+) ]]; then
  CANDIDATE="${BASH_REMATCH[1]}"
  # Strip quotes if present
  CANDIDATE="${CANDIDATE%\"}"
  CANDIDATE="${CANDIDATE#\"}"
  CANDIDATE="${CANDIDATE%\'}"
  CANDIDATE="${CANDIDATE#\'}"
  if [ -d "$CANDIDATE/.git" ] || [ -f "$CANDIDATE/.git" ]; then
    EFFECTIVE_GIT_DIR="$CANDIDATE"
  fi
fi

# Pattern 2: git -C <path> ...
if [ -z "$EFFECTIVE_GIT_DIR" ] && [[ "$CMD_ONELINE" =~ git[[:space:]]+-C[[:space:]]+([^[:space:]]+) ]]; then
  CANDIDATE="${BASH_REMATCH[1]}"
  CANDIDATE="${CANDIDATE%\"}"
  CANDIDATE="${CANDIDATE#\"}"
  if [ -d "$CANDIDATE/.git" ] || [ -f "$CANDIDATE/.git" ]; then
    EFFECTIVE_GIT_DIR="$CANDIDATE"
  fi
fi

# Fallback: main repo
if [ -z "$EFFECTIVE_GIT_DIR" ]; then
  EFFECTIVE_GIT_DIR="$CLAUDE_PROJECT_DIR"
fi

cd "$EFFECTIVE_GIT_DIR" 2>/dev/null || {
  jq -n '{"decision": "block", "reason": "Cannot cd to git directory - blocking for safety"}'
  exit 0
}

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

case "$BRANCH" in
  dev|main|master)
    jq -n --arg reason "Cannot ${CMD%% *} on protected branch '$BRANCH'. Create a feature branch first: git checkout -b jabramsja/<wave-name>" \
      '{"decision": "block", "reason": $reason}'
    ;;
esac
