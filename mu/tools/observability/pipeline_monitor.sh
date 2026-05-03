#!/usr/bin/env bash
# pipeline_monitor.sh — Real-time pipeline observability via tmux
# Read-only by default. Action commands (clear-lock, nudge, kill) are explicit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS_SCRIPT="$SCRIPT_DIR/pipeline_status.sh"
BUS_DIR="${RCX_AGENT_BUS_DIR:-.agent_bus}"
LANE="${RCX_PIPELINE_MONITOR_LANE:-}"
REQUESTED_LANE="$LANE"
while [ $# -gt 0 ]; do
  case "${1:-}" in
    --bus-dir)
      if [ $# -lt 2 ]; then
        echo "ERROR: --bus-dir requires a value" >&2
        exit 2
      fi
      BUS_DIR="${2:-}"
      shift 2
      ;;
    --lane)
      if [ $# -lt 2 ]; then
        echo "ERROR: --lane requires a value" >&2
        exit 2
      fi
      LANE="${2:-}"
      REQUESTED_LANE="$LANE"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done
case "$BUS_DIR" in
  /*|*/*|*\\*|*..*|"")
    echo "ERROR: invalid --bus-dir: $BUS_DIR" >&2
    exit 2
    ;;
esac
if [[ "$BUS_DIR" != ".agent_bus" && ! "$BUS_DIR" =~ ^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "ERROR: --bus-dir must be .agent_bus or .agent_bus-<id>" >&2
  exit 2
fi

resolve_observability_repo_root() {
  local root="" current_root=""
  current_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$current_root" ]; then
    printf '%s\n' "$current_root"
    return 0
  fi
  if [ -f "$STATUS_SCRIPT" ]; then
    root=$(RCX_AGENT_BUS_DIR="$BUS_DIR" bash "$STATUS_SCRIPT" --bus-dir "$BUS_DIR" --print-root 2>/dev/null || true)
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
BUS_PATH="$REPO_ROOT/$BUS_DIR"
COMMAND="${1:-}"
SESSION="rcx-pipeline"
DASHBOARD_PORT="8099"
IDENTITY_LANE="default"
IDENTITY_HELPER="$SCRIPT_DIR/pipeline_monitor_identity.py"

identity_requires_config() {
  case "$COMMAND" in
    start|stop|attach) return 0 ;;
    *) [ -n "$LANE" ] ;;
  esac
}

resolve_monitor_identity() {
  local helper_args=(
    python3 "$IDENTITY_HELPER"
    --repo-root "$REPO_ROOT"
    --bus-dir "$BUS_DIR"
    --format shell
  )
  if [ -n "$LANE" ]; then
    helper_args+=(--lane "$LANE")
  fi
  if ! identity_requires_config; then
    helper_args+=(--allow-unconfigured-named-bus)
  fi
  local output="" error_file=""
  error_file="$(mktemp "${TMPDIR:-/tmp}/rcx_monitor_identity.XXXXXX")"
  if ! output="$("${helper_args[@]}" 2>"$error_file")"; then
    cat "$error_file" >&2
    rm -f "$error_file"
    exit 2
  fi
  rm -f "$error_file"
  eval "$output"
  SESSION="$RCX_MONITOR_TMUX_SESSION"
  DASHBOARD_PORT="$RCX_MONITOR_DASHBOARD_PORT"
  BUS_DIR="$RCX_MONITOR_BUS_DIR"
  BUS_PATH="$RCX_MONITOR_BUS_PATH"
  IDENTITY_LANE="$RCX_MONITOR_LANE"
}

if [ -f "$IDENTITY_HELPER" ]; then
  resolve_monitor_identity
elif identity_requires_config && { [ "$BUS_DIR" != ".agent_bus" ] || [ -n "$LANE" ]; }; then
  echo "ERROR: monitor identity helper missing: $IDENTITY_HELPER" >&2
  exit 2
fi

LIVE_LOG_KEY="$(printf '%s' "$REPO_ROOT" | cksum | awk '{print $1}')"
LIVE_LOG="${RCX_PIPELINE_LIVE_LOG:-/tmp/rcx_pipeline_live_${LIVE_LOG_KEY}.txt}"
SESSION_WIDTH="${RCX_PIPELINE_TMUX_WIDTH:-240}"
SESSION_HEIGHT="${RCX_PIPELINE_TMUX_HEIGHT:-70}"
STATE_DIR="${RCX_PIPELINE_MONITOR_STATE_DIR:-${TMPDIR:-/tmp}/rcx_pipeline_monitor/$SESSION}"
OWNER_PID_FILE="$STATE_DIR/owner.pid"
OWNER_ROOT_FILE="$STATE_DIR/owner.root"
OWNER_LOCK_DIR="$STATE_DIR/owner.lock"
OWNER_LOCK_PID_FILE="$OWNER_LOCK_DIR/pid"
OWNER_REGISTRY_DIR="$STATE_DIR/owners"
OWNER_INTERVAL_SECONDS="${RCX_PIPELINE_MONITOR_HEALTH_INTERVAL:-5}"
EXPECTED_PANE_1="PANE 1 · LIVE PIPELINE LOG"
EXPECTED_PANE_2="PANE 2 · REVIEW FINDINGS"
EXPECTED_PANE_3="PANE 3 · PLAIN-ENGLISH STATUS"
EXPECTED_PANE_4="PANE 4 · SESSION TIMELINE"

usage() {
  cat <<'EOF'
Usage: pipeline_monitor.sh [--bus-dir .agent_bus[-id]] [--lane name] <command> [options]

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
# Keep the freshest real phase log visible for longer after a run ends so the
# monitor still shows the last live failure/success instead of blanking almost
# immediately.
IDLE_WINDOW_SECONDS=3600
LOG_WATCHER_HEARTBEAT_SECONDS="${RCX_LOG_WATCHER_HEARTBEAT_SECONDS:-300}"
case "$LOG_WATCHER_HEARTBEAT_SECONDS" in
  ""|*[!0-9]*) LOG_WATCHER_HEARTBEAT_SECONDS=300 ;;
esac
current_log=""
tail_pid=""
last_heartbeat_epoch=0
BUS_DIR="${RCX_AGENT_BUS_DIR:-${BUS_DIR:-.agent_bus}}"

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

resolve_live_log() {
  if [ -n "${RCX_PIPELINE_LIVE_LOG:-}" ]; then
    printf '%s\n' "$RCX_PIPELINE_LIVE_LOG"
    return 0
  fi
  local repo_root="" key=""
  repo_root="$(resolve_repo_root)"
  key="$(printf '%s' "$repo_root" | cksum | awk '{print $1}')"
  printf '/tmp/rcx_pipeline_live_%s.txt\n' "$key"
}

LIVE_LOG="$(resolve_live_log)"

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

file_has_visible_content() {
  local path="$1"
  [ -s "$path" ] || return 1
  grep -q '[^[:space:]]' "$path" 2>/dev/null
}

now_seconds() {
  date +%s
}

heartbeat_due() {
  if [ "$LOG_WATCHER_HEARTBEAT_SECONDS" -le 0 ]; then
    return 0
  fi
  local now=""
  now="$(now_seconds)"
  if [ "$last_heartbeat_epoch" -eq 0 ]; then
    return 0
  fi
  [ $(( now - last_heartbeat_epoch )) -ge "$LOG_WATCHER_HEARTBEAT_SECONDS" ]
}

find_newest_recent_log() {
  local newest=""
  newest="$(
    shopt -s nullglob
    for candidate in "$@"; do
      [ -f "$candidate" ] || continue
      file_is_recent "$candidate" || continue
      file_has_visible_content "$candidate" || continue
      printf '%s\t%s\n' "$(file_mtime_seconds "$candidate")" "$candidate"
    done | sort -rn -k1,1 | head -1 | cut -f2-
  )"
  printf '%s\n' "$newest"
}

find_newest_log() {
  local repo_root=""
  # Live tee output (from 'exec' command) takes priority
  if file_is_recent "$LIVE_LOG" && file_has_visible_content "$LIVE_LOG"; then
    echo "$LIVE_LOG"
    return
  fi
  # After the explicit live tee log, choose the freshest real pipeline surface
  # across reviewer transcripts and stdout/live logs. Bridge stderr placeholders
  # stay in a final fallback tier so they cannot outrank fresher real output.
  repo_root="$(resolve_repo_root)"
  [ -n "$repo_root" ] || return
  local newest=""
  newest="$(find_newest_recent_log \
    "$repo_root"/"$BUS_DIR"/raw/phase-b-*/*reviewer*.txt \
    "$repo_root"/"$BUS_DIR"/raw/phase-a-*/*reviewer*.txt \
    "$repo_root"/.scratch/commit_executor_live.log \
    "$repo_root"/.scratch/phase_a_executor_live.log \
    "$repo_root"/.scratch/phase_b_executor_live.log \
    "$repo_root"/.scratch/phase_b_implementer_output_*.txt \
    "$repo_root"/.scratch/phase_a_agent_review_*.stdout.log \
    "$repo_root"/.scratch/phase_b_agent_review_*.stdout.log \
    "$repo_root"/.scratch/phase_a_bridge_*.stdout.log \
    "$repo_root"/.scratch/phase_b_bridge_*.stdout.log \
    /tmp/phase_b_*.txt /tmp/commit_*.txt /tmp/phase_a_*.txt)"
  if [ -n "$newest" ]; then
    echo "$newest"
    return
  fi
  newest="$(find_newest_recent_log \
    "$repo_root"/.scratch/phase_b_bridge_*.stderr.log)"
  if [ -n "$newest" ]; then
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
  echo "  No active pipeline log in the last 1 hour."
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
    last_heartbeat_epoch="$(now_seconds)"
  fi
}

refresh_tail_if_due() {
  local active_log="$1"
  [ -n "$active_log" ] || return 0
  if heartbeat_due; then
    switch_tail "$active_log"
  fi
}

while true; do
  newest=$(find_newest_log) || newest=""
  if [ -n "$newest" ] && [ "$newest" != "$current_log" ]; then
    switch_tail "$newest"
  elif [ -n "$newest" ] && [ "$newest" = "$current_log" ]; then
    refresh_tail_if_due "$newest"
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

normalize_path() {
  local path="$1"
  (
    cd "$path" 2>/dev/null && pwd -P
  ) || printf '%s\n' "$path"
}

ensure_state_dir() {
  mkdir -p "$STATE_DIR"
}

owner_registry_file() {
  local pid="$1"
  printf '%s\n' "$OWNER_REGISTRY_DIR/$pid.pid"
}

current_owner_pid() {
  [ -f "$OWNER_PID_FILE" ] || return 1
  tr -d '[:space:]' < "$OWNER_PID_FILE"
}

current_owner_lock_pid() {
  [ -f "$OWNER_LOCK_PID_FILE" ] || return 1
  tr -d '[:space:]' < "$OWNER_LOCK_PID_FILE"
}

process_command_line() {
  local pid="$1"
  ps -ww -p "$pid" -o command= 2>/dev/null || ps -p "$pid" -o command= 2>/dev/null || true
}

process_cwd() {
  local pid="$1" cwd=""
  if [ -e "/proc/$pid/cwd" ]; then
    (
      cd "/proc/$pid/cwd" 2>/dev/null && pwd -P
    ) && return 0
  fi
  cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1 || true)"
  [ -n "$cwd" ] && normalize_path "$cwd"
}

owner_expected_root() {
  normalize_path "$REPO_ROOT"
}

owner_record_root() {
  local pid="$1" entry="" recorded_pid=""
  entry="$(owner_registry_file "$pid")"
  if [ -f "$entry" ]; then
    sed -n 's/^repo_root=//p' "$entry" | head -1
    return 0
  fi
  recorded_pid="$(current_owner_pid 2>/dev/null || true)"
  if [ -n "$recorded_pid" ] && [ "$recorded_pid" = "$pid" ] && [ -f "$OWNER_ROOT_FILE" ]; then
    head -1 "$OWNER_ROOT_FILE"
    return 0
  fi
  return 1
}

owner_command_matches_root() {
  local cmd="$1" expected_root="$2"
  case "$cmd" in
    *"$expected_root"/mu/tools/observability/pipeline_monitor.sh*__owner-loop*|*"$expected_root"/tools/observability/pipeline_monitor.sh*__owner-loop*)
      return 0
      ;;
  esac
  return 1
}

owner_command_has_absolute_monitor_path() {
  local cmd="$1"
  printf '%s\n' "$cmd" | grep -Eq '(^|[[:space:]])/[^[:space:]]*/(mu/tools/observability/pipeline_monitor\.sh|tools/observability/pipeline_monitor\.sh)([[:space:]]|$).*__owner-loop'
}

owner_process_has_monitor_command() {
  local pid="$1" cmd=""
  case "$pid" in
    ''|*[!0-9]*)
      return 1
      ;;
  esac
  kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(process_command_line "$pid")"
  [ -n "$cmd" ] || return 1
  case "$cmd" in
    *pipeline_monitor.sh*__owner-loop*)
      return 0
      ;;
  esac
  return 1
}

owner_process_matches_root() {
  local pid="$1" expected_root="$2" cmd="" record_root="" cwd=""
  owner_process_has_monitor_command "$pid" || return 1
  cmd="$(process_command_line "$pid")"
  owner_command_matches_root "$cmd" "$expected_root" && return 0
  if owner_command_has_absolute_monitor_path "$cmd"; then
    return 1
  fi
  record_root="$(owner_record_root "$pid" 2>/dev/null || true)"
  if [ "$record_root" = "$expected_root" ]; then
    cwd="$(process_cwd "$pid" 2>/dev/null || true)"
    [ -n "$cwd" ] && [ "$(normalize_path "$cwd")" = "$expected_root" ]
    return $?
  fi
  return 1
}

owner_process_verified() {
  local pid="$1" expected_root=""
  expected_root="$(owner_expected_root)"
  owner_process_matches_root "$pid" "$expected_root"
}

clear_owner_pid_record() {
  local pid="$1"
  [ -n "$pid" ] && rm -f "$(owner_registry_file "$pid")"
  if [ -n "$pid" ] && [ "$(current_owner_pid 2>/dev/null || true)" = "$pid" ]; then
    rm -f "$OWNER_PID_FILE" "$OWNER_ROOT_FILE"
  fi
  rmdir "$OWNER_REGISTRY_DIR" 2>/dev/null || true
}

owner_is_live() {
  local pid=""
  pid="$(current_owner_pid 2>/dev/null || true)"
  if [ -z "$pid" ]; then
    return 1
  fi
  if owner_process_verified "$pid"; then
    return 0
  fi
  clear_owner_pid_record "$pid"
  return 1
}

record_owner_pid() {
  local pid="$1" root=""
  root="$(owner_expected_root)"
  mkdir -p "$OWNER_REGISTRY_DIR"
  printf '%s\n' "$pid" > "$OWNER_PID_FILE"
  printf '%s\n' "$root" > "$OWNER_ROOT_FILE"
  {
    printf 'repo_root=%s\n' "$root"
    printf 'session=%s\n' "$SESSION"
    printf 'bus_dir=%s\n' "$BUS_DIR"
    printf 'lane=%s\n' "$IDENTITY_LANE"
  } > "$(owner_registry_file "$pid")"
}

prune_invalid_owner_registry() {
  local entry="" pid=""
  [ -d "$OWNER_REGISTRY_DIR" ] || return 0
  for entry in "$OWNER_REGISTRY_DIR"/*.pid; do
    [ -e "$entry" ] || continue
    pid="$(basename "$entry" .pid)"
    if ! owner_process_has_monitor_command "$pid"; then
      rm -f "$entry"
    fi
  done
  rmdir "$OWNER_REGISTRY_DIR" 2>/dev/null || true
}

prune_stale_owner_state() {
  local pid=""
  pid="$(current_owner_pid 2>/dev/null || true)"
  if [ -n "$pid" ] && ! owner_process_verified "$pid" && ! owner_process_has_monitor_command "$pid"; then
    clear_owner_pid_record "$pid"
  fi
  prune_invalid_owner_registry
}

tracked_owner_pids() {
  local pid="" entry="" entry_pid=""
  pid="$(current_owner_pid 2>/dev/null || true)"
  [ -n "$pid" ] && printf '%s\n' "$pid"
  if [ -d "$OWNER_REGISTRY_DIR" ]; then
    for entry in "$OWNER_REGISTRY_DIR"/*.pid; do
      [ -e "$entry" ] || continue
      entry_pid="$(basename "$entry" .pid)"
      [ -n "$entry_pid" ] && printf '%s\n' "$entry_pid"
    done
  fi
}

acquire_owner_lock() {
  ensure_state_dir
  local attempts=0 holder_pid=""
  while ! mkdir "$OWNER_LOCK_DIR" 2>/dev/null; do
    holder_pid="$(current_owner_lock_pid 2>/dev/null || true)"
    if [ -n "$holder_pid" ] && ! kill -0 "$holder_pid" 2>/dev/null; then
      rm -rf "$OWNER_LOCK_DIR"
      continue
    fi
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 200 ]; then
      if [ -z "$holder_pid" ]; then
        rm -rf "$OWNER_LOCK_DIR"
        attempts=0
        continue
      fi
      echo "ERROR: timed out acquiring pipeline monitor owner lock" >&2
      return 1
    fi
    sleep 0.05
  done
  printf '%s\n' "$$" > "$OWNER_LOCK_PID_FILE"
}

release_owner_lock() {
  local holder_pid=""
  holder_pid="$(current_owner_lock_pid 2>/dev/null || true)"
  if [ -z "$holder_pid" ] || [ "$holder_pid" = "$$" ]; then
    rm -rf "$OWNER_LOCK_DIR"
  fi
}

tmux_session_health_detail() {
  local expected_root="$1"
  local panes="" count=0 title="" pane_path="" expected_root_real="" pane_path_real=""
  local seen_1=0 seen_2=0 seen_3=0 seen_4=0

  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "session missing"
    return 1
  fi

  panes="$(tmux list-panes -t "$SESSION" -F '#{pane_title}	#{pane_current_path}' 2>/dev/null || true)"
  [ -n "$panes" ] || {
    echo "tmux list-panes returned no pane state"
    return 1
  }
  [ -d "$expected_root" ] || {
    echo "expected repo root missing: $expected_root"
    return 1
  }
  expected_root_real="$(normalize_path "$expected_root")"

  while IFS=$'\t' read -r title pane_path || [ -n "$title$pane_path" ]; do
    [ -n "$title" ] && [ -n "$pane_path" ] || {
      echo "tmux list-panes returned an unparseable pane entry"
      return 1
    }
    count=$((count + 1))
    case "$title" in
      "$EXPECTED_PANE_1") seen_1=1 ;;
      "$EXPECTED_PANE_2") seen_2=1 ;;
      "$EXPECTED_PANE_3") seen_3=1 ;;
      "$EXPECTED_PANE_4") seen_4=1 ;;
      *)
        echo "unexpected pane title: $title"
        return 1
        ;;
    esac
    if [ ! -d "$pane_path" ]; then
      echo "pane rooted at missing path: $title -> $pane_path"
      return 1
    fi
    pane_path_real="$(normalize_path "$pane_path")"
    if [ "$pane_path_real" != "$expected_root_real" ]; then
      echo "pane rooted at wrong repo: $title -> $pane_path"
      return 1
    fi
  done <<< "$panes"

  if [ "$count" -ne 4 ]; then
    echo "unexpected pane count: $count"
    return 1
  fi
  if [ "$seen_1" -ne 1 ] || [ "$seen_2" -ne 1 ] || [ "$seen_3" -ne 1 ] || [ "$seen_4" -ne 1 ]; then
    echo "missing monitor panes"
    return 1
  fi

  echo "session healthy at $expected_root_real"
  return 0
}

rebuild_tmux_session() {
  local repo_root="$1"

  tmux kill-session -t "$SESSION" 2>/dev/null || true

  # Write the log watcher script
  local watcher="/tmp/rcx_log_watcher.sh"
  write_log_watcher > "$watcher"
  chmod +x "$watcher"

  local OBS_DIR="$repo_root/mu/tools/observability"
  local repo_q="" obs_q="" watcher_q="" status_q="" root_helper_q="" bus_q="" lane_q=""
  printf -v repo_q '%q' "$repo_root"
  printf -v obs_q '%q' "$OBS_DIR"
  printf -v watcher_q '%q' "$watcher"
  printf -v status_q '%q' "$OBS_DIR/pipeline_status.sh"
  printf -v root_helper_q '%q' "$OBS_DIR/_resolve_live_root.sh"
  printf -v bus_q '%q' "$BUS_DIR"
  printf -v lane_q '%q' "$IDENTITY_LANE"

  local pane1_cmd=""
  local pane2_cmd=""
  local pane3_cmd=""
  local pane4_cmd=""
  # Do not pin panes to the launcher worktree. Let each pane re-resolve the
  # freshest active pipeline worktree on every refresh so tmux stays honest
  # when the real run lives in a different linked worktree.
  pane1_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && BUS_DIR=$bus_q RCX_AGENT_BUS_DIR=$bus_q RCX_PIPELINE_MONITOR_LANE=$lane_q RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $watcher_q"
  pane2_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && BUS_DIR=$bus_q RCX_AGENT_BUS_DIR=$bus_q RCX_PIPELINE_MONITOR_LANE=$lane_q RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_findings.sh"
  pane3_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && BUS_DIR=$bus_q RCX_AGENT_BUS_DIR=$bus_q RCX_PIPELINE_MONITOR_LANE=$lane_q RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_processes.sh"
  pane4_cmd="cd $repo_q && unset RCX_OBS_REPO_ROOT && BUS_DIR=$bus_q RCX_AGENT_BUS_DIR=$bus_q RCX_PIPELINE_MONITOR_LANE=$lane_q RCX_OBS_STATUS_SCRIPT=$status_q RCX_OBS_ROOT_HELPER=$root_helper_q bash $obs_q/_pane_timeline.sh"

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
}

ensure_tmux_session() {
  local repo_root="$1"
  if tmux_session_health_detail "$repo_root" >/dev/null 2>&1; then
    return 0
  fi
  rebuild_tmux_session "$repo_root"
}

stop_wrong_root_owner_processes() {
  local owner_pids="" pid="" live_remaining=0 expected_root=""
  expected_root="$(owner_expected_root)"
  owner_pids="$(tracked_owner_pids | awk 'NF && !seen[$0]++ { print $0 }' 2>/dev/null || true)"
  for pid in $owner_pids; do
    if owner_process_has_monitor_command "$pid" && ! owner_process_matches_root "$pid" "$expected_root"; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 20); do
    live_remaining=0
    for pid in $owner_pids; do
      if owner_process_has_monitor_command "$pid" && ! owner_process_matches_root "$pid" "$expected_root"; then
        live_remaining=1
        break
      fi
    done
    if [ "$live_remaining" -eq 0 ]; then
      break
    fi
    sleep 0.1
  done
  for pid in $owner_pids; do
    if owner_process_has_monitor_command "$pid" && ! owner_process_matches_root "$pid" "$expected_root"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    if ! owner_process_has_monitor_command "$pid"; then
      clear_owner_pid_record "$pid"
    fi
  done
}

ensure_owner_running() {
  local owner_pid="" owner_args=()
  acquire_owner_lock || return 1
  prune_stale_owner_state
  stop_wrong_root_owner_processes
  prune_stale_owner_state
  if owner_is_live; then
    release_owner_lock
    return 0
  fi

  if [ "$BUS_DIR" != ".agent_bus" ]; then
    owner_args+=(--bus-dir "$BUS_DIR")
  fi
  if [ -n "$REQUESTED_LANE" ]; then
    owner_args+=(--lane "$REQUESTED_LANE")
  fi
  if [ "${#owner_args[@]}" -gt 0 ]; then
    RCX_PIPELINE_MONITOR_STATE_DIR="$STATE_DIR" \
    RCX_PIPELINE_MONITOR_HEALTH_INTERVAL="$OWNER_INTERVAL_SECONDS" \
      nohup bash "$0" "${owner_args[@]}" __owner-loop >/dev/null 2>&1 &
  else
    RCX_PIPELINE_MONITOR_STATE_DIR="$STATE_DIR" \
    RCX_PIPELINE_MONITOR_HEALTH_INTERVAL="$OWNER_INTERVAL_SECONDS" \
      nohup bash "$0" __owner-loop >/dev/null 2>&1 &
  fi
  owner_pid="$!"
  record_owner_pid "$owner_pid"
  for _ in $(seq 1 20); do
    if owner_process_verified "$owner_pid"; then
      release_owner_lock
      return 0
    fi
    sleep 0.05
  done
  clear_owner_pid_record "$owner_pid"
  release_owner_lock
  echo "ERROR: failed to launch pipeline monitor owner" >&2
  return 1
}

stop_owner_process() {
  local owner_pids="" pid="" live_remaining=0
  prune_stale_owner_state
  owner_pids="$(tracked_owner_pids | awk 'NF && !seen[$0]++ { print $0 }' 2>/dev/null || true)"
  for pid in $owner_pids; do
    if owner_process_has_monitor_command "$pid"; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 20); do
    live_remaining=0
    for pid in $owner_pids; do
      if owner_process_has_monitor_command "$pid"; then
        live_remaining=1
        break
      fi
    done
    if [ "$live_remaining" -eq 0 ]; then
      break
    fi
    sleep 0.1
  done
  for pid in $owner_pids; do
    if owner_process_has_monitor_command "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  rm -f "$OWNER_PID_FILE" "$OWNER_ROOT_FILE"
  rm -f "$OWNER_REGISTRY_DIR"/*.pid 2>/dev/null || true
  rmdir "$OWNER_REGISTRY_DIR" 2>/dev/null || true
  rm -rf "$OWNER_LOCK_DIR"
}

ensure_tmux_session_under_owner_lock() {
  local rc=0
  acquire_owner_lock || return 1
  ensure_tmux_session "$REPO_ROOT" || rc=$?
  release_owner_lock
  return "$rc"
}

cmd_owner_tick() {
  ensure_tmux_session_under_owner_lock
}

cmd_owner_loop() {
  local sleep_pid="" owner_pid=""
  ensure_state_dir
  owner_pid="$(current_owner_pid 2>/dev/null || true)"
  if [ -n "$owner_pid" ] && [ "$owner_pid" != "$$" ] && owner_process_verified "$owner_pid"; then
    exit 0
  fi
  record_owner_pid "$$"
  trap '
    if [ -n "${sleep_pid:-}" ] && kill -0 "$sleep_pid" 2>/dev/null; then
      kill "$sleep_pid" 2>/dev/null || true
    fi
    clear_owner_pid_record "$$"
    if [ -f "$OWNER_PID_FILE" ] && [ "$(cat "$OWNER_PID_FILE" 2>/dev/null || true)" = "$$" ]; then
      rm -f "$OWNER_PID_FILE"
    fi
  ' EXIT INT TERM

  while true; do
    cmd_owner_tick >/dev/null 2>&1 || true
    sleep "$OWNER_INTERVAL_SECONDS" &
    sleep_pid="$!"
    wait "$sleep_pid" 2>/dev/null || true
    sleep_pid=""
  done
}

cmd_start() {
  local detach=false
  while [ $# -gt 0 ]; do
    case "$1" in
      --detach) detach=true; shift ;;
      *) echo "Unknown option: $1"; usage 1 ;;
    esac
  done

  ensure_owner_running
  ensure_tmux_session_under_owner_lock

  local autoping_launcher="$REPO_ROOT/tools/session/ensure_codex_autoping.sh"
  if [ -n "${CODEX_THREAD_ID:-}" ] && [ -x "$autoping_launcher" ]; then
    if ! "$autoping_launcher" \
      --repo "$REPO_ROOT" \
      --thread-id "$CODEX_THREAD_ID" \
      --bus-dir "$BUS_DIR" \
      --tmux-session "$SESSION" \
      --tmux-pane "$SESSION:1.3" \
      --force-restart >/dev/null 2>&1; then
      echo "WARN: failed to restart Codex autoping after tmux session reset" >&2
    fi
  fi

  echo "Pipeline monitor started (session: $SESSION)"
  echo "Lane identity: lane=$IDENTITY_LANE bus=$BUS_PATH dashboard=http://127.0.0.1:$DASHBOARD_PORT"
  if [ "$detach" = false ]; then
    echo "Attaching... (detach with Ctrl-b d)"
    tmux attach-session -t "$SESSION"
  else
    echo "Detached. Attach with: tmux attach-session -t $SESSION"
  fi
}

cmd_stop() {
  local had_session=false
  local had_owner=false

  prune_stale_owner_state
  if tracked_owner_pids | grep -q .; then
    had_owner=true
  fi
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    had_session=true
  fi

  stop_owner_process
  tmux kill-session -t "$SESSION" 2>/dev/null || true

  if [ "$had_session" = true ] || [ "$had_owner" = true ]; then
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
  exec env -u RCX_OBS_REPO_ROOT RCX_AGENT_BUS_DIR="$BUS_DIR" "$STATUS_SCRIPT" --bus-dir "$BUS_DIR"
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
  RCX_AGENT_BUS_DIR="$BUS_DIR" "$@" 2>&1 | tee "$LIVE_LOG"
}

# ── clear-lock: Remove stale bridge locks ──
cmd_clear_lock() {
  local found=false
  for lock in "$BUS_PATH/meta/meta_bridge.lock" "$BUS_PATH/bridge.lock"; do
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
    pr=$(ls -t "$BUS_PATH/executors/commit_executor_"*.json 2>/dev/null | head -1 | xargs jq -r '.pr_number // empty' 2>/dev/null)
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
  __owner-loop) shift; cmd_owner_loop "$@" ;;
  -h|--help)   usage 0 ;;
  "")          usage 1 ;;
  *)           echo "Unknown command: $1"; usage 1 ;;
esac
