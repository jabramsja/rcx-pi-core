#!/usr/bin/env bash
# _pane_timeline.sh — Session timeline pane for tmux
# Shows chronological history of what happened this pipeline run.
set +e
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
  BRANCH_NAME="$next_branch"
}
REPO_ROOT=""
BRANCH_NAME=""
BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_timeline_$$.txt"

fmt_time() {
  # Convert epoch to HH:MM
  if [ -n "$1" ] && [ "$1" -gt 0 ] 2>/dev/null; then
    date -r "$1" '+%H:%M' 2>/dev/null || date -d "@$1" '+%H:%M' 2>/dev/null || echo "??:??"
  fi
}

file_time() {
  stat -f%m "$1" 2>/dev/null || stat -c%Y "$1" 2>/dev/null || echo 0
}

pid_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

repo_has_process() {
  local pattern="$1" pid cmd cwd
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
    case "$cmd" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*"_pane_"*|*"pipeline_monitor.sh"*)
        continue
        ;;
      "bash -c "*|*/bash\ -c\ *|"tee "*)
        continue
        ;;
    esac
    case "$cmd" in
      *"$REPO_ROOT"*)
        return 0
        ;;
    esac
    cwd="$(pid_cwd "$pid")"
    if [ -n "$cwd" ] && [ "$cwd" = "$REPO_ROOT" ]; then
      return 0
    fi
  done < <(pgrep -f "$pattern" 2>/dev/null || true)
  return 1
}

while true; do
  refresh_context
  {
  echo -e "${BOLD}Pane 4: session timeline${RESET}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}This pane shows the recent milestones in time order.${RESET}"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"
  echo ""

  # Collect events with timestamps, then sort chronologically
  EVENTS=""
  add_event() {
    local ts="$1" msg="$2"
    [ -z "$ts" ] || [ "$ts" = "0" ] && return
    EVENTS="${EVENTS}${ts}|${msg}\n"
  }

  # 1. Implementer runs
  for f in $(ls -t "$REPO_ROOT/.scratch/phase_b_implementer_output_"*.txt 2>/dev/null | head -5); do
    ts=$(file_time "$f")
    size=$(wc -c < "$f" 2>/dev/null | xargs)
    # Check if this run produced changes
    if [ "$size" -gt 100000 ]; then
      add_event "$ts" "${PURPLE}Claude done${RESET} — $(( size / 1024 ))KB output"
    else
      add_event "$ts" "${PURPLE}Claude implementing${RESET}..."
    fi
  done

  # 2. Agent reviews
  for f in $(ls -t "$REPO_ROOT/.scratch/phase_b_agent_review_"*.status.json 2>/dev/null | head -5); do
    ts=$(file_time "$f")
    status=$(python3 -c "
import json
d = json.load(open('$f'))
s = d.get('status','?')
completed = d.get('completed_agents',{})
running = d.get('running_agents',[])
passed = sum(1 for v in completed.values() if v.get('passed'))
failed = sum(1 for v in completed.values() if not v.get('passed'))
total = len(completed)
if s == 'completed':
    if failed: print(f'${YELLOW}Agents${RESET}: {passed} pass, {failed} need work')
    else: print(f'${GREEN}Agents${RESET}: all {total} passed')
elif running:
    names = ', '.join(running)
    print(f'${CYAN}Agents running${RESET}: {names}')
else:
    print(f'${CYAN}Agents${RESET}: {s}')
" 2>/dev/null)
    [ -n "$status" ] && add_event "$ts" "$status"
  done

  # 3. Bridge review rounds
  RAW_DIR="$REPO_ROOT/.agent_bus/raw"
  if [ -d "$RAW_DIR" ]; then
    for dir in $(ls -dt "$RAW_DIR"/phase-?-r[0-9]* 2>/dev/null | head -8); do
      round_name=$(basename "$dir")
      reviewer_file=$(ls -t "$dir"/*reviewer*.txt 2>/dev/null | head -1) || true
      [ -z "$reviewer_file" ] || [ ! -s "$reviewer_file" ] && continue
      ts=$(file_time "$reviewer_file")

      decision=$(python3 -c "
import json, re
content = open('$reviewer_file', errors='replace').read()
matches = list(re.finditer(r'BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE', content, re.DOTALL))
if not matches: exit()
env = json.loads(matches[-1].group(1))
env = None
for m in reversed(matches):
    candidate = json.loads(m.group(1))
    dec = candidate.get('decision','')
    if dec and '|' not in dec:
        env = candidate
        break
if env is None:
    exit()
dec = env.get('decision','?')
findings = env.get('findings',[])
blk = sum(1 for f in findings if f.get('disposition') == 'blocking')
nb = sum(1 for f in findings if f.get('disposition') != 'blocking')
if dec in ('GO','COMMIT_GO'):
    print(f'\033[32mCodex: GO\033[0m ({nb} advisory)')
elif dec == 'REQUEST_CHANGES':
    print(f'\033[33mCodex: REQUEST_CHANGES\033[0m ({blk}B {nb}NB)')
elif dec == 'NO_GO':
    print(f'\033[31mCodex: NO_GO\033[0m ({blk} blocker, {nb} advisory)')
else:
    print(f'Codex: {dec} ({blk}B {nb}NB)')
" 2>/dev/null)
      [ -n "$decision" ] && add_event "$ts" "$decision"

      # Also add the start time (reader file = when review started)
      reader_file=$(ls -t "$dir"/*reader*.txt 2>/dev/null | head -1) || true
      if [ -n "$reader_file" ]; then
        start_ts=$(file_time "$reader_file")
        add_event "$start_ts" "${YELLOW}Codex reviewing${RESET}..."
      fi
    done
  fi

  # 4. Executor start
  for f in "$REPO_ROOT/.scratch/phase_a_executor_live.log" \
           "$REPO_ROOT/.scratch/phase_b_executor_live.log" \
           "$REPO_ROOT/.scratch/commit_executor_live.log"; do
    [ -f "$f" ] || continue
    ts=$(file_time "$f")
    case "$(basename "$f")" in
      phase_a_executor_live.log) add_event "$ts" "${YELLOW}Phase A updated${RESET}" ;;
      phase_b_executor_live.log) add_event "$ts" "${PURPLE}Phase B updated${RESET}" ;;
      commit_executor_live.log) add_event "$ts" "${GREEN}Commit path updated${RESET}" ;;
    esac
  done

  # 5. Commits on current branch
  git -C "$REPO_ROOT" log --format="%ct|${GREEN}Committed${RESET}: %s" --since="6 hours ago" -5 2>/dev/null | while IFS='|' read -r cts msg; do
    echo "${cts}|${msg}"
  done > /tmp/rcx_timeline_commits_$$.txt 2>/dev/null
  if [ -s /tmp/rcx_timeline_commits_$$.txt ]; then
    while IFS= read -r line; do
      EVENTS="${EVENTS}${line}\n"
    done < /tmp/rcx_timeline_commits_$$.txt
  fi
  rm -f /tmp/rcx_timeline_commits_$$.txt

  # Sort and display
  if [ -n "$EVENTS" ]; then
    echo -e "$EVENTS" | sort -t'|' -k1 -n | while IFS='|' read -r ts msg; do
      [ -z "$ts" ] || [ -z "$msg" ] && continue
      time_str=$(fmt_time "$ts")
      echo -e "  ${DIM}${time_str}${RESET}  $msg"
    done
  else
    echo -e "  ${DIM}No pipeline activity yet${RESET}"
  fi

  # Current status pointer
  echo ""
  now=$(date '+%H:%M')
  # Figure out what's happening right now
  if repo_has_process "codex.*exec.*gpt"; then
    echo -e "  ${DIM}${now}${RESET}  ${YELLOW}← Codex reviewing now${RESET}"
  elif repo_has_process "claude.*--print"; then
    echo -e "  ${DIM}${now}${RESET}  ${PURPLE}← Claude implementing now${RESET}"
  elif repo_has_process "run_review.py"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← SDK review agents checking this worktree now${RESET}"
  elif repo_has_process "phase_a_executor\|phase_b_executor\|commit_executor\|executor_dispatch"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← pipeline executor working in this worktree now${RESET}"
  else
    echo -e "  ${DIM}${now}${RESET}  ${DIM}← idle${RESET}"
  fi

  # Helpful reference
  echo ""
  echo -e "${DIM}Typical durations:${RESET}"
  echo -e "${DIM}  Claude: 5-15m | Agents: 3-5m | Codex: 10-20m${RESET}"
  echo -e "${DIM}  NO_GO is normal — usually 2-3 rounds to converge${RESET}"

  } > "$TMPOUT" 2>/dev/null

  # Only redraw if content changed (ignore first line with title)
  NEW_HASH=$(tail -n +2 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +2 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    printf '\033[H\033[2J\033[3J'
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  else
    # Data unchanged — just update timestamp so user knows it's alive
    tput cup 0 0 2>/dev/null
    echo -e "${BOLD}Pane 4: session timeline${RESET}  $(date '+%H:%M:%S')"
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
