#!/usr/bin/env bash
# pipeline_status.sh — One-shot pipeline state summary
# Read-only: never modifies state, only reads .agent_bus/ and process info.
set -uo pipefail

find_worktree_for_branch() {
  local target="$1"
  local current_path="" current_branch="" match="" matches=0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      worktree\ *)
        current_path="${line#worktree }"
        current_branch=""
        ;;
      branch\ refs/heads/*)
        current_branch="${line#branch refs/heads/}"
        if [ "$current_branch" = "$target" ] && [ -n "$current_path" ]; then
          match="$current_path"
          matches=$((matches + 1))
        fi
        ;;
      "")
        current_path=""
        current_branch=""
        ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null || true)

  if [ "$matches" -eq 1 ] && [ -n "$match" ]; then
    printf '%s\n' "$match"
    return 0
  fi
  return 1
}

resolve_repo_root() {
  local root="" branch=""
  if root="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -n "$branch" ]; then
    root="$(find_worktree_for_branch "$branch" || true)"
    if [ -n "$root" ]; then
      printf '%s\n' "$root"
      return 0
    fi
  fi

  root="$(find_worktree_for_branch dev || true)"
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  pwd
}

REPO_ROOT="$(resolve_repo_root)"
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
LOCK2="$BUS/bridge.lock"
_show_lock_status() {
  local lock="$1" label="$2"
  if [ ! -f "$lock" ]; then return 1; fi
  if [ ! -s "$lock" ]; then return 1; fi  # empty = released
  local holder lock_pid
  holder=$(jq -r '.holder // "unknown"' "$lock" 2>/dev/null) || return 1
  lock_pid=$(jq -r '.pid // "0"' "$lock" 2>/dev/null) || return 1
  if [ "$lock_pid" != "0" ] && kill -0 "$lock_pid" 2>/dev/null; then
    echo -e "${CYAN}Bridge:${RESET} ${YELLOW}LOCKED${RESET} by $holder (PID $lock_pid, alive)"
  else
    echo -e "${CYAN}Bridge:${RESET} ${RED}STALE LOCK${RESET} by $holder (PID $lock_pid, dead)"
  fi
  return 0
}
_show_lock_status "$LOCK" "meta" || _show_lock_status "$LOCK2" "bridge" || \
  echo -e "${CYAN}Bridge:${RESET} idle (no lock)"

# ── Active Processes ──
echo ""
EXEC_PIDS=$(pgrep -f "executor_dispatch\|commit_executor\|phase_b_executor\|phase_a_executor\|meta_bridge_supervisor" 2>/dev/null || true)
if [ -n "$EXEC_PIDS" ]; then
  echo -e "${BOLD}Active Processes:${RESET}"
  for pid in $EXEC_PIDS; do
    FULL_CMD=$(ps -p "$pid" -o command= 2>/dev/null)
    case "$FULL_CMD" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*"_pane_"*|*"pipeline_monitor.sh"*)
        continue
        ;;
    esac
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
