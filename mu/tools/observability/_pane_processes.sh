#!/usr/bin/env bash
# _pane_processes.sh — Process tree pane for pipeline_monitor
# Resilient: never exits on transient errors
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
while true; do
  clear
  echo "PIPELINE PROCESSES"
  echo "─────────────────"
  pids=$(pgrep -f 'executor_dispatch|commit_executor|phase_b_executor|phase_a_executor|meta_bridge_supervisor|codex.*sandbox' 2>/dev/null || true)
  if [ -n "$pids" ]; then
    for pid in $pids; do
      cmd=$(ps -p "$pid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-70) || continue
      elapsed=$(ps -p "$pid" -o etime= 2>/dev/null | xargs) || elapsed="?"
      echo "  PID $pid ($elapsed) $cmd"
      children=$(pgrep -P "$pid" 2>/dev/null || true)
      for cpid in $children; do
        ccmd=$(ps -p "$cpid" -o command= 2>/dev/null | sed 's|.*/||' | cut -c1-60) || ccmd="(exited)"
        echo "    └─ $cpid $ccmd"
      done
    done
  else
    echo "  (none)"
  fi
  echo ""
  # Check both lock files
  for lock in "$REPO_ROOT/.agent_bus/meta/meta_bridge.lock" "$REPO_ROOT/.agent_bus/bridge.lock"; do
    label=$(basename "$(dirname "$lock")")/$(basename "$lock")
    if [ -f "$lock" ] && [ -s "$lock" ]; then
      holder=$(jq -r '.holder // "unknown"' "$lock" 2>/dev/null) || holder="?"
      lpid=$(jq -r '.pid // "0"' "$lock" 2>/dev/null) || lpid="0"
      if [ "$lpid" != "0" ] && kill -0 "$lpid" 2>/dev/null; then
        echo "LOCK ($label): $holder PID $lpid (alive)"
      else
        echo "LOCK ($label): $holder PID $lpid (STALE)"
      fi
    fi
  done
  # Show if lock files exist but are empty (released normally)
  for lock in "$REPO_ROOT/.agent_bus/meta/meta_bridge.lock" "$REPO_ROOT/.agent_bus/bridge.lock"; do
    if [ -f "$lock" ] && [ ! -s "$lock" ]; then
      echo "LOCK: (clean)"
      break
    fi
  done
  if [ ! -f "$REPO_ROOT/.agent_bus/meta/meta_bridge.lock" ] && [ ! -f "$REPO_ROOT/.agent_bus/bridge.lock" ]; then
    echo "LOCK: (none)"
  fi
  sleep 5
done
