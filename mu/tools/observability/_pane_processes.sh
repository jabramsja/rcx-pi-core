#!/usr/bin/env bash
# _pane_processes.sh — Process tree pane for pipeline_monitor
REPO_ROOT="$(git rev-parse --show-toplevel)"
while true; do
  clear
  echo "PIPELINE PROCESSES"
  echo "─────────────────"
  pids=$(pgrep -f 'executor_dispatch|commit_executor|phase_b_executor|phase_a_executor|meta_bridge_supervisor|codex.*sandbox' 2>/dev/null || true)
  if [ -n "$pids" ]; then
    for pid in $pids; do
      cmd=$(ps -p "$pid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-70)
      elapsed=$(ps -p "$pid" -o etime= 2>/dev/null | xargs)
      echo "  PID $pid ($elapsed) $cmd"
      children=$(pgrep -P "$pid" 2>/dev/null || true)
      for cpid in $children; do
        ccmd=$(ps -p "$cpid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-60)
        echo "    └─ $cpid $ccmd"
      done
    done
  else
    echo "  (none)"
  fi
  echo ""
  echo "BRIDGE LOCK"
  lock="$REPO_ROOT/.agent_bus/meta/meta_bridge.lock"
  if [ -f "$lock" ]; then
    holder=$(jq -r '.holder' "$lock" 2>/dev/null)
    lpid=$(jq -r '.pid' "$lock" 2>/dev/null)
    if kill -0 "$lpid" 2>/dev/null; then
      echo "  $holder PID $lpid (alive)"
    else
      echo "  $holder PID $lpid (STALE)"
    fi
  else
    echo "  (none)"
  fi
  sleep 5
done
