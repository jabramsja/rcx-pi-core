#!/usr/bin/env bash
# pipeline_monitor.sh — Real-time pipeline observability via tmux
# Read-only by default. Action commands (clear-lock, nudge, kill) are explicit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS_SCRIPT="$SCRIPT_DIR/pipeline_status.sh"

resolve_observability_repo_root() {
  local root="" current_root=""
  current_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$current_root" ]; then
    printf '%s\n' "$current_root"
    return 0
  fi
  if [ -f "$STATUS_SCRIPT" ]; then
    root=$(bash "$STATUS_SCRIPT" --print-root 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  return 1
}

if ! REPO_ROOT="$(resolve_observability_repo_root)"; then
  echo "ERROR: cannot resolve repo root" >&2
  exit 1
fi
SESSION="rcx-pipeline"
LIVE_LOG="/tmp/rcx_pipeline_live.txt"
SESSION_WIDTH="${RCX_PIPELINE_TMUX_WIDTH:-240}"
SESSION_HEIGHT="${RCX_PIPELINE_TMUX_HEIGHT:-70}"

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
LIVE_LOG="/tmp/rcx_pipeline_live.txt"
# Keep the freshest real phase log visible for longer after a run ends so the
# monitor still shows the last live failure/success instead of blanking almost
# immediately.
IDLE_WINDOW_SECONDS=3600
current_log=""
tail_pid=""

resolve_repo_root() {
  local root=""
  if [ -n "${RCX_OBS_ROOT_HELPER:-}" ] && [ -f "${RCX_OBS_ROOT_HELPER:-}" ]; then
    root=$(bash "$RCX_OBS_ROOT_HELPER" 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  if [ -n "${RCX_OBS_REPO_ROOT:-}" ] && [ -d "${RCX_OBS_REPO_ROOT:-}" ]; then
    (
      cd "${RCX_OBS_REPO_ROOT}" 2>/dev/null && pwd -P
    ) || printf '%s\n' "${RCX_OBS_REPO_ROOT}"
    return 0
  fi
  if [ -n "${RCX_OBS_STATUS_SCRIPT:-}" ] && [ -f "${RCX_OBS_STATUS_SCRIPT:-}" ]; then
    root=$(bash "$RCX_OBS_STATUS_SCRIPT" --print-root 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

resolve_branch_name() {
  local repo_root=""
  repo_root="$(resolve_repo_root)"
  [ -n "$repo_root" ] || {
    echo "unknown"
    return 0
  }
  git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}

file_mtime_seconds() {
  local path="$1"
  stat -f%m "$path" 2>/dev/null || stat -c%Y "$path" 2>/dev/null || echo 0
}

file_is_recent() {
  local path="$1"
  [ -f "$path" ] || return 1
  local age=$(( $(date +%s) - $(file_mtime_seconds "$path") ))
  [ "$age" -lt "$IDLE_WINDOW_SECONDS" ]
}

find_newest_log() {
  local log=""
  local repo_root=""
  # Live tee output (from 'exec' command) takes priority
  if file_is_recent "$LIVE_LOG"; then
    echo "$LIVE_LOG"
    return
  fi
  # Collect all recent pipeline logs and pick the most recently modified.
  # Avoids pinning to idle executor log while subprocess logs are still active.
  repo_root="$(resolve_repo_root)"
  [ -n "$repo_root" ] || return
  local newest=""
  newest=$(ls -t \
    "$repo_root"/.scratch/commit_executor_live.log \
    "$repo_root"/.scratch/phase_a_executor_live.log \
    "$repo_root"/.scratch/phase_b_executor_live.log \
    "$repo_root"/.scratch/phase_b_implementer_output_*.txt \
    "$repo_root"/.scratch/phase_a_agent_review_*.stdout.log \
    "$repo_root"/.scratch/phase_a_bridge_*.stdout.log \
    "$repo_root"/.scratch/phase_b_bridge_*.stdout.log \
    "$repo_root"/.scratch/phase_b_bridge_*.stderr.log \
    "$repo_root"/.scratch/phase_b_agent_review_*.stdout.log \
    /tmp/phase_b_*.txt /tmp/commit_*.txt /tmp/phase_a_*.txt \
    2>/dev/null | head -1) || true
  if [ -n "$newest" ] && file_is_recent "$newest"; then
    echo "$newest"
    return
  fi
  echo ""
}

stop_tail() {
  if [ -n "$tail_pid" ] && kill -0 "$tail_pid" 2>/dev/null; then
    kill "$tail_pid" 2>/dev/null || true
    wait "$tail_pid" 2>/dev/null || true
  fi
  tail_pid=""
  current_log=""
}

render_idle_screen() {
  local repo_root="" branch="" now=""
  repo_root="$(resolve_repo_root)"
  branch="$(resolve_branch_name)"
  now="$(date '+%H:%M:%S')"
  printf '\033[H\033[2J\033[3J'
  printf '\033[1;36mPane 1: live pipeline log\033[0m  %s\n' "$now"
  echo ""
  echo "  This pane shows the raw live log from the active phase."
  echo "  No active pipeline log in the last 5 minutes."
  echo "  The last wave finished or went quiet."
  echo ""
  echo "  Branch: $branch"
  echo "  Worktree: $repo_root"
  echo ""
  echo "  This pane will switch automatically when the next phase starts."
}

switch_tail() {
  local new_log="$1"
  stop_tail
  if [ -f "$new_log" ]; then
    printf '\033[H\033[2J\033[3J'
    printf '\033[1;36mPane 1: live pipeline log\033[0m\n'
    printf '\033[1;36m── %s ──\033[0m\n' "$(basename "$new_log")"
    tail -f "$new_log" &
    tail_pid=$!
    current_log="$new_log"
  fi
}

while true; do
  newest=$(find_newest_log) || newest=""
  if [ -n "$newest" ] && [ "$newest" != "$current_log" ]; then
    switch_tail "$newest"
  elif [ -z "$newest" ]; then
    if [ -n "$current_log" ]; then
      stop_tail
    fi
    render_idle_screen
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

  local OBS_DIR="$REPO_ROOT/mu/tools/observability"
  local repo_q="" obs_q="" watcher_q="" status_q="" root_helper_q=""
  printf -v repo_q '%q' "$REPO_ROOT"
  printf -v obs_q '%q' "$OBS_DIR"
  printf -v watcher_q '%q' "$watcher"
  printf -v status_q '%q' "$OBS_DIR/pipeline_status.sh"
  printf -v root_helper_q '%q' "$OBS_DIR/_resolve_live_root.sh"

  local pane1_cmd=""
  local pane2_cmd=""
  local pane3_cmd=""
  local pane4_cmd=""
  # Do not pin panes to the launcher worktree. Let each pane re-resolve the
  # freshest active pipeline worktree on every refresh so tmux stays honest
  # when the real run lives in a different linked worktree.
  pane1_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $watcher_q"
  pane2_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_findings.sh"
  pane3_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_processes.sh"
  pane4_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_timeline.sh"

  # Create session
  tmux new-session -d -x "$SESSION_WIDTH" -y "$SESSION_HEIGHT" -s "$SESSION" "$pane1_cmd"
  local W=""
  local pane1_id="" pane2_id="" pane3_id="" pane4_id=""
  # Resolve the new window and active pane from tmux itself instead of assuming
  # window .1 or pane .1. This keeps startup working across base-index and
  # pane-base-index variants.
  W="$(tmux display-message -p -t "$SESSION" '#{window_id}')"
  pane1_id="$(tmux display-message -p -t "$W" '#{pane_id}')"

  # Build the layout as a vertical split first, then split each row
  # horizontally. On tmux/macOS this yields founder-facing pane numbers in the
  # natural reading order: 1 top-left, 2 top-right, 3 bottom-left, 4 bottom-right.
  local bottom_row_id=""

  # Split vertically → bottom row placeholder (becomes pane 3 after the row split)
  bottom_row_id="$(tmux split-window -v -t "$pane1_id" -P -F '#{pane_id}' "$pane3_cmd")"

  # Split the top row horizontally → pane 2 (top-right): Review Findings
  pane2_id="$(tmux split-window -h -t "$pane1_id" -P -F '#{pane_id}' "$pane2_cmd")"

  # The original bottom row becomes pane 3 (bottom-left): Plain-English Status
  pane3_id="$bottom_row_id"

  # Split the bottom row horizontally → pane 4 (bottom-right): Session Timeline
  pane4_id="$(tmux split-window -h -t "$pane3_id" -P -F '#{pane_id}' "$pane4_cmd")"

  # Select top-left pane for initial focus
  tmux select-pane -t "$pane1_id"
  tmux setw -t "$W" aggressive-resize on
  tmux setw -t "$W" pane-border-status top
  tmux setw -t "$W" pane-border-format '#{pane_title}'
  # Use stable pane ids here even though the split order now matches the
  # founder-facing visual 1/2/3/4 layout. The ids keep title binding honest.
  tmux select-pane -t "$pane1_id" -T "PANE 1 · LIVE PIPELINE LOG"
  tmux select-pane -t "$pane2_id" -T "PANE 2 · REVIEW FINDINGS"
  tmux select-pane -t "$pane3_id" -T "PANE 3 · PLAIN-ENGLISH STATUS"
  tmux select-pane -t "$pane4_id" -T "PANE 4 · SESSION TIMELINE"
  tmux select-pane -t "$pane1_id"

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
  exec env -u RCX_OBS_REPO_ROOT "$STATUS_SCRIPT"
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
