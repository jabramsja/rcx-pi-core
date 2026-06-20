#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO="/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX"
TMUX_SESSION="rcx-pipeline"
TMUX_PANE=""
BUS_DIR="${RCX_AGENT_BUS_DIR:-.agent_bus}"
REPO=""
THREAD_ID="${CODEX_THREAD_ID:-}"
INTERVAL="20"
INITIAL_DELAY="30"
PING_TIMEOUT="120"
FORCE_RESTART=0

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/ensure_codex_autoping.sh [options]

Options:
  --repo <path>            Override the WorkingRCX repo path
  --thread-id <id>         Override CODEX_THREAD_ID
  --interval <seconds>     Poll interval (default: 20)
  --initial-delay <sec>    Initial delay before first tick (default: 30)
  --ping-timeout <sec>     Kill a stale ping subprocess after this many seconds (default: 120)
  --bus-dir <dir>          Active repo-root agent bus (.agent_bus or .agent_bus-<id>)
  --tmux-session <name>    Target monitor tmux session (default: rcx-pipeline)
  --tmux-pane <target>     Target monitor pane for tail reads (default: <session>:1.3)
  --force-restart          Restart an existing watcher for this thread
  -h, --help               Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --repo)
            [ $# -ge 2 ] || { echo "ERROR: --repo requires a path" >&2; exit 2; }
            REPO="$2"
            shift 2
            ;;
        --thread-id)
            [ $# -ge 2 ] || { echo "ERROR: --thread-id requires a value" >&2; exit 2; }
            THREAD_ID="$2"
            shift 2
            ;;
        --interval)
            [ $# -ge 2 ] || { echo "ERROR: --interval requires a value" >&2; exit 2; }
            INTERVAL="$2"
            shift 2
            ;;
        --initial-delay)
            [ $# -ge 2 ] || { echo "ERROR: --initial-delay requires a value" >&2; exit 2; }
            INITIAL_DELAY="$2"
            shift 2
            ;;
        --ping-timeout)
            [ $# -ge 2 ] || { echo "ERROR: --ping-timeout requires a value" >&2; exit 2; }
            PING_TIMEOUT="$2"
            shift 2
            ;;
        --bus-dir)
            [ $# -ge 2 ] || { echo "ERROR: --bus-dir requires a value" >&2; exit 2; }
            BUS_DIR="$2"
            shift 2
            ;;
        --tmux-session)
            [ $# -ge 2 ] || { echo "ERROR: --tmux-session requires a value" >&2; exit 2; }
            TMUX_SESSION="$2"
            shift 2
            ;;
        --tmux-pane)
            [ $# -ge 2 ] || { echo "ERROR: --tmux-pane requires a value" >&2; exit 2; }
            TMUX_PANE="$2"
            shift 2
            ;;
        --force-restart)
            FORCE_RESTART=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
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
if [[ ! "$TMUX_SESSION" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]]; then
    echo "ERROR: invalid --tmux-session: $TMUX_SESSION" >&2
    exit 2
fi
if [ -z "$TMUX_PANE" ]; then
    TMUX_PANE="$TMUX_SESSION:1.3"
fi

if [ -z "$REPO" ]; then
    if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
        REPO="$git_root"
    else
        REPO="$DEFAULT_REPO"
    fi
fi

if [ "${RCX_PIPELINE_SESSION:-0}" = "1" ]; then
    echo "Codex autoping: skipped (RCX_PIPELINE_SESSION=1)"
    exit 0
fi

if [ -z "$THREAD_ID" ]; then
    echo "Codex autoping: skipped (CODEX_THREAD_ID unset)"
    exit 0
fi

resolve_session_script() {
    local name="$1"
    local candidate=""
    for candidate in "$REPO/mu/tools/session/$name" "$REPO/tools/session/$name"; do
        if [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    printf '%s\n' "$REPO/mu/tools/session/$name"
}

WATCH_SCRIPT="$(resolve_session_script codex_autoping_watch.py)"
if [ ! -f "$WATCH_SCRIPT" ]; then
    echo "Codex autoping: missing watcher script at $WATCH_SCRIPT"
    exit 1
fi
WINDOW_SCRIPT="$(resolve_session_script codex_autoping_window.sh)"
if [ ! -f "$WINDOW_SCRIPT" ]; then
    echo "Codex autoping: missing tmux window script at $WINDOW_SCRIPT"
    exit 1
fi

THREAD_SLUG="$(printf '%s' "$THREAD_ID" | tr -c 'A-Za-z0-9_.-' '_')"
STATE_DIR="${RCX_CODEX_HOME:-$HOME/.codex}/state"
LOG_DIR="${RCX_CODEX_HOME:-$HOME/.codex}/log/autoping"
STATE_PATH="$STATE_DIR/rcx_autoping_${THREAD_SLUG}.json"
SUMMARY_PATH="$STATE_DIR/rcx_autoping_${THREAD_SLUG}_summary.txt"
RUNNER_LOG="$LOG_DIR/rcx_autoping_${THREAD_SLUG}.runner.log"
mkdir -p "$STATE_DIR" "$LOG_DIR"

process_is_recorded_autoping_watcher() {
    local pid="$1"
    python3 - <<'PY' "$pid" "$WATCH_SCRIPT" "$THREAD_ID"
import os
import shlex
import subprocess
import sys
from pathlib import Path

pid_text, watch_script, thread_id = sys.argv[1:4]
try:
    pid = int(pid_text)
except (TypeError, ValueError):
    raise SystemExit(1)
if pid <= 1:
    raise SystemExit(1)
command = ""
proc_cmdline = Path(f"/proc/{pid}/cmdline")
try:
    if proc_cmdline.exists():
        raw = proc_cmdline.read_bytes()
        command = " ".join(
            part.decode(errors="replace")
            for part in raw.split(b"\0")
            if part
        ).strip()
except OSError:
    command = ""
if not command:
    try:
        proc = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        raise SystemExit(1)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SystemExit(1)
    command = proc.stdout.strip()
try:
    tokens = shlex.split(command)
except ValueError:
    tokens = command.split()
expected_path = str(Path(watch_script))
expected_name = os.path.basename(expected_path)
has_watch_script = any(
    token == expected_path
    or os.path.basename(token) == expected_name
    or token.endswith("/" + expected_name)
    for token in tokens
)
has_thread_id = False
for index, token in enumerate(tokens):
    if token == "--thread-id" and index + 1 < len(tokens) and tokens[index + 1] == thread_id:
        has_thread_id = True
        break
if not has_thread_id and thread_id in tokens:
    has_thread_id = True
raise SystemExit(0 if has_watch_script and has_thread_id else 1)
PY
}

stop_recorded_autoping_watcher() {
    local pid="$1"
    local reason="$2"
    if process_is_recorded_autoping_watcher "$pid"; then
        echo "Codex autoping: stopping recorded watcher pid=$pid ($reason)"
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
    else
        echo "Codex autoping: recorded pid=$pid is live but not this autoping watcher; preserving process and reseeding"
    fi
}

existing_pid=""
if [ -f "$STATE_PATH" ]; then
    existing_pid="$(python3 - <<'PY' "$STATE_PATH"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text())
except Exception:
    print("")
else:
    pid = payload.get("watcher_pid") or payload.get("active_pid")
    print("" if pid in (None, "") else str(pid))
PY
)"
fi

tmux_session_active=0
tmux_autoping_window_present=0
autoping_window_ids() {
    tmux list-windows -t "$TMUX_SESSION" -F '#{window_id} #{window_name}' 2>/dev/null \
        | awk '$2 == "AUTO-PING" { print $1 }'
}
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux_session_active=1
    if autoping_window_ids | grep -q .; then
        tmux_autoping_window_present=1
    fi
fi

if [ -n "$existing_pid" ] && ps -p "$existing_pid" > /dev/null 2>&1; then
    if ! process_is_recorded_autoping_watcher "$existing_pid"; then
        echo "Codex autoping: recorded pid=$existing_pid is live but not this autoping watcher; preserving process and reseeding"
    elif [ "$FORCE_RESTART" -ne 1 ]; then
        if [ "$tmux_session_active" -eq 1 ] && [ "$tmux_autoping_window_present" -ne 1 ]; then
            echo "Codex autoping: active pid=$existing_pid but AUTO-PING window missing; restarting tmux-managed watcher"
            stop_recorded_autoping_watcher "$existing_pid" "AUTO-PING window missing"
        else
            echo "Codex autoping: active pid=$existing_pid thread=$THREAD_ID"
            echo "Autoping state: $STATE_PATH"
            echo "Autoping summary: $SUMMARY_PATH"
            exit 0
        fi
    else
        stop_recorded_autoping_watcher "$existing_pid" "force restart"
    fi
fi

cleanup_orphaned_autoping_execs() {
    python3 - <<'PY' "$THREAD_ID" "$THREAD_SLUG"
import os
import signal
import subprocess
import sys

thread_id = sys.argv[1]
thread_slug = sys.argv[2]
try:
    proc = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,command="],
        text=True,
        capture_output=True,
        check=False,
    )
except OSError:
    raise SystemExit(0)
if proc.returncode not in (0, 1) and not proc.stdout:
    raise SystemExit(0)
if not proc.stdout:
    raise SystemExit(0)
for raw_line in proc.stdout.splitlines():
    line = raw_line.strip()
    if not line:
        continue
    parts = line.split(None, 2)
    if len(parts) != 3:
        continue
    pid_text, ppid_text, command = parts
    if thread_id not in command and thread_slug not in command:
        continue
    if "codex exec" not in command:
        continue
    if "Autonomous WorkingRCX pipeline watchdog tick." not in command:
        continue
    try:
        pid = int(pid_text)
        ppid = int(ppid_text)
    except ValueError:
        continue
    if ppid != 1:
        continue
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        print(f"Codex autoping: cleaned orphaned exec process group pid={pid}")
    except PermissionError:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Codex autoping: cleaned orphaned exec pid={pid}")
        except ProcessLookupError:
            continue
    except ProcessLookupError:
        continue
PY
}

cleanup_orphaned_autoping_execs

CMD=(python3 "$WATCH_SCRIPT" --repo-root "$REPO" --thread-id "$THREAD_ID" --interval "$INTERVAL" --initial-delay "$INITIAL_DELAY" --ping-timeout "$PING_TIMEOUT" --bus-dir "$BUS_DIR" --tmux-session "$TMUX_SESSION" --tmux-pane "$TMUX_PANE")
WINDOW_CMD=("$WINDOW_SCRIPT" --repo "$REPO" --thread-id "$THREAD_ID" --interval "$INTERVAL" --initial-delay "$INITIAL_DELAY" --ping-timeout "$PING_TIMEOUT" --bus-dir "$BUS_DIR" --tmux-session "$TMUX_SESSION" --tmux-pane "$TMUX_PANE")
WINDOW_CMD_STRING="$(printf '%q ' "${WINDOW_CMD[@]}")"
WINDOW_CMD_STRING="${WINDOW_CMD_STRING% }"

if [ "$tmux_session_active" -eq 1 ]; then
    if [ "$tmux_autoping_window_present" -eq 1 ]; then
        while IFS= read -r window_id; do
            [ -n "$window_id" ] || continue
            tmux kill-window -t "$window_id" 2>/dev/null || true
        done < <(autoping_window_ids)
    fi
    tmux new-window -d -t "$TMUX_SESSION" -n "AUTO-PING" "$WINDOW_CMD_STRING"
    echo "Codex autoping: ACTIVE in tmux-managed AUTO-PING window for thread $THREAD_ID"
else
    nohup "${CMD[@]}" >"$RUNNER_LOG" 2>&1 </dev/null &
    WATCHER_PID="$!"
    echo "Codex autoping: ACTIVE in background pid=$WATCHER_PID for thread $THREAD_ID"
fi

echo "Autoping state: $STATE_PATH"
echo "Autoping summary: $SUMMARY_PATH"
echo "Autoping watcher: $WATCH_SCRIPT"
