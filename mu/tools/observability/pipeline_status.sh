#!/usr/bin/env bash
# pipeline_status.sh — One-shot pipeline state summary
# Read-only: never modifies state, only reads .agent_bus/ and process info.
set -uo pipefail

LIVE_STATE_MAX_AGE_SECONDS=21600

file_mtime_seconds() {
  local path="$1"
  stat -f%m "$path" 2>/dev/null || stat -c%Y "$path" 2>/dev/null || echo ""
}

file_age_seconds() {
  local path="$1"
  local mtime="" now=""
  mtime=$(file_mtime_seconds "$path")
  [ -n "$mtime" ] || return 1
  now=$(date +%s)
  printf '%s\n' "$((now - mtime))"
}

file_is_recent() {
  local path="$1" age=""
  age=$(file_age_seconds "$path" 2>/dev/null || true)
  [ -n "$age" ] || return 1
  [ "$age" -le "$LIVE_STATE_MAX_AGE_SECONDS" ]
}

lock_file_is_live() {
  local lock="$1" lock_pid=""
  [ -s "$lock" ] || return 1
  lock_pid=$(jq -r '.pid // "0"' "$lock" 2>/dev/null || printf '0')
  if [ "$lock_pid" != "0" ] && kill -0 "$lock_pid" 2>/dev/null; then
    return 0
  fi
  file_is_recent "$lock"
}

list_linked_worktrees() {
  local current_path="" is_bare=false
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      worktree\ *)
        current_path="${line#worktree }"
        is_bare=false
        ;;
      bare)
        is_bare=true
        ;;
      "")
        if [ "$is_bare" = false ] && [ -n "$current_path" ]; then
          printf '%s\n' "$current_path"
        fi
        current_path=""
        is_bare=false
        ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null || true)

  if [ "$is_bare" = false ] && [ -n "$current_path" ]; then
    printf '%s\n' "$current_path"
  fi
}

normalize_path() {
  local path="$1"
  (
    cd "$path" 2>/dev/null && pwd -P
  ) || printf '%s\n' "$path"
}

pid_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

pid_matches_worktree() {
  local pid="$1" path="$2" cmd="" cwd="" normalized=""
  normalized="$(normalize_path "$path")"
  cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
  case "$cmd" in
    *"tail -f "*|*"rcx_log_watcher.sh"*|*"_pane_"*|*"pipeline_monitor.sh"*)
      return 1
      ;;
  esac
  case "$cmd" in
    *"$normalized"/*|*"$normalized "'*|*"$normalized\""*|*"$normalized"\'*|*"$normalized") return 0 ;;
  esac
  cwd="$(pid_cwd "$pid")"
  [ -n "$cwd" ] && [ "$(normalize_path "$cwd")" = "$normalized" ]
}

worktree_has_live_process() {
  local path="$1" pid=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    pid_matches_worktree "$pid" "$path" && return 0
  done < <(
    pgrep -f \
      'executor_dispatch|commit_executor|phase_b_executor|phase_a_executor|meta_bridge_supervisor|bridge_supervisor|claude.*--print|run_review.py|codex.*exec.*gpt' \
      2>/dev/null || true
  )
  return 1
}

branch_for_worktree_path() {
  local target="$1" normalized_target="" current_path="" current_branch="" normalized_current=""
  normalized_target="$(normalize_path "$target")"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      worktree\ *)
        current_path="${line#worktree }"
        current_branch=""
        ;;
      branch\ refs/heads/*)
        current_branch="${line#branch refs/heads/}"
        ;;
      "")
        if [ -n "$current_path" ] && [ -n "$current_branch" ]; then
          normalized_current="$(normalize_path "$current_path")"
          if [ "$normalized_current" = "$normalized_target" ]; then
            printf '%s\n' "$current_branch"
            return 0
          fi
        fi
        current_path=""
        current_branch=""
        ;;
    esac
  done < <(git worktree list --porcelain 2>/dev/null || true)

  if [ -n "$current_path" ] && [ -n "$current_branch" ]; then
    normalized_current="$(normalize_path "$current_path")"
    if [ "$normalized_current" = "$normalized_target" ]; then
      printf '%s\n' "$current_branch"
      return 0
    fi
  fi

  return 1
}

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

worktree_activity_timestamp() {
  local path="$1"
  local lock=""
  local best=0
  local signal=""
  local reviewer=""
  local commit_state=""
  local status=""
  local mtime=""

  if worktree_has_live_process "$path"; then
    best=$(( $(date +%s) + LIVE_STATE_MAX_AGE_SECONDS + 1 ))
  fi

  for lock in "$path/.agent_bus/meta/meta_bridge.lock" "$path/.agent_bus/bridge.lock"; do
    if lock_file_is_live "$lock"; then
      mtime=$(file_mtime_seconds "$lock")
      if [ -n "$mtime" ] && [ "$mtime" -gt "$best" ]; then
        best="$mtime"
      fi
    fi
  done

  if [ -s "$path/.agent_bus/meta/continuation.json" ] && file_is_recent "$path/.agent_bus/meta/continuation.json"; then
    mtime=$(file_mtime_seconds "$path/.agent_bus/meta/continuation.json")
    if [ -n "$mtime" ] && [ "$mtime" -gt "$best" ]; then
      best="$mtime"
    fi
  fi

  commit_state=$(ls -t "$path"/.agent_bus/executors/commit_executor_*.json 2>/dev/null | head -1) || true
  if [ -n "$commit_state" ]; then
    status=$(jq -r '.status // ""' "$commit_state" 2>/dev/null || true)
    case "$status" in
      ""|success|held|error)
        ;;
      *)
        if file_is_recent "$commit_state"; then
          mtime=$(file_mtime_seconds "$commit_state")
          if [ -n "$mtime" ] && [ "$mtime" -gt "$best" ]; then
            best="$mtime"
          fi
        fi
        ;;
    esac
  fi

  for signal in \
    "$path/.agent_bus/executors/phase_b_state.json" \
    "$path/.agent_bus/recovery/recovery_status.json" \
    "$path/.scratch/phase_a_executor_live.log" \
    "$path/.scratch/phase_b_executor_live.log" \
    "$path/.scratch/commit_executor_live.log"
  do
    if [ -f "$signal" ] && file_is_recent "$signal"; then
      mtime=$(file_mtime_seconds "$signal")
      if [ -n "$mtime" ] && [ "$mtime" -gt "$best" ]; then
        best="$mtime"
      fi
    fi
  done

  reviewer=$(ls -t \
    "$path"/.agent_bus/raw/phase-?-r[0-9]*/*reviewer*.txt \
    "$path"/.agent_bus/raw/phase-?-reentry-r[0-9]*/*reviewer*.txt \
    2>/dev/null | head -1) || true
  if [ -n "$reviewer" ] && file_is_recent "$reviewer"; then
    mtime=$(file_mtime_seconds "$reviewer")
    if [ -n "$mtime" ] && [ "$mtime" -gt "$best" ]; then
      best="$mtime"
    fi
  fi

  printf '%s\n' "$best"
}

worktree_has_live_pipeline_state() {
  local ts=""
  ts=$(worktree_activity_timestamp "$1" 2>/dev/null || echo 0)
  [ -n "$ts" ] && [ "$ts" -gt 0 ] 2>/dev/null
}

find_active_worktree() {
  local best_path="" best_score=0 path="" score=0

  while IFS= read -r path; do
    [ -z "$path" ] && continue
    score=$(worktree_activity_timestamp "$path" 2>/dev/null || echo 0)
    [ -n "$score" ] || score=0
    if [ "$score" -gt "$best_score" ] 2>/dev/null; then
      best_path="$path"
      best_score="$score"
    fi
  done < <(list_linked_worktrees)

  if [ -n "$best_path" ] && [ "$best_score" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$best_path"
    return 0
  fi
  return 1
}

find_sole_linked_worktree() {
  local match="" matches=0

  while IFS= read -r path; do
    [ -z "$path" ] && continue
    match="$path"
    matches=$((matches + 1))
  done < <(list_linked_worktrees)

  if [ "$matches" -eq 1 ] && [ -n "$match" ]; then
    printf '%s\n' "$match"
    return 0
  fi
  return 1
}

print_branch_for_root() {
  local target_root="$1" branch_name=""
  branch_name="$(branch_for_worktree_path "$target_root" || true)"
  if [ -z "$branch_name" ]; then
    branch_name="$(git -C "$target_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
  fi
  printf '%s\n' "$branch_name"
}

if [ "${1:-}" = "--print-branch-for-root" ]; then
  if [ -z "${2:-}" ]; then
    echo "ERROR: --print-branch-for-root requires a path" >&2
    exit 1
  fi
  print_branch_for_root "$2"
  exit 0
fi

resolve_observability_repo_root() {
  local root="" branch="" current_root="" current_score=0 best_score=0 branch_root="" branch_score=0
  if current_root="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -n "$current_root" ]; then
    current_score=$(worktree_activity_timestamp "$current_root" 2>/dev/null || echo 0)
    root="$(find_active_worktree || true)"
    if [ -n "$root" ]; then
      best_score=$(worktree_activity_timestamp "$root" 2>/dev/null || echo 0)
      if [ "$current_score" -ge "$best_score" ] 2>/dev/null && [ "$current_score" -gt 0 ] 2>/dev/null; then
        printf '%s\n' "$current_root"
        return 0
      fi
      printf '%s\n' "$root"
      return 0
    fi

    printf '%s\n' "$current_root"
    return 0
  fi

  branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -n "$branch" ]; then
    branch_root="$(find_worktree_for_branch "$branch" || true)"
    if [ -n "$branch_root" ]; then
      branch_score=$(worktree_activity_timestamp "$branch_root" 2>/dev/null || echo 0)
    fi
  fi

  if root="$(find_active_worktree)"; then
    if [ -n "$root" ]; then
      best_score=$(worktree_activity_timestamp "$root" 2>/dev/null || echo 0)
      if [ -n "$branch_root" ] && [ "$branch_score" -ge "$best_score" ] 2>/dev/null; then
        printf '%s\n' "$branch_root"
        return 0
      fi
      printf '%s\n' "$root"
      return 0
    fi
  fi

  if [ -n "$branch_root" ]; then
    printf '%s\n' "$branch_root"
    return 0
  fi

  root="$(find_sole_linked_worktree || true)"
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  root="$(find_worktree_for_branch dev || true)"
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  echo "ERROR: cannot resolve repo root — no exact branch worktree, unique active pipeline worktree, sole linked worktree, or unique dev worktree found for '${branch:-<detached>}'" >&2
  return 1
}

if ! REPO_ROOT="$(resolve_observability_repo_root)"; then
  exit 1
fi

if [ "${1:-}" = "--print-root" ]; then
  printf '%s\n' "$REPO_ROOT"
  exit 0
fi

if [ "${1:-}" = "--print-branch" ]; then
  print_branch_for_root "$REPO_ROOT"
  exit 0
fi

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
printed_process=false
if [ -n "$EXEC_PIDS" ]; then
  for pid in $EXEC_PIDS; do
    FULL_CMD=$(ps -p "$pid" -o command= 2>/dev/null)
    [ -n "$FULL_CMD" ] || continue
    case "$FULL_CMD" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*"_pane_"*|*"pipeline_monitor.sh"*)
        continue
        ;;
    esac
    if [ "$printed_process" = false ]; then
      echo -e "${BOLD}Active Processes:${RESET}"
      printed_process=true
    fi
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
fi
if [ "$printed_process" = false ]; then
  echo -e "${DIM}No active pipeline processes${RESET}"
fi

# ── Recovery ──
if [ -f "$REPO_ROOT/mu/tools/observability/pipeline_dashboard.py" ]; then
  echo ""
  python3 "$REPO_ROOT/mu/tools/observability/pipeline_dashboard.py" \
    --render-recovery \
    --repo-root "$REPO_ROOT" 2>/dev/null || true
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
