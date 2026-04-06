#!/usr/bin/env bash
set -euo pipefail

file_mtime_seconds() {
  local path="$1"
  stat -f%m "$path" 2>/dev/null || stat -c%Y "$path" 2>/dev/null || echo 0
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

worktree_score() {
  local root="$1" best=0 candidate="" mtime=0
  for candidate in \
    "$root/.scratch/phase_a_executor_live.log" \
    "$root/.scratch/phase_b_executor_live.log" \
    "$root/.scratch/commit_executor_live.log" \
    "$root/.agent_bus/recovery/recovery_status.json" \
    "$root/.agent_bus/executors/phase_b_state.json"
  do
    [ -f "$candidate" ] || continue
    mtime=$(file_mtime_seconds "$candidate")
    [ "$mtime" -gt "$best" ] && best="$mtime"
  done

  candidate=$(ls -t \
    "$root"/.agent_bus/raw/phase-?-r[0-9]*/*reviewer*.txt \
    "$root"/.agent_bus/raw/phase-?-reentry-r[0-9]*/*reviewer*.txt \
    "$root"/.scratch/phase_a_agent_review_*.status.json \
    "$root"/.scratch/phase_b_agent_review_*.status.json \
    2>/dev/null | head -1) || true
  if [ -n "$candidate" ]; then
    mtime=$(file_mtime_seconds "$candidate")
    [ "$mtime" -gt "$best" ] && best="$mtime"
  fi

  printf '%s\n' "$best"
}

CURRENT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
CURRENT_ROOT="$(normalize_path "$CURRENT_ROOT")"

BEST_ROOT="$CURRENT_ROOT"
BEST_SCORE="$(worktree_score "$CURRENT_ROOT")"

while IFS= read -r path; do
  [ -n "$path" ] || continue
  path="$(normalize_path "$path")"
  score="$(worktree_score "$path")"
  if [ "$score" -gt "$BEST_SCORE" ] 2>/dev/null; then
    BEST_ROOT="$path"
    BEST_SCORE="$score"
  fi
done < <(list_linked_worktrees)

printf '%s\n' "$BEST_ROOT"
