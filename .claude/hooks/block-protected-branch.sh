#!/usr/bin/env bash
# PreToolUse hook on Bash: block git commit/push on protected branches (dev, main).
# Catches the "committed on dev, had to create branch after" mistake.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# 2026-04-11 block-protected-branch lexer rewrite: replace the recursive
# sed-regex comment-and-quote stripping (v1-v3 fix cycle; see the packet
# at reports/control_plane/block_protected_branch_lexer_2026-04-11.md
# for the full history, bot findings, and design rationale) with a
# bash-aware state-machine tokenizer that correctly handles POSIX
# word-boundary comments, single-quoted strings, double-quoted strings,
# unquoted backslash escapes, line continuations, and fail-closed
# behavior on malformed input (unclosed quote or trailing backslash at
# end-of-input).
#
# The helper at _block_protected_branch_tokenize.py implements the
# lexer contract. On any parser error it exits 2 and writes no tokens
# to stdout; the hook converts that into a BLOCK decision so malformed
# input cannot turn into an allow path.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The tokenizer emits NUL-terminated tokens (not newline-terminated)
# so that a shell word containing an embedded newline (e.g. a
# single-quoted multiline string) is not fragmented into multiple
# words by the consumer loop below. Buffer the output through a temp
# file because bash command substitution ($(...)) strips NUL bytes
# from its captured output, which would corrupt the delimiter stream.
CMD_TOKENS_FILE=$(mktemp)
trap 'rm -f "$CMD_TOKENS_FILE"' EXIT
if ! printf '%s' "$CMD" \
      | python3 "$HOOK_DIR/_block_protected_branch_tokenize.py" \
      >"$CMD_TOKENS_FILE" 2>/dev/null; then
  jq -n '{"decision": "block", "reason": "block-protected-branch: tokenizer parser error - blocking for safety"}'
  exit 0
fi

# Raw one-line view of the command for the best-effort worktree-path
# detectors at Patterns 1 and 2 below. These are NOT the safety gate -
# they only pick which directory to branch-check in. The safety gate is
# the BLOCKED flag, which uses the tokenizer above. Over-detection here
# causes the branch check to run in the "wrong" worktree whose branch
# is typically protected (dev/main), triggering BLOCK anyway -
# fail-closed.
# Strip per-line comments BEFORE flattening (learning.md 2026-04-11: strip-then-flatten,
# not flatten-then-strip). Then flatten to one line for pattern matching.
CMD_ONELINE=$(printf '%s' "$CMD" | sed -E 's/(^|[[:space:]])#.*$/\1/g' | tr '\n' ' ')

# Extract git subcommands: find words immediately after "git" (skipping -c key=val style flags).
# Only block on actual git subcommands, not on branch names or other arguments that
# happen to contain words like "commit" (e.g., git checkout -b pre-commit-fix).
BLOCKED=false
EXPECT_FLAG_ARG=false
while IFS= read -r -d '' word; do
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
done < "$CMD_TOKENS_FILE"
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
