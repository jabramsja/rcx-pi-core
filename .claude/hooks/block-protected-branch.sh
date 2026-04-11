#!/usr/bin/env bash
# PreToolUse hook on Bash: block git commit/push on protected branches (dev, main).
# Catches the "committed on dev, had to create branch after" mistake.
set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""' < /dev/stdin 2>/dev/null || echo "")

# 2026-04-11 PR #746 P1 fix + PR #754 P1 follow-up: strip bash comments
# PER LINE BEFORE flattening newlines, AND only match `#` at word
# boundaries (start of line or after whitespace) — `#` INSIDE a word
# (e.g. `echo foo#bar`) is literal text, not a comment delimiter in bash.
#
# Prior iterations and their bugs:
#
#   v1 (pre-2026-04-11 P746): `CMD_ONELINE=$(tr '\n' ' '); CMD_STRIPPED=$(sed 's/#[^;|&]*(;|&&|\|\||$)//g' ...)`
#     BUG: flatten first, then strip. A multiline command like
#     "# this is a comment\ngit commit -m x" flattened to
#     "# this is a comment git commit -m x", then sed matched from
#     `#` to end-of-flattened-string (no `;|&` separator present),
#     erasing `git commit`. BLOCKED stayed false → protected-branch
#     guard was BYPASSED for multiline input starting with a comment.
#     Bot finding: PR #746 P1 inline at line 14.
#     BENEFIT by accident: correctly handled `echo foo#bar; git commit -m x`
#     because `[^;|&]*` stopped at `;`.
#
#   v2 (first PR #754 attempt): `CMD_NOCOMMENTS=$(sed 's/#.*$//g' <<< CMD); CMD_ONELINE=$(tr '\n' ' ' <<< CMD_NOCOMMENTS)`
#     BUG: strip first, then flatten — correct order for multiline —
#     BUT the regex `#.*$` treats EVERY `#` as comment start. For
#     `echo foo#bar; git commit -m x`, the `.*$` match eats
#     `#bar; git commit -m x`, leaving `echo foo`. BLOCKED stayed
#     false → protected-branch guard BYPASSED again.
#     Bot finding: PR #754 P1 inline at line 28 (reproduced on tmp
#     main-branch repo: hook returned allow for the foo#bar case).
#
#   v3 (this fix, 2026-04-11): `CMD_NOCOMMENTS=$(sed -E 's/(^|[[:space:]])#.*$/\1/g' <<< CMD); ...`
#     Per-line processing (handles v1 multiline bug) AND word-boundary
#     match (handles v2 foo#bar bug). `(^|[[:space:]])` matches either
#     beginning-of-line or whitespace before the `#`. `\1` backreference
#     preserves the matched anchor character (so the preceding
#     whitespace isn't consumed by the substitution).
#
# Verified via 6 smoke tests (see protocol_wave_execution tests or run
# the inline scenarios in the commit message): (A) multiline comment
# + git commit BLOCKS, (B) single-line inline comment does NOT block,
# (C) quoted git commit does NOT block, (D) bare git commit BLOCKS,
# (F) `git checkout -b pre-commit-fix` does NOT block, (G) NEW
# `echo foo#bar; git commit -m x` BLOCKS (this is the PR #754 P1
# regression scenario).
#
# NOTE on BSD sed: `[^\n]` inside a character class is NOT a newline
# exclusion — it's literal `\` and `n` — so `[^\n]*$` would fail to
# match comments containing the letter `n`. Always use `.*$` against
# line-oriented input.
CMD_NOCOMMENTS=$(echo "$CMD" | sed -E 's/(^|[[:space:]])#.*$/\1/g')

# Collapse newlines to single line for regex matching (catches multiline git commands)
CMD_ONELINE=$(echo "$CMD_NOCOMMENTS" | tr '\n' ' ')

# Strip content inside quotes to avoid false positives like
# echo "...git commit...". Comments are already stripped above.
CMD_STRIPPED=$(echo "$CMD_ONELINE" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")

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
