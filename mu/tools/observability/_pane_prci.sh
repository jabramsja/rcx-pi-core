#!/usr/bin/env bash
# _pane_prci.sh — PR/CI status pane for pipeline_monitor
# Resilient: never exits on transient errors (gh timeouts, network issues)
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
while true; do
  clear
  echo "PR / CI STATUS"
  echo "──────────────"
  EXEC_FILE=$(ls -t "$REPO_ROOT/.agent_bus/executors/commit_executor_"*.json 2>/dev/null | head -1) || true
  if [ -n "$EXEC_FILE" ]; then
    PR=$(jq -r '.pr_number // empty' "$EXEC_FILE" 2>/dev/null) || PR=""
    if [ -n "$PR" ]; then
      echo "PR #$PR"
      gh pr checks "$PR" 2>/dev/null | head -8 || echo "  (gh checks unavailable)"
      echo ""
      REVIEW=$(gh pr view "$PR" --json reviews --jq '.reviews[-1] | "Review: " + (.commit.oid[:10]) + " " + .submittedAt + " " + .state' 2>/dev/null) || REVIEW=""
      [ -n "$REVIEW" ] && echo "$REVIEW"
    else
      echo "No PR yet"
    fi
  else
    # Fallback: check current branch for open PRs
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || BRANCH=""
    if [ -n "$BRANCH" ] && [ "$BRANCH" != "dev" ]; then
      PR_NUM=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number' 2>/dev/null) || PR_NUM=""
      if [ -n "$PR_NUM" ]; then
        echo "PR #$PR_NUM (from branch)"
        gh pr checks "$PR_NUM" 2>/dev/null | head -8 || echo "  (gh checks unavailable)"
      else
        echo "No active executor or PR"
      fi
    else
      echo "No active executor or PR"
    fi
  fi
  sleep 15
done
