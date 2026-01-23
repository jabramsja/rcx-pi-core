#!/usr/bin/env bash
set -euo pipefail

: "${HISTTIMEFORMAT:=}"
: "${size:=}"

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/merge_pr_clean.sh <PR_NUMBER>" >&2
  exit 2
fi

PR="$1"

# Read PR metadata (base + head)
BASE_BRANCH="$(gh pr view "$PR" --json baseRefName -q .baseRefName)"
HEAD_BRANCH="$(gh pr view "$PR" --json headRefName -q .headRefName)"

echo "== PR #$PR =="
echo "base: $BASE_BRANCH"
echo "head: $HEAD_BRANCH"
echo

echo "== 0) Fetch latest refs =="
git fetch origin --prune

echo "== 1) Update base branch (origin/$BASE_BRANCH) =="
git checkout "$BASE_BRANCH" >/dev/null
git pull --ff-only
git fetch origin --prune

echo "== 2) Rebase head onto origin/$BASE_BRANCH =="
git checkout "$HEAD_BRANCH" >/dev/null
git rebase "origin/$BASE_BRANCH"

echo "== 3) Push rebased head (safe force) =="
git push --force-with-lease

echo "== 4) Watch PR checks (fail-fast) =="
gh pr checks "$PR" --watch --fail-fast

echo "== 5) Merge PR =="
gh pr merge "$PR" --merge --delete-branch

echo "== 6) Sync base branch after merge =="
git checkout "$BASE_BRANCH" >/dev/null
git pull --ff-only

echo "OK: merged PR #$PR and synced $BASE_BRANCH"
