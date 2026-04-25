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
  load_role_agent_labels "$REPO_ROOT"
}
REPO_ROOT=""
BRANCH_NAME=""
REVIEWER_DISPLAY="Reviewer"
REVIEWER_SHORT="Reviewer"
IMPLEMENTER_DISPLAY="Implementer"
IMPLEMENTER_SHORT="Implementer"
BOLD="\033[1m" DIM="\033[2m" GREEN="\033[32m" YELLOW="\033[33m"
RED="\033[31m" CYAN="\033[36m" PURPLE="\033[35m" RESET="\033[0m"
LAST_HASH=""
TMPOUT="/tmp/rcx_pane_timeline_$$.txt"
ONESHOT="${RCX_PANE_ONESHOT:-0}"

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

is_control_plane_resume_command() {
  local cmd="$1"
  case "$cmd" in
    *"Autonomous WorkingRCX pipeline watchdog tick."*|*"WorkingRCX pipeline pager wakeup."*)
      return 0
      ;;
  esac
  return 1
}

repo_has_process() {
  local pattern="$1" pid cmd cwd
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
    case "$cmd" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*/_pane_*.sh*|*"pipeline_monitor.sh"*)
        continue
        ;;
      "bash -c "*|*/bash\ -c\ *|"tee "*)
        continue
        ;;
    esac
    is_control_plane_resume_command "$cmd" && continue
    command_matches_live_keyword "$pattern" "$cmd" || continue
    case "$cmd" in
      *"$REPO_ROOT"* )
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

command_matches_live_keyword() {
  local kw="$1" cmd="$2"
  case "$kw" in
    phase_a_executor|phase_b_executor|commit_executor|executor_dispatch|bridge_supervisor|meta_bridge_supervisor)
      case "$cmd" in
        *"/${kw}.py"*|*" ${kw}.py"*)
          return 0
          ;;
      esac
      return 1
      ;;
    *)
      case "$cmd" in
        *"$kw"*) return 0 ;;
      esac
      return 1
      ;;
  esac
}

repo_has_any_process() {
  local pattern=""
  for pattern in "$@"; do
    repo_has_process "$pattern" && return 0
  done
  return 1
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
  local cmd="$1" lowered=""
  is_control_plane_resume_command "$cmd" && return 1
  lowered="$(printf '%s' "$cmd" | tr '[:upper:]' '[:lower:]')"
  case "$lowered" in
    *"codex exec"*)
      case "$lowered" in
        *"codex.app"*|*"codex helper"*) ;;
        *)
          printf '%s\n' "codex"
          return 0
          ;;
      esac
      ;;
  esac
  case "$lowered" in
    *"claude"*--print*)
      printf '%s\n' "claude"
      return 0
      ;;
  esac
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

repo_has_bridge_role() {
  local wanted_role="$1" pid="" cmd="" cwd=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd="$(pid_command "$pid")"
    case "$cmd" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*/_pane_*.sh*|*"pipeline_monitor.sh"*|"bash -c "*|*/bash\ -c\ *|"tee "*)
        continue
        ;;
    esac
    is_control_plane_resume_command "$cmd" && continue
    bridge_agent_name_for_command "$cmd" >/dev/null || continue
    case "$cmd" in
      *"$REPO_ROOT"* ) ;;
      *)
        cwd="$(pid_cwd "$pid")"
        [ -n "$cwd" ] && [ "$cwd" = "$REPO_ROOT" ] || continue
        ;;
    esac
    if [ "$wanted_role" = "review" ] && pid_has_ancestor_matching "$pid" 'bridge_supervisor\.py review|meta_bridge_supervisor'; then
      return 0
    fi
    if [ "$wanted_role" = "implement" ] && pid_has_ancestor_matching "$pid" 'phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py'; then
      return 0
    fi
  done < <(pgrep -f "codex.*exec|claude.*--print" 2>/dev/null || true)
  return 1
}

render_autoping_status() {
  python3 - "$REPO_ROOT" <<'PY' 2>/dev/null
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
state_dir = Path.home() / ".codex" / "state"
if not state_dir.is_dir():
    raise SystemExit(0)


def parse_stamp(value: object) -> tuple[float, str]:
    if not isinstance(value, str) or not value:
        return (0.0, "")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return (0.0, value)
    return (dt.timestamp(), dt.astimezone().strftime("%H:%M:%S"))


best: tuple[float, dict[str, object]] | None = None
for state_path in state_dir.glob("rcx_autoping_*.json"):
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    if not isinstance(payload, dict):
        continue
    bridge_state = payload.get("bridge_state")
    if not isinstance(bridge_state, dict):
        continue
    wave_root = bridge_state.get("wave_root")
    if not isinstance(wave_root, str):
        continue
    try:
        wave_path = Path(wave_root).resolve()
    except OSError:
        continue
    if wave_path != repo_root:
        continue
    rank, _ = parse_stamp(payload.get("updated_at") or payload.get("last_dispatched_at"))
    if best is None or rank >= best[0]:
        best = (rank, payload)

if best is None:
    raise SystemExit(0)

_, payload = best
summary = ""
summary_path = payload.get("summary_path")
if isinstance(summary_path, str):
    try:
        summary = Path(summary_path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        summary = ""
if not summary:
    value = payload.get("last_summary")
    if isinstance(value, str):
        summary = value.strip()
summary = " ".join(summary.split())
if len(summary) > 140:
    summary = summary[:137].rstrip() + "..."

_, dispatched = parse_stamp(payload.get("last_dispatched_at"))
_, completed = parse_stamp(payload.get("last_completed_at"))
status = payload.get("status")
if not isinstance(status, str) or not status:
    status = "-"

parts = []
if dispatched:
    parts.append(f"last ping {dispatched}")
if completed:
    parts.append(f"last done {completed}")
parts.append(f"status {status}")

print("AUTOPING\t" + " | ".join(parts))
if summary:
    print("SUMMARY\t" + summary)
PY
}

render_pager_status() {
  python3 - "$REPO_ROOT" <<'PY' 2>/dev/null
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
state_path = repo_root / ".agent_bus" / "observability" / "pipeline_agent_pager_state.json"
if not state_path.is_file():
    raise SystemExit(0)

try:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

dispatcher = payload.get("dispatcher")
if not isinstance(dispatcher, dict):
    raise SystemExit(0)
last_dispatch = dispatcher.get("last_dispatch")
if not isinstance(last_dispatch, dict):
    raise SystemExit(0)

if not any(last_dispatch.get(key) for key in ("event_id", "event_type", "summary", "attempted_at")):
    raise SystemExit(0)


def parse_stamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return value


parts = []
attempted = parse_stamp(last_dispatch.get("attempted_at"))
if attempted:
    parts.append(f"last wake {attempted}")
event_type = str(last_dispatch.get("event_type") or "").strip()
if event_type:
    parts.append(event_type)
phase = str(last_dispatch.get("phase") or "").strip()
state = str(last_dispatch.get("state") or "").strip()
if phase or state:
    parts.append(" / ".join(part for part in (phase, state) if part))
target = str(last_dispatch.get("target") or "").strip()
if target:
    parts.append(f"target {target}")
ack = last_dispatch.get("acknowledged")
if ack is True:
    parts.append("ack yes")
elif ack is False:
    parts.append("ack no")

summary = " ".join(str(last_dispatch.get("summary") or "").split())
if len(summary) > 140:
    summary = summary[:137].rstrip() + "..."

print("PAGER\t" + " | ".join(parts))
if summary:
    print("PAGER_SUMMARY\t" + summary)
PY
}

while true; do
  refresh_context
  {
  echo -e "${BOLD}Pane 4: session timeline${RESET}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}This pane shows the recent milestones in time order.${RESET}"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"
  autoping_status="$(render_autoping_status)"
  if [ -n "$autoping_status" ]; then
    while IFS=$'\t' read -r tag value; do
      case "$tag" in
        AUTOPING)
          echo -e "  ${DIM}Autoping:${RESET} $value"
          ;;
        SUMMARY)
          echo -e "  ${DIM}Last ping:${RESET} $value"
          ;;
      esac
    done <<< "$autoping_status"
  fi
  pager_status="$(render_pager_status)"
  if [ -n "$pager_status" ]; then
    while IFS=$'\t' read -r tag value; do
      case "$tag" in
        PAGER)
          echo -e "  ${DIM}Pager:${RESET} $value"
          ;;
        PAGER_SUMMARY)
          echo -e "  ${DIM}Last pager event:${RESET} $value"
          ;;
      esac
    done <<< "$pager_status"
  fi
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
      add_event "$ts" "${PURPLE}${IMPLEMENTER_SHORT} done${RESET} — $(( size / 1024 ))KB output"
    else
      add_event "$ts" "${PURPLE}${IMPLEMENTER_SHORT} implementing${RESET}..."
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

      decision=$(python3 - "$reviewer_file" "$REVIEWER_SHORT" <<'PY' 2>/dev/null
import json
import re
import sys

reviewer_file = sys.argv[1]
reviewer_short = sys.argv[2]
content = open(reviewer_file, errors="replace").read()
matches = list(re.finditer(r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE", content, re.DOTALL))
env = None
for match in reversed(matches):
    candidate = json.loads(match.group(1))
    decision = candidate.get("decision", "")
    if decision and "|" not in decision:
        env = candidate
        break
if env is None:
    raise SystemExit(0)
decision = env.get("decision", "?")
findings = env.get("findings", [])
blocking = sum(1 for item in findings if item.get("disposition") == "blocking")
non_blocking = sum(1 for item in findings if item.get("disposition") != "blocking")
if decision in ("GO", "COMMIT_GO"):
    print(f"\033[32m{reviewer_short}: GO\033[0m ({non_blocking} advisory)")
elif decision == "REQUEST_CHANGES":
    print(f"\033[33m{reviewer_short}: REQUEST_CHANGES\033[0m ({blocking}B {non_blocking}NB)")
elif decision == "NO_GO":
    print(f"\033[31m{reviewer_short}: NO_GO\033[0m ({blocking} blocker, {non_blocking} advisory)")
else:
    print(f"{reviewer_short}: {decision} ({blocking}B {non_blocking}NB)")
PY
)
      [ -n "$decision" ] && add_event "$ts" "$decision"

      # Also add the start time (reader file = when review started)
      reader_file=$(ls -t "$dir"/*reader*.txt 2>/dev/null | head -1) || true
      if [ -n "$reader_file" ]; then
        start_ts=$(file_time "$reader_file")
        add_event "$start_ts" "${YELLOW}${REVIEWER_SHORT} reviewing${RESET}..."
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
  if repo_has_bridge_role "review"; then
    echo -e "  ${DIM}${now}${RESET}  ${YELLOW}← ${REVIEWER_SHORT} reviewing now${RESET}"
  elif repo_has_bridge_role "implement"; then
    echo -e "  ${DIM}${now}${RESET}  ${PURPLE}← ${IMPLEMENTER_SHORT} implementing now${RESET}"
  elif repo_has_process "run_review.py"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← SDK review agents checking this worktree now${RESET}"
  elif repo_has_any_process "phase_a_executor" "phase_b_executor" "commit_executor" "executor_dispatch"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← pipeline executor working in this worktree now${RESET}"
  else
    echo -e "  ${DIM}${now}${RESET}  ${DIM}← idle${RESET}"
  fi

  # Helpful reference
  echo ""
  echo -e "${DIM}Typical durations:${RESET}"
  echo -e "${DIM}  ${IMPLEMENTER_SHORT} impl: 5-15m | Agents: 3-5m | ${REVIEWER_SHORT} review: 10-20m${RESET}"
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

  if [ "$ONESHOT" = "1" ]; then
    rm -f "$TMPOUT"
    exit 0
  fi

  sleep 5
done
