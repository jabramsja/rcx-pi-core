#!/usr/bin/env bash
# pipeline_monitor.sh — Real-time pipeline observability via tmux
# Read-only by default. Action commands (clear-lock, nudge, kill) are explicit.
set -euo pipefail

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
SESSION="rcx-pipeline"
LIVE_LOG="/tmp/rcx_pipeline_live.txt"

usage() {
  cat <<'EOF'
Usage: pipeline_monitor.sh <command> [options]

Dashboard:
  start [--detach]         Launch tmux monitoring session
  stop                     Kill the monitoring session
  attach                   Attach to existing session
  status                   One-shot status (no tmux)

Run executors with live output in tmux:
  exec <command...>        Run command with tee to tmux live pane

Actions (safe one-shot commands):
  clear-lock               Remove stale bridge lock (checks PID first)
  nudge <pr-number>        Post @codex review on a PR
  kill <pid>               Kill a stale pipeline process

┌──────────────────────┬──────────────────────┐
│ Live Output (auto)   │ Review Findings      │
├──────────────────────┼──────────────────────┤
│ Status + Activity    │ Session Timeline     │
└──────────────────────┴──────────────────────┘
EOF
  exit "${1:-0}"
}

# ── Auto-switching log watcher ──
# Writes a helper script that continuously finds and tails the newest log,
# switching when a newer one appears (new stage started).
write_log_watcher() {
  cat <<'WATCHER_EOF'
#!/usr/bin/env bash
# Resilient: never exits on transient errors
set +e  # Do not exit on error
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
LIVE_LOG="/tmp/rcx_pipeline_live.txt"
current_log=""
tail_pid=""

find_newest_log() {
  local log=""
  # Live tee output (from 'exec' command) takes priority
  if [ -f "$LIVE_LOG" ]; then
    local mtime
    mtime=$(stat -f%m "$LIVE_LOG" 2>/dev/null || stat -c%Y "$LIVE_LOG" 2>/dev/null || echo 0)
    local age=$(( $(date +%s) - mtime ))
    if [ "$age" -lt 300 ]; then
      echo "$LIVE_LOG"
      return
    fi
  fi
  # Collect all recent pipeline logs and pick the most recently modified.
  # Avoids pinning to idle executor log while subprocess logs are still active.
  local newest=""
  newest=$(ls -t \
    "$REPO_ROOT"/.scratch/commit_executor_live.log \
    "$REPO_ROOT"/.scratch/phase_a_executor_live.log \
    "$REPO_ROOT"/.scratch/phase_b_executor_live.log \
    "$REPO_ROOT"/.scratch/phase_a_agent_review_*.stdout.log \
    "$REPO_ROOT"/.scratch/phase_a_bridge_*.stdout.log \
    "$REPO_ROOT"/.scratch/phase_b_bridge_*.stdout.log \
    "$REPO_ROOT"/.scratch/phase_b_agent_review_*.stdout.log \
    /tmp/phase_b_*.txt /tmp/commit_*.txt /tmp/phase_a_*.txt \
    2>/dev/null | head -1) || true
  if [ -n "$newest" ]; then
    local file_age=$(( $(date +%s) - $(stat -f%m "$newest" 2>/dev/null || stat -c%Y "$newest" 2>/dev/null || echo 0) ))
    if [ "$file_age" -lt 300 ]; then
      echo "$newest"
      return
    fi
  fi
  echo ""
}

switch_tail() {
  local new_log="$1"
  if [ -n "$tail_pid" ] && kill -0 "$tail_pid" 2>/dev/null; then
    kill "$tail_pid" 2>/dev/null || true
    wait "$tail_pid" 2>/dev/null || true
  fi
  tail_pid=""
  if [ -f "$new_log" ]; then
    printf '\033[1;36m── %s ──\033[0m\n' "$(basename "$new_log")"
    tail -f "$new_log" &
    tail_pid=$!
    current_log="$new_log"
  fi
}

echo "Auto-switching log watcher — scanning for active logs..."
while true; do
  newest=$(find_newest_log) || newest=""
  if [ -n "$newest" ] && [ "$newest" != "$current_log" ]; then
    switch_tail "$newest"
  elif [ -z "$newest" ] && [ -z "$current_log" ]; then
    printf '\r\033[2mWaiting for pipeline activity...\033[0m'
  fi
  # Check if tail process died (file deleted/truncated)
  if [ -n "$tail_pid" ] && ! kill -0 "$tail_pid" 2>/dev/null; then
    tail_pid=""
    current_log=""
  fi
  sleep 3
done
WATCHER_EOF
}

cmd_start() {
  local detach=false
  while [ $# -gt 0 ]; do
    case "$1" in
      --detach) detach=true; shift ;;
      *) echo "Unknown option: $1"; usage 1 ;;
    esac
  done

  # Kill existing session if any
  tmux kill-session -t "$SESSION" 2>/dev/null || true

  # Write the log watcher script
  local watcher="/tmp/rcx_log_watcher.sh"
  write_log_watcher > "$watcher"
  chmod +x "$watcher"

  # Create session
  tmux new-session -d -s "$SESSION"
  local W="$SESSION:1"  # window 1 (base-index=1 on macOS)

  local OBS_DIR="$REPO_ROOT/mu/tools/observability"

  # Pane 1 (top-left): Auto-switching live output
  tmux send-keys -t "$W" "cd '$REPO_ROOT' && bash '$watcher'" Enter

  # Split horizontally → pane 2 (right): Review Findings
  tmux split-window -h -t "$W"
  tmux send-keys "cd '$REPO_ROOT' && bash '$OBS_DIR/_pane_findings.sh'" Enter

  # Split right pane vertically → pane 3 (bottom-right): Session Timeline
  tmux split-window -v -t "$W"
  tmux send-keys "cd '$REPO_ROOT' && bash '$OBS_DIR/_pane_timeline.sh'" Enter

  # Select left pane (pane 1) and split vertically → pane 4 (bottom-left): Status + Activity
  tmux select-pane -t "$W.1"
  tmux split-window -v -t "$W"
  tmux send-keys "cd '$REPO_ROOT' && bash '$OBS_DIR/_pane_processes.sh'" Enter

  # Select top-left pane for initial focus
  tmux select-pane -t "$W.1"

  echo "Pipeline monitor started (session: $SESSION)"
  if [ "$detach" = false ]; then
    echo "Attaching... (detach with Ctrl-b d)"
    tmux attach-session -t "$SESSION"
  else
    echo "Detached. Attach with: tmux attach-session -t $SESSION"
  fi
}

cmd_stop() {
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    echo "Pipeline monitor stopped."
  else
    echo "No active pipeline monitor session."
  fi
}

cmd_attach() {
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux attach-session -t "$SESSION"
  else
    echo "No active session. Start with: pipeline_monitor.sh start"
    exit 1
  fi
}

cmd_status() {
  exec "$REPO_ROOT/mu/tools/observability/pipeline_status.sh"
}

# ── exec: Run a command with live tee to tmux ──
cmd_exec() {
  if [ $# -eq 0 ]; then
    echo "Usage: pipeline_monitor.sh exec <command...>"
    exit 1
  fi
  # Touch the live log so the tmux watcher picks it up
  : > "$LIVE_LOG"
  echo "Output streaming to tmux monitor via $LIVE_LOG"
  echo "───────────────────────────────────────────────"
  # Run with tee — output goes to both this terminal and the live log
  "$@" 2>&1 | tee "$LIVE_LOG"
}

# ── clear-lock: Remove stale bridge locks ──
cmd_clear_lock() {
  local found=false
  for lock in "$REPO_ROOT/.agent_bus/meta/meta_bridge.lock" "$REPO_ROOT/.agent_bus/bridge.lock"; do
    if [ ! -f "$lock" ]; then
      continue
    fi
    # Empty file = properly released lock, not stale
    if [ ! -s "$lock" ]; then
      continue
    fi
    found=true
    local pid label
    label=$(basename "$lock")
    pid=$(jq -r '.pid // "0"' "$lock" 2>/dev/null) || pid="0"
    if [ "$pid" != "0" ] && kill -0 "$pid" 2>/dev/null; then
      echo "$label: holder PID $pid is ALIVE. Not removing."
      continue
    fi
    rm -f "$lock"
    echo "$label: stale lock removed (PID $pid was dead)."
  done
  if [ "$found" = false ]; then
    echo "No stale bridge locks."
  fi
}

# ── nudge: Post @codex review on a PR ──
cmd_nudge() {
  local pr="${1:-}"
  if [ -z "$pr" ]; then
    # Auto-detect from executor state
    pr=$(ls -t "$REPO_ROOT/.agent_bus/executors/commit_executor_"*.json 2>/dev/null | head -1 | xargs jq -r '.pr_number // empty' 2>/dev/null)
    if [ -z "$pr" ]; then
      echo "Usage: pipeline_monitor.sh nudge <pr-number>"
      exit 1
    fi
  fi
  echo "Posting @codex review on PR #$pr..."
  gh pr comment "$pr" --body "@codex review"
  echo "Done. Connector typically responds in 3-8 minutes."
}

# ── kill: Kill a stale pipeline process ──
cmd_kill() {
  local pid="${1:-}"
  if [ -z "$pid" ]; then
    echo "Usage: pipeline_monitor.sh kill <pid>"
    echo ""
    echo "Active pipeline processes:"
    pgrep -f 'executor_dispatch|commit_executor|phase_b_executor|phase_a_executor|meta_bridge_supervisor' 2>/dev/null | while read p; do
      ps -p "$p" -o pid=,etime=,command= 2>/dev/null | sed 's|.*/||' | cut -c1-80
    done
    exit 1
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "PID $pid is not running."
    return 1
  fi
  echo "Killing PID $pid..."
  kill "$pid"
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Still alive, sending SIGKILL..."
    kill -9 "$pid" 2>/dev/null || true
  fi
  echo "Done."
}

# Main dispatch
case "${1:-}" in
  start)       shift; cmd_start "$@" ;;
  stop)        cmd_stop ;;
  attach)      cmd_attach ;;
  status)      cmd_status ;;
  exec)        shift; cmd_exec "$@" ;;
  clear-lock)  cmd_clear_lock ;;
  nudge)       shift; cmd_nudge "$@" ;;
  kill)        shift; cmd_kill "$@" ;;
  -h|--help)   usage 0 ;;
  "")          usage 1 ;;
  *)           echo "Unknown command: $1"; usage 1 ;;
esac
