#!/usr/bin/env bash
# _pane_prci.sh — PR/CI status pane for pipeline_monitor
REPO_ROOT="$(git rev-parse --show-toplevel)"
while true; do
  clear
  echo "PR / CI STATUS"
  echo "──────────────"
  EXEC_FILE=$(ls -t "$REPO_ROOT/.agent_bus/executors/commit_executor_"*.json 2>/dev/null | head -1)
  if [ -n "$EXEC_FILE" ]; then
    PR=$(jq -r '.pr_number // empty' "$EXEC_FILE" 2>/dev/null)
    if [ -n "$PR" ]; then
      echo "PR #$PR"
      gh pr checks "$PR" 2>/dev/null | head -8
      echo ""
      REVIEW=$(gh pr view "$PR" --json reviews --jq '.reviews[-1] | "Review: " + (.commit.oid[:10]) + " " + .submittedAt + " " + .state' 2>/dev/null)
      [ -n "$REVIEW" ] && echo "$REVIEW"
    else
      echo "No PR yet"
    fi
  else
    echo "No active executor"
  fi
  sleep 15
done
