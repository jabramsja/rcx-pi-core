#!/usr/bin/env bash
# _pane_processes.sh — Human-readable pipeline status pane for tmux
# Shows what's happening in plain language, not just PIDs
# Auto-reloads when the script file changes on disk.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
resolve_repo_root() {
  local helper="$SCRIPT_DIR/pipeline_status.sh"
  local root=""
  if [ -f "$helper" ]; then
    root=$(bash "$helper" --print-root 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}
resolve_branch_name() {
  local helper="$SCRIPT_DIR/pipeline_status.sh"
  local branch=""
  if [ -f "$helper" ]; then
    branch=$(bash "$helper" --print-branch-for-root "$REPO_ROOT" 2>/dev/null || true)
  fi
  if [ -n "$branch" ]; then
    printf '%s\n' "$branch"
    return 0
  fi
  git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}
REPO_ROOT="$(resolve_repo_root)"
BUS="$REPO_ROOT/.agent_bus"
BRANCH_NAME="$(resolve_branch_name)"
SELF="$SCRIPT_DIR/$(basename "$0")"
SELF_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)

BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_processes_$$.txt"
ONESHOT="${RCX_PANE_ONESHOT:-0}"

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

find_live_pid() {
  local kw="$1" pid cmd
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd=$(ps -p "$pid" -o command= 2>/dev/null) || continue
    case "$cmd" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*"_pane_"*|*"pipeline_monitor.sh"*)
        continue
        ;;
    esac
    pid_matches_repo_root "$pid" || continue
    if echo "$cmd" | grep -q "$kw"; then
      printf "%s\n" "$pid"
      return 0
    fi
  done < <(pgrep -f "$kw" 2>/dev/null || true)
  return 1
}

pid_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

pid_matches_repo_root() {
  local pid="$1" cmd cwd
  cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
  case "$cmd" in
    *"$REPO_ROOT"*) return 0 ;;
  esac
  cwd="$(pid_cwd "$pid")"
  [ -n "$cwd" ] && [ "$cwd" = "$REPO_ROOT" ]
}

while true; do
  # Build output to temp file, only redraw if content changed
  {
  echo -e "${BOLD}WHAT'S HAPPENING${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"
  echo ""

  # Detect active phase
  phase="idle"
  phase_pid=""
  for kw in phase_a_executor phase_b_executor commit_executor meta_bridge_supervisor bridge_supervisor executor_dispatch; do
    pid=$(find_live_pid "$kw") || true
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
  codex_pids=""
  codex_count=0
  codex_start=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    pid_matches_repo_root "$pid" || continue
    codex_pids="${codex_pids}${pid} "
    codex_count=$((codex_count + 1))
    if [ -z "$codex_start" ]; then
      s=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
      codex_start=$(date -j -f "%c" "$s" +%s 2>/dev/null || echo "")
    fi
  done < <(pgrep -f "codex.*exec.*gpt" 2>/dev/null | head -5 || true)
  if [ "$codex_count" -gt 0 ]; then
    echo -e ""
    echo -e "  ${YELLOW}REVIEWING${RESET}  Codex GPT-5.4 xhigh"
    echo -e "  ${DIM}$codex_count process(es)$([ -n "$codex_start" ] && echo " · $(elapsed_str "$codex_start")") | PIDs: ${codex_pids%% }${RESET}"
    echo -e "  ${DIM}Checking implementation for bugs, security issues,${RESET}"
    echo -e "  ${DIM}protocol violations, and code quality.${RESET}"
  fi

  # Check for Claude (implementer — must have --print flag, not interactive sessions)
  claude_pids=""
  claude_count=0
  claude_start=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    pid_matches_repo_root "$pid" || continue
    cmd=$(ps -p "$pid" -o command= 2>/dev/null) || continue
    # Only count implementer processes (have --print), skip interactive sessions
    if echo "$cmd" | grep -q "\-\-print"; then
      claude_pids="${claude_pids}${pid} "
      claude_count=$((claude_count + 1))
      if [ -z "$claude_start" ]; then
        s=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
        claude_start=$(date -j -f "%c" "$s" +%s 2>/dev/null || echo "")
      fi
    fi
  done < <(pgrep -f "claude.*--print" 2>/dev/null | head -3 || true)
  if [ "$claude_count" -gt 0 ]; then
    # Collect PIDs into a comma-separated string
    claude_pid_list=$(echo "${claude_pids%% }" | tr ' ' ',')
    echo -e ""
    echo -e "  ${PURPLE}IMPLEMENTING${RESET}  Claude Opus 4.6 max"
    echo -e "  ${DIM}$claude_count process(es)$([ -n "$claude_start" ] && echo " · $(elapsed_str "$claude_start")") | PIDs: $claude_pid_list${RESET}"
    echo -e "  ${DIM}Writing code changes based on the fix plan.${RESET}"
  fi

  # Check for SDK agents
  agent_pid=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    pid_matches_repo_root "$pid" || continue
    agent_pid="$pid"
    break
  done < <(pgrep -f "run_review.py" 2>/dev/null || true)
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

  echo ""

  DASHBOARD_PY="$SCRIPT_DIR/pipeline_dashboard.py"
  if [ -f "$DASHBOARD_PY" ]; then
    python3 "$DASHBOARD_PY" --render-recovery --repo-root "$REPO_ROOT" 2>/dev/null || true
    echo ""
  fi

  } > "$TMPOUT" 2>/dev/null

  # Live activity — show whichever model is active (implementer OR reviewer)
  # Pick the most recently modified source
  IMPL=$(ls -t "$REPO_ROOT/.scratch/phase_b_implementer_output_"*.txt 2>/dev/null | head -1) || true
  REVIEWER=$(ls -t "$REPO_ROOT/.agent_bus/raw"/phase-?-r[0-9]*/*reviewer*.txt 2>/dev/null | head -1) || true
  # Find which source is freshest
  activity_source=""
  activity_label=""
  activity_age=9999
  for candidate_file in "$IMPL" "$REVIEWER"; do
    [ -z "$candidate_file" ] || [ ! -f "$candidate_file" ] && continue
    age=$(( $(date +%s) - $(stat -f%m "$candidate_file" 2>/dev/null || stat -c%Y "$candidate_file" 2>/dev/null || echo 0) ))
    if [ "$age" -lt "$activity_age" ] && [ "$age" -lt 600 ]; then
      activity_age=$age
      activity_source="$candidate_file"
    fi
  done

  if [ -n "$activity_source" ]; then
    # Determine label
    case "$activity_source" in
      *implementer*) activity_label="${PURPLE}IMPLEMENTING${RESET}" ;;
      *reviewer*) activity_label="${YELLOW}REVIEWING${RESET}" ;;
      *codex*|*rollout*) activity_label="${YELLOW}REVIEWING${RESET}" ;;
    esac

    echo -e "${BOLD}ACTIVITY${RESET} ${activity_label} ${DIM}(${activity_age}s ago)${RESET}" >> "$TMPOUT"
    echo "─────────────────────────────────────" >> "$TMPOUT"

    if echo "$activity_source" | grep -q "implementer"; then
      # Claude stream-json: parse tool calls and thinking
      tail -20 "$activity_source" 2>/dev/null | python3 -c "
import json, sys
for line in sys.stdin:
    try:
        evt = json.loads(line.strip())
        if evt.get('type') != 'assistant': continue
        for b in evt.get('message',{}).get('content',[]):
            bt = b.get('type','')
            if bt == 'tool_use':
                name = b.get('name','?')
                inp = b.get('input',{})
                d = inp.get('file_path','') or inp.get('command','')[:70] or inp.get('pattern','')[:50] or ''
                d = d.split('WorkingRCX/')[-1] if 'WorkingRCX/' in d else d
                print(f'  \033[36m{name}\033[0m {d}')
            elif bt == 'text':
                t = b.get('text','').strip().split(chr(10))[0][:90]
                if t: print(f'  \033[2m{t}\033[0m')
    except: pass
" 2>/dev/null | tail -6 >> "$TMPOUT"

    elif echo "$activity_source" | grep -q "rollout\|codex/sessions"; then
      # Codex JSONL: parse tool calls and token counts
      tail -30 "$activity_source" 2>/dev/null | python3 -c "
import json, sys
for line in sys.stdin:
    try:
        evt = json.loads(line.strip())
        ts = evt.get('timestamp','')[11:19]
        etype = evt.get('type','')
        payload = evt.get('payload',{})
        if etype == 'response_item':
            ptype = payload.get('type','')
            if ptype == 'function_call':
                name = payload.get('name','?')
                args = payload.get('arguments','')[:60]
                print(f'  \033[36m{ts} {name}\033[0m {args}')
            elif ptype == 'message':
                content = payload.get('content',[])
                if isinstance(content, list) and content:
                    t = content[0].get('text','')[:90]
                elif isinstance(content, str):
                    t = content[:90]
                else:
                    t = ''
                if t: print(f'  \033[2m{ts} {t}\033[0m')
    except: pass
" 2>/dev/null | tail -6 >> "$TMPOUT"

    else
      # Raw reviewer text: show last few lines
      tail -6 "$activity_source" 2>/dev/null | while IFS= read -r line; do
        echo "  $line" | head -c 95
        echo ""
      done >> "$TMPOUT"
    fi
    echo "" >> "$TMPOUT"
  fi

  # Only redraw if content changed (ignore timestamp line)
  NEW_HASH=$(tail -n +2 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +2 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    clear
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  fi

  if [ "$ONESHOT" = "1" ]; then
    rm -f "$TMPOUT"
    exit 0
  fi

  # Auto-reload: if script changed on disk, re-exec
  NEW_MTIME=$(stat -f%m "$SELF" 2>/dev/null || stat -c%Y "$SELF" 2>/dev/null || echo 0)
  if [ "$NEW_MTIME" != "$SELF_MTIME" ]; then
    rm -f "$TMPOUT"
    sleep 1
    exec bash "$SELF"
  fi

  sleep 5
done
