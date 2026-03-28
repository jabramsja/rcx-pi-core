#!/usr/bin/env bash
# pipeline_monitor.sh — Real-time pipeline observability via tmux
# Read-only: never modifies state, only reads .agent_bus/, processes, and GitHub.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SESSION="rcx-pipeline"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [options]

Commands:
  start [--log <path>] [--detach]   Launch tmux monitoring session
  stop                              Kill the monitoring session
  attach                            Attach to existing session
  status                            One-shot status (no tmux)

Options:
  --log <path>    Specific log file to tail (auto-detected if omitted)
  --detach        Start session without attaching

The monitor creates a tmux session with 4 panes:
  ┌──────────────────┬──────────────────┐
  │ Executor Output  │ Pipeline State   │
  ├──────────────────┼──────────────────┤
  │ Process Tree     │ PR / CI Status   │
  └──────────────────┴──────────────────┘
EOF
  exit "${1:-0}"
}

find_executor_log() {
  # Auto-detect the most recent executor/bridge stdout log
  local log=""
  # Check .scratch for phase_b stdout logs
  log=$(ls -t "$REPO_ROOT"/.scratch/phase_b_bridge_*.stdout.log 2>/dev/null | head -1)
  [ -n "$log" ] && echo "$log" && return
  # Check .scratch for agent review logs
  log=$(ls -t "$REPO_ROOT"/.scratch/phase_b_agent_review_*.stdout.log 2>/dev/null | head -1)
  [ -n "$log" ] && echo "$log" && return
  # Check /tmp for operator-directed logs
  log=$(ls -t /tmp/phase_b_*.txt /tmp/commit_*.txt 2>/dev/null | head -1)
  [ -n "$log" ] && echo "$log" && return
  echo ""
}

cmd_start() {
  local log_path="" detach=false
  while [ $# -gt 0 ]; do
    case "$1" in
      --log) log_path="$2"; shift 2 ;;
      --detach) detach=true; shift ;;
      *) echo "Unknown option: $1"; usage 1 ;;
    esac
  done

  # Kill existing session if any
  tmux kill-session -t "$SESSION" 2>/dev/null || true

  # Auto-detect log if not provided
  if [ -z "$log_path" ]; then
    log_path=$(find_executor_log)
  fi

  # Create session with first pane (Executor Output)
  tmux new-session -d -s "$SESSION" -x 200 -y 50

  # Pane 0 (top-left): Executor Output
  if [ -n "$log_path" ] && [ -f "$log_path" ]; then
    tmux send-keys -t "$SESSION:0.0" "tail -f '$log_path'" Enter
  else
    tmux send-keys -t "$SESSION:0.0" "echo 'No executor log detected. Use: tools/pipeline_monitor.sh start --log <path>'; echo 'Watching for new logs...'; while true; do log=\$(ls -t $REPO_ROOT/.scratch/phase_b_bridge_*.stdout.log /tmp/phase_b_*.txt /tmp/commit_*.txt 2>/dev/null | head -1); if [ -n \"\$log\" ]; then echo \"Found: \$log\"; tail -f \"\$log\"; break; fi; sleep 5; done" Enter
  fi

  # Split horizontally (top-right): Pipeline State
  tmux split-window -h -t "$SESSION:0.0"
  tmux send-keys -t "$SESSION:0.1" "watch -n5 -c '$REPO_ROOT/mu/tools/observability/pipeline_status.sh'" Enter

  # Split pane 0 vertically (bottom-left): Process Tree
  tmux split-window -v -t "$SESSION:0.0"
  tmux send-keys -t "$SESSION:0.2" "watch -n5 'echo \"PIPELINE PROCESSES\"; echo \"─────────────────\"; pgrep -f \"executor_dispatch|commit_executor|phase_b_executor|phase_a_executor|meta_bridge_supervisor|codex.*sandbox|bridge_supervisor\" 2>/dev/null | while read pid; do ps -p \$pid -o pid=,etime=,command= 2>/dev/null | sed \"s|.*/||\" | cut -c1-80; pgrep -P \$pid 2>/dev/null | while read cpid; do echo \"  └─ \$(ps -p \$cpid -o pid=,command= 2>/dev/null | sed \"s|.*/||\" | cut -c1-70)\"; done; done; echo; echo \"BRIDGE LOCK\"; cat $REPO_ROOT/.agent_bus/meta/meta_bridge.lock 2>/dev/null | jq -r \"\\\"  \\(.holder) PID \\(.pid)\\\"\" 2>/dev/null || echo \"  (none)\"'" Enter

  # Split pane 1 vertically (bottom-right): PR / CI Status
  tmux split-window -v -t "$SESSION:0.1"
  tmux send-keys -t "$SESSION:0.3" "watch -n15 'echo \"PR / CI STATUS\"; echo \"──────────────\"; EXEC_FILE=\$(ls -t $REPO_ROOT/.agent_bus/executors/commit_executor_*.json 2>/dev/null | head -1); if [ -n \"\$EXEC_FILE\" ]; then PR=\$(jq -r \".pr_number // \\\"\\\"\" \"\$EXEC_FILE\" 2>/dev/null); if [ -n \"\$PR\" ] && [ \"\$PR\" != \"null\" ]; then echo \"PR #\$PR\"; gh pr checks \"\$PR\" 2>/dev/null | head -8; echo; REVIEW=\$(gh pr view \"\$PR\" --json reviews --jq \".reviews[-1] | \\\"Review: \\(.commit.oid[:10]) \\(.submittedAt) \\(.state)\\\"\" 2>/dev/null); echo \"\$REVIEW\"; echo; COMMENTS=\$(gh api repos/jabramsja/rcx-pi-core/issues/\$PR/comments --jq \".[-3:][] | \\\"\\(.created_at) \\(.body[:40])\\\"\" 2>/dev/null); echo \"Recent comments:\"; echo \"\$COMMENTS\"; else echo \"No PR yet\"; fi; else echo \"No active executor\"; fi'" Enter

  # Balance panes
  tmux select-layout -t "$SESSION" tiled 2>/dev/null || true

  echo "Pipeline monitor started (session: $SESSION)"
  if [ "$detach" = false ]; then
    echo "Attaching... (detach with Ctrl-b d)"
    tmux attach-session -t "$SESSION"
  else
    echo "Detached. Attach with: tools/pipeline_monitor.sh attach"
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
    echo "No active pipeline monitor session. Start with: tools/pipeline_monitor.sh start"
    exit 1
  fi
}

cmd_status() {
  exec "$REPO_ROOT/mu/tools/observability/pipeline_status.sh"
}

# Main dispatch
case "${1:-}" in
  start)   shift; cmd_start "$@" ;;
  stop)    cmd_stop ;;
  attach)  cmd_attach ;;
  status)  cmd_status ;;
  -h|--help) usage 0 ;;
  "") usage 1 ;;
  *) echo "Unknown command: $1"; usage 1 ;;
esac
