#!/usr/bin/env bash
# pipeline_status.sh — One-shot pipeline state summary
# Read-only: never modifies state, only reads .agent_bus/ and process info.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
BUS="$REPO_ROOT/.agent_bus"

# Colors (disable if not tty)
if [ -t 1 ]; then
  BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
  RED="\033[31m" CYAN="\033[36m" RESET="\033[0m"
else
  BOLD="" DIM="" GREEN="" YELLOW="" RED="" CYAN="" RESET=""
fi

echo -e "${BOLD}PIPELINE STATUS${RESET} ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "────────────────────────────────────────"

# ── Executor State ──
EXEC_FILES=$(find "$BUS/executors" -name 'commit_executor_*.json' -newer "$BUS/executors" 2>/dev/null | head -1)
if [ -z "$EXEC_FILES" ]; then
  EXEC_FILES=$(ls -t "$BUS/executors"/commit_executor_*.json 2>/dev/null | head -1)
fi

if [ -n "$EXEC_FILES" ] && [ -f "$EXEC_FILES" ]; then
  WAVE=$(jq -r '.target_branch // "unknown"' "$EXEC_FILES" 2>/dev/null | sed 's|jabramsja/||')
  STATUS=$(jq -r '.status // "unknown"' "$EXEC_FILES" 2>/dev/null)
  STEPS=$(jq -r '.steps_completed | length' "$EXEC_FILES" 2>/dev/null)
  LAST_STEP=$(jq -r '.steps_completed[-1] // "none"' "$EXEC_FILES" 2>/dev/null)
  PR=$(jq -r '.pr_number // "none"' "$EXEC_FILES" 2>/dev/null)
  echo -e "${CYAN}Executor:${RESET} $WAVE"
  echo -e "  Step: ${BOLD}$STEPS/15${RESET} ($LAST_STEP) | Status: $STATUS | PR: #$PR"
else
  echo -e "${DIM}Executor: idle (no active commit state)${RESET}"
fi

# ── Phase B Handoff ──
HANDOFF="$BUS/executors/phase_b_handoff.json"
if [ -f "$HANDOFF" ]; then
  HO_WAVE=$(jq -r '.wave_id // "unknown"' "$HANDOFF" 2>/dev/null)
  HO_TASK=$(jq -r '.task_id // "unknown"' "$HANDOFF" 2>/dev/null)
  echo -e "${CYAN}Handoff:${RESET} $HO_WAVE ($HO_TASK)"
else
  echo -e "${DIM}Handoff: none${RESET}"
fi

# ── Supervisor Receipt ──
LATEST_RECEIPT=$(ls -t "$BUS/meta/pre_commit_receipts"/receipt_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_RECEIPT" ] && [ -f "$LATEST_RECEIPT" ]; then
  DECISION=$(jq -r '.decision // "unknown"' "$LATEST_RECEIPT" 2>/dev/null)
  TIMESTAMP=$(jq -r '.timestamp_utc // "unknown"' "$LATEST_RECEIPT" 2>/dev/null)
  if [ "$DECISION" = "COMMIT_GO" ]; then
    echo -e "${CYAN}Receipt:${RESET} ${GREEN}$DECISION${RESET} ($TIMESTAMP)"
  else
    echo -e "${CYAN}Receipt:${RESET} ${YELLOW}$DECISION${RESET} ($TIMESTAMP)"
  fi
else
  echo -e "${DIM}Receipt: none${RESET}"
fi

# ── Post-Merge Routing ──
ROUTING="$BUS/meta/post_merge_routing.json"
if [ -f "$ROUTING" ]; then
  ROUTE_DEC=$(jq -r '.decision // "unknown"' "$ROUTING" 2>/dev/null)
  ROUTE_TS=$(jq -r '.timestamp_utc // "unknown"' "$ROUTING" 2>/dev/null)
  echo -e "${CYAN}Routing:${RESET} $ROUTE_DEC ($ROUTE_TS)"
else
  echo -e "${DIM}Routing: none${RESET}"
fi

# ── Bridge Lock ──
LOCK="$BUS/meta/meta_bridge.lock"
if [ -f "$LOCK" ]; then
  HOLDER=$(jq -r '.holder // "unknown"' "$LOCK" 2>/dev/null)
  LOCK_PID=$(jq -r '.pid // "?"' "$LOCK" 2>/dev/null)
  # Check if lock holder is still alive
  if kill -0 "$LOCK_PID" 2>/dev/null; then
    echo -e "${CYAN}Bridge:${RESET} ${YELLOW}LOCKED${RESET} by $HOLDER (PID $LOCK_PID, alive)"
  else
    echo -e "${CYAN}Bridge:${RESET} ${RED}STALE LOCK${RESET} by $HOLDER (PID $LOCK_PID, dead)"
  fi
else
  echo -e "${CYAN}Bridge:${RESET} idle (no lock)"
fi

# ── Active Processes ──
echo ""
EXEC_PIDS=$(pgrep -f "executor_dispatch\|commit_executor\|phase_b_executor\|phase_a_executor\|meta_bridge_supervisor" 2>/dev/null || true)
if [ -n "$EXEC_PIDS" ]; then
  echo -e "${BOLD}Active Processes:${RESET}"
  for pid in $EXEC_PIDS; do
    CMD=$(ps -p "$pid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-70)
    ELAPSED=$(ps -p "$pid" -o etime= 2>/dev/null | xargs)
    echo -e "  PID $pid (${ELAPSED}) $CMD"
    # Show children
    CHILDREN=$(pgrep -P "$pid" 2>/dev/null || true)
    for cpid in $CHILDREN; do
      CCMD=$(ps -p "$cpid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-60)
      echo -e "    └─ PID $cpid $CCMD"
    done
  done
else
  echo -e "${DIM}No active pipeline processes${RESET}"
fi

# ── PR / CI Status ──
if [ -n "$EXEC_FILES" ] && [ -f "$EXEC_FILES" ]; then
  PR_NUM=$(jq -r '.pr_number // ""' "$EXEC_FILES" 2>/dev/null)
  if [ -n "$PR_NUM" ] && [ "$PR_NUM" != "null" ] && [ "$PR_NUM" != "none" ]; then
    echo ""
    echo -e "${BOLD}PR #$PR_NUM:${RESET}"
    # CI checks
    CI_OUT=$(gh pr checks "$PR_NUM" 2>/dev/null || echo "  (unavailable)")
    echo "$CI_OUT" | head -8 | while IFS= read -r line; do
      if echo "$line" | grep -q "pass"; then
        echo -e "  ${GREEN}$line${RESET}"
      elif echo "$line" | grep -q "fail"; then
        echo -e "  ${RED}$line${RESET}"
      else
        echo -e "  $line"
      fi
    done
    # Latest review
    REVIEW_SHA=$(gh pr view "$PR_NUM" --json reviews --jq '.reviews[-1].commit.oid // ""' 2>/dev/null | head -c10)
    REVIEW_AT=$(gh pr view "$PR_NUM" --json reviews --jq '.reviews[-1].submittedAt // ""' 2>/dev/null)
    HEAD_SHA=$(git rev-parse HEAD 2>/dev/null | head -c10)
    if [ -n "$REVIEW_SHA" ]; then
      if [ "$REVIEW_SHA" = "$HEAD_SHA" ]; then
        echo -e "  Review: ${GREEN}current-head${RESET} ($REVIEW_SHA at $REVIEW_AT)"
      else
        echo -e "  Review: ${YELLOW}stale${RESET} ($REVIEW_SHA at $REVIEW_AT, HEAD=$HEAD_SHA)"
      fi
    fi
  fi
fi

echo ""
