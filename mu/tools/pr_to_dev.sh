#!/usr/bin/env bash
# Create (or locate) a pull request with base branch locked to dev.
#
# Usage:
#   tools/pr_to_dev.sh
#   tools/pr_to_dev.sh --title "my title" --body "my body"
#   tools/pr_to_dev.sh --fill
#
# Notes:
# - Refuses to run from branch "dev"
# - Requires current branch to be pushed to origin first
# - If gh auth is unavailable, prints a compare URL fallback

set -euo pipefail

BASE_BRANCH="dev"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '1,14p' "$0"
  exit 0
fi

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: not inside a git repository."
  exit 1
fi
cd "$REPO_ROOT"

HEAD_BRANCH="$(git branch --show-current)"
if [[ -z "$HEAD_BRANCH" ]]; then
  echo "ERROR: unable to determine current branch."
  exit 1
fi

if [[ "$HEAD_BRANCH" == "$BASE_BRANCH" ]]; then
  echo "ERROR: current branch is '$BASE_BRANCH'."
  echo "Create a feature branch first, then run this command again."
  echo "Example: git switch -c codex/my-change"
  exit 1
fi

if ! REMOTE_HEADS="$(git ls-remote --heads origin 2>/dev/null)"; then
  echo "ERROR: unable to query remote 'origin'. Check network/auth."
  exit 1
fi

if ! echo "$REMOTE_HEADS" | awk '{print $2}' | grep -qx "refs/heads/$HEAD_BRANCH"; then
  echo "ERROR: branch '$HEAD_BRANCH' is not pushed to origin."
  echo "Run: git push -u origin $HEAD_BRANCH"
  exit 1
fi

if command -v gh >/dev/null 2>&1 && gh auth status -h github.com >/dev/null 2>&1; then
  # If an open PR already exists for this head/base pair, reuse it.
  EXISTING_URL="$(
    gh pr list \
      --state open \
      --head "$HEAD_BRANCH" \
      --base "$BASE_BRANCH" \
      --json url \
      --jq '.[0].url // ""' 2>/dev/null || true
  )"

  if [[ -n "$EXISTING_URL" ]]; then
    echo "Open PR already exists:"
    echo "$EXISTING_URL"
    exit 0
  fi

  if [[ "$#" -gt 0 ]]; then
    gh pr create --base "$BASE_BRANCH" --head "$HEAD_BRANCH" "$@"
  else
    gh pr create --base "$BASE_BRANCH" --head "$HEAD_BRANCH" --fill
  fi
  exit 0
fi

# Fallback when gh is unavailable or not authenticated.
REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
if [[ "$REMOTE_URL" =~ github\.com[:/](.+/.+)\.git$ ]]; then
  REPO_SLUG="${BASH_REMATCH[1]}"
  echo "gh is unavailable or not authenticated."
  echo "Open this URL to create the PR (base locked to dev):"
  echo "https://github.com/$REPO_SLUG/compare/$BASE_BRANCH...$HEAD_BRANCH?expand=1"
  exit 0
fi

echo "gh is unavailable or not authenticated."
echo "Unable to derive GitHub URL from origin remote."
echo "Create PR manually with base '$BASE_BRANCH' and head '$HEAD_BRANCH'."
exit 1
