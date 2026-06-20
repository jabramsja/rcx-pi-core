#!/usr/bin/env bash
# _pane_timeline.sh — Session timeline pane for tmux
# Shows chronological history of what happened this pipeline run.
set +e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUS_DIR="${RCX_AGENT_BUS_DIR:-${BUS_DIR:-.agent_bus}}"
if [[ "$BUS_DIR" == /* || "$BUS_DIR" == *"/"* || "$BUS_DIR" == *"\\"* || "$BUS_DIR" == *".."* ]]; then
  echo "ERROR: invalid RCX_AGENT_BUS_DIR: $BUS_DIR" >&2
  exit 2
fi
if [[ "$BUS_DIR" != ".agent_bus" && ! "$BUS_DIR" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "ERROR: RCX_AGENT_BUS_DIR must be .agent_bus or .agent_bus-<id>" >&2
  exit 2
fi
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
  # Optional autofollow (WI-2B): when RCX_OBS_AUTOFOLLOW_BUS=1, re-resolve the
  # freshest active (root,bus) pair each refresh and rebind the effective bus so
  # the default monitor's panes follow the freshest active lane. Fail-safe: empty
  # or invalid helper output keeps the CURRENT bus (never blank, never error,
  # validation unchanged). Signal unset = today's behavior exactly.
  if [ "${RCX_OBS_AUTOFOLLOW_BUS:-}" = "1" ]; then
    local _af_helper="$SCRIPT_DIR/_resolve_live_root.sh" _af_root="" _af_bus=""
    if [ -f "$_af_helper" ]; then
      { IFS= read -r _af_root; IFS= read -r _af_bus; } < <(RCX_AGENT_BUS_DIR="$BUS_DIR" bash "$_af_helper" --emit-pair 2>/dev/null) || true
    fi
    if [ -n "$_af_root" ] && { [ "$_af_bus" = ".agent_bus" ] || [[ "$_af_bus" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; }; then
      BUS_DIR="$_af_bus"
      export BUS_DIR
      export RCX_AGENT_BUS_DIR="$_af_bus"
      next_root="$_af_root"
    fi
  fi
  [ -n "$next_root" ] || next_root="$(resolve_repo_root)"
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
VERBOSE="${RCX_PANE_VERBOSE:-0}"
PROCESS_SCAN_LIMIT="${RCX_PANE_PROCESS_SCAN_LIMIT:-32}"
if ! [[ "$PROCESS_SCAN_LIMIT" =~ ^[0-9]+$ ]] || [ "$PROCESS_SCAN_LIMIT" -lt 1 ]; then
  PROCESS_SCAN_LIMIT=32
fi

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

bridge_agent_display_name_for_agent() {
  local agent="$1" root="${2:-$REPO_ROOT}" bus="${3:-$BUS_DIR}" output=""
  [ -n "$agent" ] || return 1
  output="$(python3 - "$root" "$bus" "$agent" <<'PY' 2>/dev/null
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
bus_dir = sys.argv[2]
agent = sys.argv[3]
sys.path.insert(0, str(repo_root / "mu" / "tools" / "executors"))
try:
    from executor_common import bridge_agent_status_name
    print(bridge_agent_status_name(repo_root, agent, bus_dir))
except Exception:
    print(agent.replace("_", " ").title().split()[0])
PY
)"
  [ -n "$output" ] && printf '%s\n' "$output" || printf '%s\n' "$agent"
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

pgrep_limited() {
  local pattern="$1"
  # Do not cap before repo-root filtering. A machine can have many global
  # Codex/Claude processes, and the relevant bridge worker may be later in the
  # process list. Callers filter by repo root before rendering rows.
  pgrep -f "$pattern" 2>/dev/null
}

is_control_plane_resume_command() {
  local cmd="$1"
  case "$cmd" in
    *"Autonomous WorkingRCX pipeline watchdog tick."*|*"WorkingRCX pipeline pager wakeup."*|*"WorkingRCX dedicated Claude monitor keepalive tick."*)
      return 0
      ;;
  esac
  return 1
}

repo_has_process() {
  local pattern="$1" pid cmd
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
    pid_matches_repo_root "$pid" || continue
    pid_matches_selected_bus_dir "$pid" || continue
    return 0
  done < <(pgrep_limited "$pattern")
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

pid_matches_repo_root() {
  local pid="$1" cmd="" cwd=""
  cmd="$(pid_command "$pid")"
  case "$cmd" in
    *"$REPO_ROOT"*) return 0 ;;
  esac
  cwd="$(pid_cwd "$pid")"
  [ -n "$cwd" ] && [ "$cwd" = "$REPO_ROOT" ]
}

command_bus_markers() {
  python3 - "$1" <<'PY' 2>/dev/null
from __future__ import annotations

import re
import shlex
import sys

command = sys.argv[1]
markers: list[str] = []
try:
    tokens = shlex.split(command)
except ValueError:
    tokens = command.split()
for index, token in enumerate(tokens):
    if token == "--bus-dir" and index + 1 < len(tokens):
        markers.append(tokens[index + 1])
    elif token.startswith("--bus-dir="):
        markers.append(token.split("=", 1)[1])
pattern = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<bus>\.agent_bus(?:-[A-Za-z0-9][A-Za-z0-9_-]*)?)"
    r"(?=$|[/'\"\s:=])"
)
for match in pattern.finditer(command):
    marker = match.group("bus")
    if marker not in markers:
        markers.append(marker)
for marker in markers:
    print(marker)
PY
}

pid_matches_selected_bus_dir() {
  local pid="$1" current="$1" depth=0 parent="" cmd="" marker="" saw_marker=0
  while [ "$depth" -lt 8 ]; do
    if [ -z "$current" ]; then
      [ "$saw_marker" = "1" ] || [ "$BUS_DIR" = ".agent_bus" ]
      return $?
    fi
    cmd="$(pid_command "$current")"
    while IFS= read -r marker; do
      [ -z "$marker" ] && continue
      saw_marker=1
      [ "$marker" = "$BUS_DIR" ] || return 1
    done < <(command_bus_markers "$cmd")
    parent="$(pid_ppid "$current")"
    if [ -z "$parent" ] || [ "$parent" = "1" ]; then
      [ "$saw_marker" = "1" ] || [ "$BUS_DIR" = ".agent_bus" ]
      return $?
    fi
    current="$parent"
    depth=$((depth + 1))
  done
  [ "$saw_marker" = "1" ] || [ "$BUS_DIR" = ".agent_bus" ]
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
  local wanted_role="$1" pid="" cmd=""
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
    if [ "$wanted_role" = "review" ] && pid_has_ancestor_matching "$pid" 'bridge_supervisor\.py([[:space:]][^[:space:]]+)*[[:space:]]review([[:space:]]|$)|meta_bridge_supervisor'; then
      pid_matches_repo_root "$pid" || continue
      pid_matches_selected_bus_dir "$pid" || continue
      return 0
    fi
    if [ "$wanted_role" = "implement" ] && pid_has_ancestor_matching "$pid" 'phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py'; then
      pid_matches_repo_root "$pid" || continue
      pid_matches_selected_bus_dir "$pid" || continue
      return 0
    fi
  done < <(pgrep_limited "codex.*exec|claude.*--print")
  return 1
}

repo_bridge_agent_for_role() {
  local wanted_role="$1" pid="" cmd="" agent=""
  while IFS= read -r pid; do
    [ -z "$pid" ] && continue
    cmd="$(pid_command "$pid")"
    case "$cmd" in
      *"tail -f "*|*"rcx_log_watcher.sh"*|*/_pane_*.sh*|*"pipeline_monitor.sh"*|"bash -c "*|*/bash\ -c\ *|"tee "*)
        continue
        ;;
    esac
    is_control_plane_resume_command "$cmd" && continue
    agent="$(bridge_agent_name_for_command "$cmd" 2>/dev/null || true)"
    [ -n "$agent" ] || continue
    if [ "$wanted_role" = "review" ] && ! pid_has_ancestor_matching "$pid" 'bridge_supervisor\.py([[:space:]][^[:space:]]+)*[[:space:]]review([[:space:]]|$)|meta_bridge_supervisor'; then
      continue
    fi
    if [ "$wanted_role" = "implement" ] && ! pid_has_ancestor_matching "$pid" 'phase_b_executor\.py|phase_a_executor\.py|commit_executor\.py'; then
      continue
    fi
    pid_matches_repo_root "$pid" || continue
    pid_matches_selected_bus_dir "$pid" || continue
    printf '%s\n' "$agent"
    return 0
  done < <(pgrep_limited "codex.*exec|claude.*--print")
  return 1
}

render_autoping_status() {
  python3 - "$REPO_ROOT" <<'PY' 2>/dev/null
from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
codex_home_raw = os.environ.get("RCX_CODEX_HOME") or os.environ.get("CODEX_HOME")
codex_home = Path(codex_home_raw).expanduser() if codex_home_raw else Path.home() / ".codex"
state_dir = codex_home / "state"
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


def age_text(rank: float) -> str:
    if rank <= 0:
        return ""
    elapsed = max(0, int(datetime.now().timestamp() - rank))
    if elapsed < 60:
        return f"{elapsed}s old"
    if elapsed < 3600:
        return f"{elapsed // 60}m old"
    return f"{elapsed // 3600}h {(elapsed % 3600) // 60}m old"


def clip_text(value: str, limit: int = 260) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def compact_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    text = value.strip()
    home = str(Path.home())
    if text == home:
        return "~"
    if text.startswith(home + "/"):
        return "~" + text[len(home):]
    try:
        path = Path(text)
        if path.is_absolute():
            return str(path)
    except OSError:
        pass
    return text


def short_id(value: object, width: int = 12) -> str:
    text = str(value or "").strip()
    if len(text) <= width:
        return text
    return text[:width]


def print_wrapped(tag: str, text: str, *, width: int = 108, max_lines: int = 3) -> None:
    lines = textwrap.wrap(
        " ".join(text.split()),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    truncated = len(lines) > max_lines
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if truncated:
        lines[-1] = clip_text(lines[-1].rstrip() + " ...", width)
    for index, line in enumerate(lines):
        print(f"{tag if index == 0 else tag + '_CONT'}\t{line}")


best: tuple[float, Path, dict[str, object]] | None = None
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
    rank = max(
        parse_stamp(payload.get("updated_at"))[0],
        parse_stamp(payload.get("last_dispatched_at"))[0],
        parse_stamp(payload.get("last_completed_at"))[0],
    )
    if best is None or rank >= best[0]:
        best = (rank, state_path, payload)

if best is None:
    raise SystemExit(0)

_, state_path, payload = best
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
summary = clip_text(summary)

_, dispatched = parse_stamp(payload.get("last_dispatched_at"))
_, completed = parse_stamp(payload.get("last_completed_at"))
updated_rank, updated = parse_stamp(payload.get("updated_at"))
status = payload.get("status")
if not isinstance(status, str) or not status:
    status = "-"

parts = []
if dispatched:
    parts.append(f"last ping {dispatched}")
if completed:
    parts.append(f"last done {completed}")
if updated:
    age = age_text(updated_rank)
    parts.append(f"state updated {updated}" + (f" ({age})" if age else ""))
parts.append(f"status {status}")

print("AUTOPING\t" + " | ".join(parts))
detail_parts = []
thread_id = short_id(payload.get("thread_id"))
if thread_id:
    detail_parts.append(f"thread {thread_id}")
watcher_pid = str(payload.get("watcher_pid") or "").strip()
if watcher_pid:
    detail_parts.append(f"watcher pid {watcher_pid}")
active_pid = str(payload.get("active_pid") or "").strip()
if active_pid:
    detail_parts.append(f"active pid {active_pid}")
last_pid = str(payload.get("last_dispatched_pid") or "").strip()
if last_pid:
    detail_parts.append(f"last ping pid {last_pid}")
if updated:
    age = age_text(updated_rank)
    detail_parts.append(f"updated {updated}" + (f" ({age})" if age else ""))
if detail_parts:
    print("AUTOPING_DETAIL\t" + " | ".join(detail_parts))
print("AUTOPING_STATE_PATH\t" + compact_path(str(state_path)))
summary_display = compact_path(summary_path)
if summary_display:
    print("AUTOPING_SUMMARY_PATH\t" + summary_display)
if summary:
    print_wrapped("SUMMARY", summary)
PY
}

render_pager_status() {
  python3 - "$REPO_ROOT" "$BUS_DIR" <<'PY' 2>/dev/null
from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
bus_dir = sys.argv[2]
state_path = repo_root / bus_dir / "observability" / "pipeline_agent_pager_state.json"
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


def clip_text(value: str, limit: int = 260) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def short_id(value: object, width: int = 12) -> str:
    text = str(value or "").strip()
    if len(text) <= width:
        return text
    return text[:width]


def join_values(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return ",".join(str(value).strip() for value in values if str(value).strip())


def print_wrapped(tag: str, text: str, *, width: int = 108, max_lines: int = 3) -> None:
    lines = textwrap.wrap(
        " ".join(text.split()),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    truncated = len(lines) > max_lines
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if truncated:
        lines[-1] = clip_text(lines[-1].rstrip() + " ...", width)
    for index, line in enumerate(lines):
        print(f"{tag if index == 0 else tag + '_CONT'}\t{line}")


parts = []
attempted = parse_stamp(last_dispatch.get("attempted_at"))
if attempted:
    parts.append(attempted)
event_type = str(last_dispatch.get("event_type") or "").strip()
if event_type:
    parts.append(event_type)
phase = str(last_dispatch.get("phase") or "").strip()
state = str(last_dispatch.get("state") or "").strip()
if phase or state:
    parts.append("/".join(part for part in (phase, state) if part))
target = str(last_dispatch.get("target") or "").strip()
if target:
    parts.append(target)
ack = last_dispatch.get("acknowledged")
if ack is True:
    parts.append("ack yes")
elif ack is False:
    parts.append("ack no")

summary = clip_text(str(last_dispatch.get("summary") or ""))

print("PAGER_WAKE\t" + " | ".join(parts))
event_id = str(last_dispatch.get("event_id") or "").strip()
detail_parts = []
if event_id:
    detail_parts.append(f"event {short_id(event_id)}")
wave_id = str(last_dispatch.get("wave_id") or "").strip()
if wave_id:
    detail_parts.append(f"wave {wave_id}")
completed = parse_stamp(last_dispatch.get("completed_at"))
if completed:
    detail_parts.append(f"done {completed}")
if detail_parts:
    print("PAGER_DETAIL\t" + " | ".join(detail_parts))
transition_key = str(last_dispatch.get("transition_key") or "").strip()
if transition_key:
    print("PAGER_TRANSITION\t" + transition_key)
events = payload.get("events")
event_state = events.get(event_id) if isinstance(events, dict) and event_id else None
state_parts = []
if isinstance(event_state, dict):
    route = str(event_state.get("route") or "").strip()
    if route:
        state_parts.append(f"route {route}")
    pending = join_values(event_state.get("pending_targets"))
    state_parts.append(f"pending {pending or 'none'}")
    requested = join_values(event_state.get("requested_targets"))
    if requested:
        state_parts.append(f"requested {requested}")
    delivered = join_values(sorted((event_state.get("delivered_targets") or {}).keys())) if isinstance(event_state.get("delivered_targets"), dict) else ""
    if delivered:
        state_parts.append(f"delivered {delivered}")
    attempts = event_state.get("attempts")
    if isinstance(attempts, dict) and attempts:
        attempt_bits = []
        for attempt_target, attempt_data in sorted(attempts.items()):
            count = ""
            if isinstance(attempt_data, dict):
                count = str(attempt_data.get("count") or "").strip()
            label = str(attempt_target or "").strip()
            if label:
                attempt_bits.append(f"{label}:{count or '?'}")
        if attempt_bits:
            state_parts.append("attempts " + ",".join(attempt_bits))
if state_parts:
    print("PAGER_STATE\t" + " | ".join(state_parts))
error = str(last_dispatch.get("error") or "").strip()
if error:
    print_wrapped("PAGER_ERROR", error)
print(f"PAGER_STATE_PATH\t{bus_dir}/observability/pipeline_agent_pager_state.json")
print(f"PAGER_EVENTS_PATH\t{bus_dir}/observability/pipeline_agent_events.jsonl")
print(f"PAGER_RECEIPTS_PATH\t{bus_dir}/observability/pipeline_agent_delivery_receipts.jsonl")
if summary:
    print_wrapped("PAGER_SUMMARY", summary)
PY
}

print_observability_status() {
  local autoping_latest="" pager_latest=""
  autoping_status="$(render_autoping_status)"
  if [ -n "$autoping_status" ]; then
    while IFS=$'\t' read -r tag value; do
      case "$tag" in
        AUTOPING)
          autoping_latest="$value"
          echo -e "  ${DIM}Autoping:${RESET} $value"
          ;;
        AUTOPING_DETAIL)
          echo -e "  ${DIM}Autoping detail:${RESET} $value"
          ;;
        AUTOPING_STATE_PATH)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Autoping state:${RESET} $value"
          ;;
        AUTOPING_SUMMARY_PATH)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Autoping summary file:${RESET} $value"
          ;;
        SUMMARY)
          echo -e "  ${DIM}Autoping summary:${RESET} $value"
          ;;
        SUMMARY_CONT)
          echo -e "  ${DIM}                 ${RESET} $value"
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
        PAGER_WAKE)
          pager_latest="$value"
          echo -e "  ${DIM}Last pager wake:${RESET} $value"
          ;;
        PAGER_DETAIL)
          echo -e "  ${DIM}Pager detail:${RESET} $value"
          ;;
        PAGER_TRANSITION)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Pager transition:${RESET} $value"
          ;;
        PAGER_STATE)
          echo -e "  ${DIM}Pager state:${RESET} $value"
          ;;
        PAGER_ERROR)
          echo -e "  ${DIM}Pager error:${RESET} $value"
          ;;
        PAGER_ERROR_CONT)
          echo -e "  ${DIM}            ${RESET} $value"
          ;;
        PAGER_STATE_PATH)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Pager state file:${RESET} $value"
          ;;
        PAGER_EVENTS_PATH)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Pager events log:${RESET} $value"
          ;;
        PAGER_RECEIPTS_PATH)
          [ "$VERBOSE" = "1" ] && echo -e "  ${DIM}Pager receipts:${RESET} $value"
          ;;
        PAGER_SUMMARY)
          echo -e "  ${DIM}Last pager event:${RESET} $value"
          ;;
        PAGER_SUMMARY_CONT)
          echo -e "  ${DIM}                 ${RESET} $value"
          ;;
      esac
    done <<< "$pager_status"
  fi
  if [ -n "$autoping_latest" ] || [ -n "$pager_latest" ]; then
    echo ""
    echo -e "  ${BOLD}Wake status pinned:${RESET}"
    [ -n "$autoping_latest" ] && echo -e "  ${DIM}Autoping latest:${RESET} $autoping_latest"
    [ -n "$pager_latest" ] && echo -e "  ${DIM}Pager latest:${RESET} $pager_latest"
  fi
}

# Main-guard the infinite refresh driver so the test can source this script and
# call refresh_context() in isolation. Running `bash _pane_timeline.sh` normally
# keeps $0 == BASH_SOURCE, so the loop still runs unchanged.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
while true; do
  refresh_context
  {
  echo -e "${BOLD}Pane 4: session timeline${RESET}  $(date '+%H:%M:%S')"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "  ${DIM}This pane shows the recent milestones in time order.${RESET}"
  echo -e "  ${DIM}Watching:${RESET} $BRANCH_NAME"
  echo -e "  ${DIM}Worktree:${RESET} $REPO_ROOT"

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
  RAW_DIR="$REPO_ROOT/$BUS_DIR/raw"
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
  review_agent="$(repo_bridge_agent_for_role "review" 2>/dev/null || true)"
  impl_agent="$(repo_bridge_agent_for_role "implement" 2>/dev/null || true)"
  if [ -n "$review_agent" ]; then
    echo -e "  ${DIM}${now}${RESET}  ${YELLOW}← $(bridge_agent_display_name_for_agent "$review_agent") reviewing now${RESET}"
  elif [ -n "$impl_agent" ]; then
    echo -e "  ${DIM}${now}${RESET}  ${PURPLE}← $(bridge_agent_display_name_for_agent "$impl_agent") implementing now${RESET}"
  elif repo_has_process "run_review.py"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← SDK review agents checking this worktree now${RESET}"
  elif repo_has_any_process "phase_a_executor" "phase_b_executor" "commit_executor" "executor_dispatch"; then
    echo -e "  ${DIM}${now}${RESET}  ${CYAN}← pipeline executor working in this worktree now${RESET}"
  else
    echo -e "  ${DIM}${now}${RESET}  ${DIM}← idle${RESET}"
  fi
  echo ""

  # Helpful reference
  echo -e "${DIM}Typical durations:${RESET}"
  echo -e "${DIM}  ${IMPLEMENTER_SHORT} impl: 5-15m | Agents: 3-5m | ${REVIEWER_SHORT} review: 10-20m${RESET}"
  echo -e "${DIM}  NO_GO is normal — usually 2-3 rounds to converge${RESET}"
  echo ""
  print_observability_status

  } > "$TMPOUT" 2>/dev/null

  # Only redraw if content changed (ignore first line with title)
  NEW_HASH=$(tail -n +2 "$TMPOUT" 2>/dev/null | md5 -q 2>/dev/null || tail -n +2 "$TMPOUT" | md5sum 2>/dev/null | cut -d' ' -f1)
  if [ "$NEW_HASH" != "$LAST_HASH" ]; then
    printf '\033[H\033[2J\033[3J'
    cat "$TMPOUT"
    LAST_HASH="$NEW_HASH"
  else
    # Data unchanged — just update timestamp so user knows it's alive
    printf '\033[H\033[2K'
    echo -e "${BOLD}Pane 4: session timeline${RESET}  $(date '+%H:%M:%S')"
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
fi
