#!/usr/bin/env bash
# _pane_processes.sh — Human-readable pipeline status pane for tmux
# Shows what's happening in plain language, not just PIDs
# Auto-reloads when the script file changes on disk.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BUS="$REPO_ROOT/.agent_bus"
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
SELF_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)

BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"

elapsed_str() {
  local started="$1"
  [ -z "$started" ] && return
  local now elapsed m s h
  now=$(date +%s)
  elapsed=$((now - started))
  h=$((elapsed / 3600))
  m=$(( (elapsed % 3600) / 60 ))
  s=$((elapsed % 60))
  if [ "$h" -gt 0 ]; then
    printf "%dh %02dm" "$h" "$m"
  elif [ "$m" -gt 0 ]; then
    printf "%dm %02ds" "$m" "$s"
  else
    printf "%ds" "$s"
  fi
}

while true; do
  clear
  echo -e "${BOLD}WHAT'S HAPPENING${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Detect active phase
  phase="idle"
  phase_pid=""
  for kw in phase_a_executor phase_b_executor commit_executor meta_bridge_supervisor bridge_supervisor executor_dispatch; do
    pid=$(pgrep -f "$kw" 2>/dev/null | head -1) || true
    if [ -n "$pid" ]; then
      case "$kw" in
        phase_a_executor) phase="Phase A: Planning" ;;
        phase_b_executor) phase="Phase B: Implement + Review" ;;
        commit_executor) phase="Commit: Pushing through gates" ;;
        meta_bridge_supervisor|bridge_supervisor) phase="Bridge: Review in progress" ;;
        executor_dispatch) phase="Dispatch: Selecting wave" ;;
      esac
      phase_pid="$pid"
      break
    fi
  done

  if [ "$phase" = "idle" ]; then
    echo -e "  ${DIM}Pipeline is idle. No active work.${RESET}"
  else
    started=$(ps -p "$phase_pid" -o lstart= 2>/dev/null | xargs)
    started_ts=""
    if [ -n "$started" ]; then
      started_ts=$(date -j -f "%c" "$started" +%s 2>/dev/null || date -d "$started" +%s 2>/dev/null || echo "")
    fi
    echo -e "  ${BOLD}${CYAN}$phase${RESET}  ${DIM}PID $phase_pid${RESET}"
    [ -n "$started_ts" ] && echo -e "  Running for $(elapsed_str "$started_ts")"
  fi

  echo ""

  # Who's working
  echo -e "${BOLD}WHO'S WORKING${RESET}"
  echo "─────────────────────────────────────"

  # Check for Codex (reviewer)
  codex_pids=$(pgrep -f "codex" 2>/dev/null | head -5) || codex_pids=""
  codex_count=0
  codex_start=""
  for pid in $codex_pids; do
    cmd=$(ps -p "$pid" -o command= 2>/dev/null) || continue
    if echo "$cmd" | grep -q "exec.*gpt-5.4"; then
      codex_count=$((codex_count + 1))
      if [ -z "$codex_start" ]; then
        s=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
        codex_start=$(date -j -f "%c" "$s" +%s 2>/dev/null || echo "")
      fi
    fi
  done
  if [ "$codex_count" -gt 0 ]; then
    echo -e ""
    echo -e "  ${YELLOW}REVIEWING${RESET}  Codex GPT-5.4 xhigh"
    echo -e "  ${DIM}$codex_count process(es)$([ -n "$codex_start" ] && echo " · $(elapsed_str "$codex_start")") | PIDs: $codex_pids${RESET}"
    echo -e "  ${DIM}Checking implementation for bugs, security issues,${RESET}"
    echo -e "  ${DIM}protocol violations, and code quality.${RESET}"
  fi

  # Check for Claude (implementer — must have --print flag, not interactive sessions)
  claude_pids=$(pgrep -f "claude.*--print" 2>/dev/null | head -3) || claude_pids=""
  claude_count=0
  claude_start=""
  for pid in $claude_pids; do
    cmd=$(ps -p "$pid" -o command= 2>/dev/null) || continue
    # Only count implementer processes (have --print), skip interactive sessions
    if echo "$cmd" | grep -q "\-\-print"; then
      claude_count=$((claude_count + 1))
      if [ -z "$claude_start" ]; then
        s=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
        claude_start=$(date -j -f "%c" "$s" +%s 2>/dev/null || echo "")
      fi
    fi
  done
  if [ "$claude_count" -gt 0 ]; then
    # Collect PIDs into a comma-separated string
    claude_pid_list=$(echo $claude_pids | tr ' ' ',')
    echo -e ""
    echo -e "  ${PURPLE}IMPLEMENTING${RESET}  Claude Opus 4.6 max"
    echo -e "  ${DIM}$claude_count process(es)$([ -n "$claude_start" ] && echo " · $(elapsed_str "$claude_start")") | PIDs: $claude_pid_list${RESET}"
    echo -e "  ${DIM}Writing code changes based on the fix plan.${RESET}"
  fi

  # Check for SDK agents
  agent_pid=$(pgrep -f "run_review.py" 2>/dev/null | head -1) || agent_pid=""
  if [ -n "$agent_pid" ]; then
    echo -e ""
    echo -e "  ${CYAN}AUDITING${RESET}  9 Native SDK Agents"
    echo -e "  ${DIM}PID: $agent_pid${RESET}"
    echo -e "  ${DIM}Fuzzer, verifier, adversary, translator, etc.${RESET}"
    echo -e "  ${DIM}Running parallel security and correctness checks.${RESET}"
  fi

  if [ "$codex_count" -eq 0 ] && [ "$claude_count" -eq 0 ] && [ -z "$agent_pid" ] && [ "$phase" != "idle" ]; then
    echo -e "  ${DIM}Executor running (no model subprocess detected yet)${RESET}"
  fi

  echo ""

  # Bridge state
  echo -e "${BOLD}BRIDGE${RESET}"
  echo "─────────────────────────────────────"
  for lock in "$BUS/bridge.lock" "$BUS/meta/meta_bridge.lock"; do
    if [ -f "$lock" ] && [ -s "$lock" ]; then
      holder=$(jq -r '.holder // "unknown"' "$lock" 2>/dev/null) || holder="?"
      lpid=$(jq -r '.pid // "0"' "$lock" 2>/dev/null) || lpid="0"
      if [ "$lpid" != "0" ] && kill -0 "$lpid" 2>/dev/null; then
        echo -e "  ${YELLOW}LOCKED${RESET} — $holder (PID $lpid, alive)"
      else
        echo -e "  ${RED}STALE LOCK${RESET} — $holder (PID $lpid, dead)"
      fi
    fi
  done

  # Phase B state — cross-check with live processes
  PB_STATE="$BUS/executors/phase_b_state.json"
  if [ -f "$PB_STATE" ]; then
    br=$(jq -r '.bridge_rounds // 0' "$PB_STATE" 2>/dev/null) || br=0
    mr=$(jq -r '.max_bridge_rounds // 0' "$PB_STATE" 2>/dev/null) || mr=0
    step=$(jq -r '.completed_step // "?"' "$PB_STATE" 2>/dev/null) || step="?"
    pb_age=$(( $(date +%s) - $(stat -f%m "$PB_STATE" 2>/dev/null || stat -c%Y "$PB_STATE" 2>/dev/null || echo 0) ))

    # Override step with live process detection (state file can be stale)
    if [ -n "$agent_pid" ]; then
      step="agent_review"
    elif [ "$claude_count" -gt 0 ]; then
      step="implementer"
    elif [ "$codex_count" -gt 0 ]; then
      step="bridge_review"
    fi

    if [ "$mr" -gt 0 ]; then
      echo -e "  Review round: ${BOLD}$br / $mr${RESET}"
    fi
    if [ "$pb_age" -gt 600 ]; then
      echo -e "  Step: $step ${DIM}(state file $(( pb_age / 60 ))m old)${RESET}"
    else
      echo -e "  Step: $step"
    fi
  fi

  # Latest receipt (show age so stale ones are obvious)
  LATEST_RECEIPT=$(ls -t "$BUS/meta/pre_commit_receipts"/receipt_*.json 2>/dev/null | head -1) || true
  if [ -n "$LATEST_RECEIPT" ] && [ -f "$LATEST_RECEIPT" ]; then
    dec=$(jq -r '.decision // "?"' "$LATEST_RECEIPT" 2>/dev/null) || dec="?"
    receipt_age=$(( $(date +%s) - $(stat -f%m "$LATEST_RECEIPT" 2>/dev/null || stat -c%Y "$LATEST_RECEIPT" 2>/dev/null || echo 0) ))
    if [ "$receipt_age" -gt 600 ]; then
      echo -e "  Last receipt: $dec ${DIM}($(( receipt_age / 60 ))m ago — stale)${RESET}"
    else
      echo -e "  Last receipt: $dec ($(( receipt_age / 60 ))m ago)"
    fi
  fi

  # No lock at all
  if [ ! -f "$BUS/bridge.lock" ] || [ ! -s "$BUS/bridge.lock" ]; then
    if [ ! -f "$BUS/meta/meta_bridge.lock" ] || [ ! -s "$BUS/meta/meta_bridge.lock" ]; then
      echo -e "  ${DIM}Unlocked${RESET}"
    fi
  fi

  # Auto-reload: if script changed on disk, re-exec
  NEW_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)
  if [ "$NEW_MTIME" != "$SELF_MTIME" ]; then
    echo -e "  ${DIM}(script updated — reloading...)${RESET}"
    sleep 1
    exec bash "$SELF"
  fi

  sleep 5
done
