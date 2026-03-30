#!/usr/bin/env bash
# _pane_prci.sh — PR/CI status pane for pipeline_monitor
# Resilient: never exits on transient errors (gh timeouts, network issues)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
while true; do
  clear
  echo "PR / CI STATUS"
  echo "──────────────"

  PR=""

  # Strategy 1: Check executor handoff for PR number
  EXEC_FILE=$(ls -t "$REPO_ROOT/.agent_bus/executors/commit_executor_"*.json 2>/dev/null | head -1) || true
  if [ -n "$EXEC_FILE" ]; then
    PR=$(jq -r '.pr_number // empty' "$EXEC_FILE" 2>/dev/null) || PR=""
  fi

  # Strategy 2: Fallback — find PR for current branch via gh pr list
  if [ -z "$PR" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || BRANCH=""
    if [ -n "$BRANCH" ] && [ "$BRANCH" != "dev" ] && [ "$BRANCH" != "main" ]; then
      PR=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number' 2>/dev/null) || PR=""
    fi
  fi

  # Strategy 3: Fallback — most recent open PR in the repo
  if [ -z "$PR" ]; then
    PR=$(gh pr list --state open --limit 1 --json number --jq '.[0].number' 2>/dev/null) || PR=""
  fi

  if [ -n "$PR" ]; then
    echo "PR #$PR"
    echo ""

    # CI checks
    echo "CI Checks:"
    gh pr checks "$PR" 2>/dev/null | head -8 || echo "  (gh checks unavailable)"
    echo ""

    # Latest review
    REVIEW=$(gh pr view "$PR" --json reviews --jq '.reviews[-1] | "\(.state) by \(.author.login) at \(.submittedAt[:16])"' 2>/dev/null) || REVIEW=""
    if [ -n "$REVIEW" ]; then
      echo "Latest review: $REVIEW"
    fi

    # Bot comments (last 3)
    BOT_COMMENTS=$(gh pr view "$PR" --json comments --jq '[.comments[] | select(.author.login == "github-actions" or .author.login == "bot" or (.author.login | test("\\[bot\\]$"))) | .author.login + ": " + (.body | split("\n")[0])[:80]] | last(3) | .[]' 2>/dev/null | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g') || BOT_COMMENTS=""
    if [ -n "$BOT_COMMENTS" ]; then
      echo ""
      echo "Bot comments:"
      echo "$BOT_COMMENTS"
    fi

    # Review thread count
    THREAD_COUNT=$(gh api "repos/{owner}/{repo}/pulls/$PR/comments" --jq 'length' 2>/dev/null) || THREAD_COUNT=""
    if [ -n "$THREAD_COUNT" ] && [ "$THREAD_COUNT" != "0" ]; then
      echo ""
      echo "Review threads: $THREAD_COUNT"
    fi
  else
    echo "No active PR found"
  fi

  sleep 15
done
