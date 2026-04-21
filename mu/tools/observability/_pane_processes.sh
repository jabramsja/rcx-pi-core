#!/usr/bin/env bash
# _pane_processes.sh — Human-readable pipeline status pane for tmux
# Shows what's happening in plain language, not just PIDs.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
resolve_repo_root() {
  local helper="$SCRIPT_DIR/_resolve_live_root.sh"
  local root=""
  if [ -f "$helper" ]; then
    root=$(bash "$helper" 2>/dev/null || true)
  fi
  if [ -n "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}
resolve_branch_name_for_root() {
  local root="${1:-$REPO_ROOT}"
  git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}
refresh_context() {
  local next_root="" next_branch=""
  next_root="$(resolve_repo_root)"
  [ -n "$next_root" ] || next_root="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
  next_branch="$(resolve_branch_name_for_root "$next_root")"
  if [ "${REPO_ROOT:-}" != "$next_root" ] || [ "${BRANCH_NAME:-}" != "$next_branch" ]; then
    LAST_HASH=""
  fi
  REPO_ROOT="$next_root"
  BUS="$REPO_ROOT/.agent_bus"
  BRANCH_NAME="$next_branch"
  load_role_agent_labels "$REPO_ROOT"
}
REPO_ROOT=""
BUS=""
BRANCH_NAME=""
REVIEWER_DISPLAY="Reviewer"
REVIEWER_SHORT="Reviewer"
IMPLEMENTER_DISPLAY="Implementer"
IMPLEMENTER_SHORT="Implementer"
BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_processes_$$.txt"
ONESHOT="${RCX_PANE_ONESHOT:-0}"
FAST_ONESHOT=0
[ "$ONESHOT" = "1" ] && FAST_ONESHOT=1

load_role_agent_labels() {
  local root="${1:-$REPO_ROOT}" output="" key="" value=""
  [ -n "$root" ] || return 0
  output="$(python3 - "$root" <<'PY' 2>/dev/null
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo_root / "mu" / "tools" / "executors"))
try:
    from executor_common import configured_role_agents
    roles = configured_role_agents(repo_root)
except Exception:
    roles = {
        "reviewer": {"display_name": "Reviewer", "status_name": "Reviewer"},
        "implementer": {"display_name": "Implementer", "status_name": "Implementer"},
    }

for role in ("reviewer", "implementer"):
    data = roles.get(role, {})
    print(f"{role.upper()}_DISPLAY\t{data.get('display_name', role.title())}")
    print(f"{role.upper()}_SHORT\t{data.get('status_name', role.title())}")
PY
)"
  while IFS=$'\t' read -r key value; do
    case "$key" in
      REVIEWER_DISPLAY) REVIEWER_DISPLAY="$value" ;;
      REVIEWER_SHORT) REVIEWER_SHORT="$value" ;;
      IMPLEMENTER_DISPLAY) IMPLEMENTER_DISPLAY="$value" ;;
      IMPLEMENTER_SHORT) IMPLEMENTER_SHORT="$value" ;;
    esac
  done <<< "$output"
}

pane_max_lines() {
  local lines="${RCX_PANE_MAX_LINES:-}"
  if ! [[ "$lines" =~ ^[0-9]+$ ]] || [ "$lines" -lt 12 ]; then
    if [ -n "${TMUX_PANE:-}" ]; then
      lines=$(tmux display-message -p -t "$TMUX_PANE" '#{pane_height}' 2>/dev/null || echo "")
    fi
  fi
  if ! [[ "$lines" =~ ^[0-9]+$ ]] || [ "$lines" -lt 12 ]; then
    lines="${LINES:-}"
  fi
  if ! [[ "$lines" =~ ^[0-9]+$ ]] || [ "$lines" -lt 12 ]; then
    lines=$(tput lines 2>/dev/null || echo 35)
  fi
  if ! [[ "$lines" =~ ^[0-9]+$ ]] || [ "$lines" -lt 12 ]; then
    lines=35
  fi
  printf '%s\n' "$lines"
}

fit_output_to_pane() {
  local file="$1"
  local max_lines="$2"
  local total_lines head_keep tail_keep tmp

  total_lines=$(wc -l < "$file" 2>/dev/null | xargs)
  if ! [[ "$total_lines" =~ ^[0-9]+$ ]] || [ "$total_lines" -le "$max_lines" ]; then
    return 0
  fi

  head_keep=16
  if [ "$max_lines" -lt 22 ]; then
    head_keep=$(( max_lines / 2 ))
  fi
  [ "$head_keep" -lt 8 ] && head_keep=8
  tail_keep=$(( max_lines - head_keep - 1 ))
  [ "$tail_keep" -lt 3 ] && tail_keep=3

  tmp="${file}.trim"
  {
    head -n "$head_keep" "$file"
    echo -e "  ${DIM}More detail is hidden to keep this pane readable.${RESET}"
    tail -n "$tail_keep" "$file"
  } > "$tmp"
  mv "$tmp" "$file"
}

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

human_phase_b_step() {
  local step="$1"
  case "$step" in
    agent_review) printf '%s\n' "native SDK agents are auditing the code" ;;
    implementer) printf '%s\n' "the implementer is writing the fix" ;;
    bridge_review) printf '%s\n' "$REVIEWER_DISPLAY is reviewing the fix" ;;
    needs_phase_b_reentry) printf '%s\n' "waiting to restart Phase B" ;;
    *)
      printf '%s\n' "${step//_/ }"
      ;;
  esac
}

human_gate_decision() {
  local decision="$1"
  case "$decision" in
    COMMIT_GO) printf '%s\n' "approved to commit and merge" ;;
    COMMIT_GO_HOLD_PUSH) printf '%s\n' "approved, but hold the push" ;;
    REQUEST_CHANGES) printf '%s\n' "changes requested" ;;
    NO_GO) printf '%s\n' "blocked" ;;
    NEEDS_PHASE_B) printf '%s\n' "send it back to Phase B" ;;
    NEEDS_PHASE_A) printf '%s\n' "send it back to Phase A" ;;
    QUESTION) printf '%s\n' "waiting on a human answer" ;;
    ERROR) printf '%s\n' "the gate hit an error" ;;
    *)
      printf '%s\n' "${decision//_/ }"
      ;;
  esac
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
      # Skip shell wrappers and tee — they contain executor keywords in
      # embedded strings (e.g. tee .scratch/phase_a_executor_live.log) which
      # cause false-positive phase detection.
      "bash -c "*|*/bash\ -c\ *|"tee "*)
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

pid_ppid() {
  local pid="$1"
  ps -p "$pid" -o ppid= 2>/dev/null | xargs
}

pid_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

bridge_agent_name_for_command() {
  local cmd="$1"
  if echo "$cmd" | grep -E -i -q '(^|[ /])codex([[:space:]]|$).*(^|[[:space:]])exec([[:space:]]|$)'; then
    printf '%s\n' "codex"
    return 0
  fi
  if echo "$cmd" | grep -E -i -q '(^|[ /])claude([[:space:]]|$).*--print'; then
    printf '%s\n' "claude"
    return 0
  fi
  return 1
}

pid_has_ancestor_matching() {
  local pid="$1" pattern="$2" depth=0 parent="" cmd=""
  while [ "$depth" -lt 8 ]; do
    parent="$(pid_ppid "$pid")"
    [ -n "$parent" ] || return 1
    [ "$parent" = "1" ] && return 1
    cmd="$(pid_command "$parent")"
    if echo "$cmd" | grep -E -q "$pattern"; then
      return 0
    fi
    pid="$parent"
    depth=$((depth + 1))
  done
  return 1
}

bridge_role_for_pid() {
  local pid="$1"
  if pid_has_ancestor_matching "$pid" 'bridge_supervisor\.py review|meta_bridge_supervisor'; then
    printf '%s\n' "review"
    return 0
  fi
  if pid_has_ancestor_matching "$pid" 'phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py'; then
    printf '%s\n' "implement"
    return 0
  fi
  printf '%s\n' "unknown"
}

while true; do
  refresh_context
  # Build output to temp file, only redraw if content changed
  {
  echo -e "${BOLD}Pane 3: plain-English status${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}This pane shows what the pipeline is doing and what recovery last did.${RESET}"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"
  echo ""

  # Detect active phase
  phase="idle"
  phase_pid=""
  if [ "$FAST_ONESHOT" != "1" ]; then
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
  fi

  if [ "$FAST_ONESHOT" != "1" ]; then
    DASHBOARD_PY="$SCRIPT_DIR/pipeline_dashboard.py"
    if [ -f "$DASHBOARD_PY" ]; then
      python3 "$DASHBOARD_PY" --emit-idle-non-go-alert --repo-root "$REPO_ROOT" >/dev/null 2>&1 || true
    fi
  fi

  if [ "$phase" = "idle" ]; then
    echo -e "  ${DIM}No pipeline step is running. Waiting for the next wave.${RESET}"
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

  worker_lines=0

  # Check for bridge-agent workers. The configured reviewer/implementer may be
  # Codex or Claude, so infer role from the live parent chain.
  codex_review_pids=""
  codex_review_count=0
  codex_review_start=""
  codex_impl_pids=""
  codex_impl_count=0
  codex_impl_start=""
  codex_unknown_pids=""
  codex_unknown_count=0
  codex_unknown_start=""
  if [ "$FAST_ONESHOT" != "1" ]; then
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      cmd=$(ps -p "$pid" -o command= 2>/dev/null) || continue
      case "$cmd" in
        "bash -c "*|*/bash\ -c\ *|"tee "*) continue ;;
      esac
      bridge_agent_name_for_command "$cmd" >/dev/null || continue
      pid_matches_repo_root "$pid" || continue
      role="$(bridge_role_for_pid "$pid")"
      s=$(ps -p "$pid" -o lstart= 2>/dev/null | xargs)
      started_ts=$(date -j -f "%c" "$s" +%s 2>/dev/null || echo "")
      case "$role" in
        review)
          codex_review_pids="${codex_review_pids}${pid} "
          codex_review_count=$((codex_review_count + 1))
          [ -z "$codex_review_start" ] && codex_review_start="$started_ts"
          ;;
        implement)
          codex_impl_pids="${codex_impl_pids}${pid} "
          codex_impl_count=$((codex_impl_count + 1))
          [ -z "$codex_impl_start" ] && codex_impl_start="$started_ts"
          ;;
        *)
          codex_unknown_pids="${codex_unknown_pids}${pid} "
          codex_unknown_count=$((codex_unknown_count + 1))
          [ -z "$codex_unknown_start" ] && codex_unknown_start="$started_ts"
          ;;
      esac
    done < <(pgrep -f "codex.*exec|claude.*--print" 2>/dev/null | head -5 || true)
  fi
  if [ "$codex_review_count" -gt 0 ]; then
    if [ "$worker_lines" -eq 0 ]; then
      echo -e "${BOLD}WHO'S WORKING${RESET}"
      echo "─────────────────────────────────────"
    fi
    worker_lines=$((worker_lines + 1))
    echo -e ""
    echo -e "  ${YELLOW}REVIEWING${RESET}  $REVIEWER_DISPLAY"
    echo -e "  ${DIM}$codex_review_count process(es)$([ -n "$codex_review_start" ] && echo " · $(elapsed_str "$codex_review_start")") | PIDs: ${codex_review_pids%% }${RESET}"
    echo -e "  ${DIM}Checking implementation for bugs, security issues,${RESET}"
    echo -e "  ${DIM}protocol violations, and code quality.${RESET}"
  fi
  if [ "$codex_impl_count" -gt 0 ]; then
    if [ "$worker_lines" -eq 0 ]; then
      echo -e "${BOLD}WHO'S WORKING${RESET}"
      echo "─────────────────────────────────────"
    fi
    worker_lines=$((worker_lines + 1))
    echo -e ""
    echo -e "  ${PURPLE}IMPLEMENTING${RESET}  $IMPLEMENTER_DISPLAY"
    echo -e "  ${DIM}$codex_impl_count process(es)$([ -n "$codex_impl_start" ] && echo " · $(elapsed_str "$codex_impl_start")") | PIDs: ${codex_impl_pids%% }${RESET}"
    echo -e "  ${DIM}Writing code changes based on the current fix plan.${RESET}"
  fi
  if [ "$codex_unknown_count" -gt 0 ]; then
    if [ "$worker_lines" -eq 0 ]; then
      echo -e "${BOLD}WHO'S WORKING${RESET}"
      echo "─────────────────────────────────────"
    fi
    worker_lines=$((worker_lines + 1))
    echo -e ""
    echo -e "  ${CYAN}WORKING${RESET}  Bridge agent subprocess"
    echo -e "  ${DIM}$codex_unknown_count process(es)$([ -n "$codex_unknown_start" ] && echo " · $(elapsed_str "$codex_unknown_start")") | PIDs: ${codex_unknown_pids%% }${RESET}"
    echo -e "  ${DIM}Role could not be inferred from the current parent chain.${RESET}"
  fi

  # Check for SDK agents
  agent_pid=""
  if [ "$FAST_ONESHOT" != "1" ]; then
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      pid_matches_repo_root "$pid" || continue
      agent_pid="$pid"
      break
  done < <(pgrep -f "run_review.py" 2>/dev/null || true)
  fi
  if [ -n "$agent_pid" ]; then
    if [ "$worker_lines" -eq 0 ]; then
      echo -e "${BOLD}WHO'S WORKING${RESET}"
      echo "─────────────────────────────────────"
    fi
    worker_lines=$((worker_lines + 1))
    echo -e ""
    # Read actual agent count from status file if available
    agent_label="SDK Agents"
    agent_status_file=$(ls -t "$REPO_ROOT/.scratch/phase_"*"_agent_review_"*.status.json 2>/dev/null | head -1) || true
    if [ -n "$agent_status_file" ] && [ -f "$agent_status_file" ]; then
      agent_info=$(python3 -c "
import json
d = json.load(open('$agent_status_file'))
running = d.get('running_agents', [])
completed = list(d.get('completed_agents', {}).keys())
total = len(set(running + completed))
if running:
    names = ', '.join(running[:3])
    print(f'{total} agents ({names} running)')
else:
    print(f'{total} agents')
" 2>/dev/null) || true
      [ -n "$agent_info" ] && agent_label="$agent_info"
    fi
    echo -e "  ${CYAN}AUDITING${RESET}  $agent_label"
    echo -e "  ${DIM}PID: $agent_pid${RESET}"
    echo -e "  ${DIM}Fuzzer, verifier, adversary, translator, etc.${RESET}"
    echo -e "  ${DIM}Running parallel security and correctness checks.${RESET}"
  fi

  if [ "$codex_review_count" -eq 0 ] && [ "$codex_impl_count" -eq 0 ] && [ "$codex_unknown_count" -eq 0 ] && [ -z "$agent_pid" ] && [ "$phase" != "idle" ]; then
    if [ "$worker_lines" -eq 0 ]; then
      echo -e "${BOLD}WHO'S WORKING${RESET}"
      echo "─────────────────────────────────────"
    fi
    worker_lines=$((worker_lines + 1))
    echo -e "  ${DIM}A pipeline step is running, but no model subprocess is active yet.${RESET}"
  fi

  if [ "$worker_lines" -eq 0 ]; then
    echo -e "  ${DIM}Nobody is working right now.${RESET}"
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
        echo -e "  ${YELLOW}Bridge is busy${RESET} — $holder (PID $lpid, alive)"
      else
        echo -e "  ${RED}Bridge lock looks stale${RESET} — $holder (PID $lpid, dead)"
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
    phase_b_is_live=0
    case "$phase" in
      "Phase B: Implement + Review"|"Bridge: Review in progress")
        phase_b_is_live=1
        ;;
    esac

    # Override step with live process detection (state file can be stale)
    if [ -n "$agent_pid" ]; then
      step="agent_review"
      phase_b_is_live=1
    elif [ "$codex_impl_count" -gt 0 ]; then
      step="implementer"
      phase_b_is_live=1
    elif [ "$codex_review_count" -gt 0 ] || [ "$codex_unknown_count" -gt 0 ]; then
      step="bridge_review"
      phase_b_is_live=1
    fi

    if [ "$mr" -gt 0 ] && { [ "$phase_b_is_live" -eq 1 ] || [ "$pb_age" -le 600 ]; }; then
      echo -e "  Review pass: ${BOLD}$br / $mr${RESET}"
    fi
    human_step=$(human_phase_b_step "$step")
    step_label="Current step"
    if [ "$phase_b_is_live" -eq 0 ]; then
      step_label="Last saved Phase B checkpoint"
    fi
    if [ "$phase_b_is_live" -eq 1 ]; then
      echo -e "  $step_label: $human_step"
    elif [ "$pb_age" -le 600 ]; then
      echo -e "  $step_label: $human_step"
    else
      echo -e "  $step_label: $human_step ${DIM}($(( pb_age / 3600 ))h ago — stale)${RESET}"
    fi
  fi

  # Latest receipt (show age so stale ones are obvious)
  LATEST_RECEIPT=$(ls -t "$BUS/meta/pre_commit_receipts"/receipt_*.json 2>/dev/null | head -1) || true
  if [ -n "$LATEST_RECEIPT" ] && [ -f "$LATEST_RECEIPT" ]; then
    dec=$(jq -r '.decision // "?"' "$LATEST_RECEIPT" 2>/dev/null) || dec="?"
    human_dec=$(human_gate_decision "$dec")
    receipt_age=$(( $(date +%s) - $(stat -f%m "$LATEST_RECEIPT" 2>/dev/null || stat -c%Y "$LATEST_RECEIPT" 2>/dev/null || echo 0) ))
    if [ "$receipt_age" -le 600 ]; then
      echo -e "  Last gate decision: $human_dec ($(( receipt_age / 60 ))m ago)"
    fi
  fi

  # No lock at all
  if [ ! -f "$BUS/bridge.lock" ] || [ ! -s "$BUS/bridge.lock" ]; then
    if [ ! -f "$BUS/meta/meta_bridge.lock" ] || [ ! -s "$BUS/meta/meta_bridge.lock" ]; then
      echo -e "  ${DIM}Bridge is clear${RESET}"
    fi
  fi

  echo ""

  DASHBOARD_PY="$SCRIPT_DIR/pipeline_dashboard.py"
  if [ -f "$DASHBOARD_PY" ]; then
    RECOVERY_TMP="/tmp/rcx_pane_processes_recovery_$$.txt"
    python3 "$DASHBOARD_PY" --render-recovery --repo-root "$REPO_ROOT" > "$RECOVERY_TMP" 2>/dev/null || true
    recovery_line_count=$(wc -l < "$RECOVERY_TMP" 2>/dev/null | xargs)
    if [[ "$recovery_line_count" =~ ^[0-9]+$ ]] && [ "$recovery_line_count" -gt 0 ]; then
      # Add staleness indicator to recovery header — check the status file age
      recovery_status_file="$REPO_ROOT/.agent_bus/recovery/recovery_status.json"
      recovery_age_label=""
      if [ -f "$recovery_status_file" ]; then
        recovery_age=$(( $(date +%s) - $(stat -f%m "$recovery_status_file" 2>/dev/null || stat -c%Y "$recovery_status_file" 2>/dev/null || echo 0) ))
        if [ "$recovery_age" -lt 120 ]; then
          recovery_age_label="${recovery_age}s ago"
        elif [ "$recovery_age" -lt 7200 ]; then
          recovery_age_label="$(( recovery_age / 60 ))m ago"
        else
          recovery_age_label="$(( recovery_age / 3600 ))h ago — stale"
        fi
      fi
      # Print recovery with age-annotated header (replace first line if it matches)
      {
        first_line=true
        while IFS= read -r line; do
          if [ "$first_line" = true ]; then
            first_line=false
            if [ -n "$recovery_age_label" ] && echo "$line" | grep -q "^RECOVERY"; then
              echo -e "${BOLD}RECOVERY${RESET}  ${DIM}($recovery_age_label)${RESET}"
              continue
            fi
          fi
          echo "$line"
        done < "$RECOVERY_TMP"
      } > "${RECOVERY_TMP}.annotated"
      mv "${RECOVERY_TMP}.annotated" "$RECOVERY_TMP"
      max_recovery_lines=8
      if [ "$phase" != "idle" ] || [ "$worker_lines" -gt 0 ]; then
        max_recovery_lines=11
      fi
      head -n "$max_recovery_lines" "$RECOVERY_TMP"
      if [ "$recovery_line_count" -gt "$max_recovery_lines" ]; then
        echo -e "  ${DIM}More recovery detail is hidden to keep this pane readable.${RESET}"
      fi
      echo ""
    fi
    rm -f "$RECOVERY_TMP"
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

  # Skip activity tail when SDK agents are running — the implementer output is stale context
  if [ "$FAST_ONESHOT" != "1" ] && [ -n "$activity_source" ] && [ -z "$agent_pid" ] && { [ "$phase" != "idle" ] || [ "$worker_lines" -gt 0 ]; }; then
    # Determine label
    case "$activity_source" in
      *implementer*) activity_label="${PURPLE}IMPLEMENTING${RESET}" ;;
      *reviewer*) activity_label="${YELLOW}REVIEWING${RESET}" ;;
      *codex*|*rollout*) activity_label="${YELLOW}REVIEWING${RESET}" ;;
    esac

    echo -e "${BOLD}ACTIVITY${RESET} ${activity_label} ${DIM}(${activity_age}s ago)${RESET}" >> "$TMPOUT"
    echo "─────────────────────────────────────" >> "$TMPOUT"

    if echo "$activity_source" | grep -q "implementer"; then
      # Parse the current structured implementer transcript with a text fallback.
      tail -30 "$activity_source" 2>/dev/null | python3 -c "
import json, sys

raw_lines = sys.stdin.read().splitlines()
events = []
for line in raw_lines:
    stripped = line.strip()
    if not stripped:
        continue
    try:
        evt = json.loads(stripped)
    except Exception:
        continue
    if evt.get('type') == 'item.completed':
        item = evt.get('item', {})
        if item.get('type') == 'agent_message':
            text = item.get('text', '').strip()
            if text:
                events.append(text.split(chr(10))[0][:90])
        continue
    if evt.get('type') == 'assistant':
        for block in evt.get('message', {}).get('content', []):
            if block.get('type') == 'text':
                text = block.get('text', '').strip()
                if text:
                    events.append(text.split(chr(10))[0][:90])
if events:
    for item in events[-6:]:
        print(f'  \033[2m{item}\033[0m')
else:
    for line in raw_lines[-6:]:
        text = line.strip()
        if text:
            print(f'  \033[2m{text[:90]}\033[0m')
" 2>/dev/null >> "$TMPOUT"

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

  fit_output_to_pane "$TMPOUT" "$(pane_max_lines)"

  # Only redraw if content changed (ignore timestamp line)
  NEW_HASH=$(tail -n +2 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +2 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    printf '\033[H\033[2J\033[3J'
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  else
    # Data unchanged — just update timestamp so user knows it's alive
    tput cup 0 0 2>/dev/null
    echo -e "${BOLD}Pane 3: plain-English status${RESET}  $(date '+%H:%M:%S')"
  fi

  if [ "$ONESHOT" = "1" ]; then
    rm -f "$TMPOUT"
    exit 0
  fi

  # Auto-reload: re-exec if script changed on disk
  _SELF="${BASH_SOURCE[0]}"
  _NEW_MTIME=$(stat -f%m "$_SELF" 2>/dev/null || stat -c%Y "$_SELF" 2>/dev/null || echo 0)
  if [ "${_SELF_MTIME:-0}" != "0" ] && [ "$_NEW_MTIME" != "$_SELF_MTIME" ]; then
    rm -f "$TMPOUT"
    sleep 1
    exec bash "$_SELF"
  fi
  _SELF_MTIME="$_NEW_MTIME"

  sleep 5
done
