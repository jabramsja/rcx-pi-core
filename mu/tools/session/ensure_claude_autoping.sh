#!/usr/bin/env bash
set -euo pipefail

# ensure_claude_autoping.sh -- ACTIVATION entry point for the dedicated Claude
# monitor autoping watcher (GAP-3). Mirror of ensure_codex_autoping.sh, SIMPLIFIED
# with NO tmux integration: it just (re)starts a background claude_autoping_watch.py
# that keeps the dedicated monitor session warm.
#
# Activation story for route=both:
#   founder runs  RCX_CLAUDE_MONITOR=1 claude
#     -> .claude/hooks/session-start.sh writes
#        <repo>/<bus>/observability/claude_monitor_session_id
#     -> ensure_claude_autoping.sh starts the watcher that keeps it warm.
# The route=both flip is NOT gated on the monitor being up: Wave A's monitor-absent
# skip is RETRYABLE (a page emitted before the monitor is up is re-queued, never
# dropped). Monitor health is visible via the state file's `status` field
# (healthy live status vs `paused`).

DEFAULT_REPO="/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX"
BUS_DIR="${RCX_AGENT_BUS_DIR:-.agent_bus}"
REPO=""
SESSION_ID=""
INTERVAL="20"
INITIAL_DELAY="30"
PING_TIMEOUT="120"
FORCE_RESTART=0

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/ensure_claude_autoping.sh [options]

Options:
  --repo <path>            Override the WorkingRCX repo path
  --session-id <id>        Override the dedicated claude_monitor_session_id
  --interval <seconds>     Poll interval (default: 20)
  --initial-delay <sec>    Initial delay before first tick (default: 30)
  --ping-timeout <sec>     Kill a stale keepalive subprocess after this many seconds (default: 120)
  --bus-dir <dir>          Active repo-root agent bus (.agent_bus or .agent_bus-<id>)
  --force-restart          Restart an existing watcher for this session
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
        --session-id)
            [ $# -ge 2 ] || { echo "ERROR: --session-id requires a value" >&2; exit 2; }
            SESSION_ID="$2"
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

if [ -z "$REPO" ]; then
    if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
        REPO="$git_root"
    else
        REPO="$DEFAULT_REPO"
    fi
fi

# Env guard: never start a keepalive from inside a pipeline-owned session.
if [ "${RCX_PIPELINE_SESSION:-0}" = "1" ]; then
    echo "Claude autoping: skipped (RCX_PIPELINE_SESSION=1)"
    exit 0
fi

OBS_DIR="$REPO/$BUS_DIR/observability"
MONITOR_FILE="$OBS_DIR/claude_monitor_session_id"

# Resolve the dedicated monitor session id (explicit override wins, else read the
# file with the SAME fail-closed discipline as the pager / watcher: strip, reject
# empty / internal-whitespace / non-UTF-8). NEVER read orchestrator_session_id.
if [ -z "$SESSION_ID" ] && [ -f "$MONITOR_FILE" ]; then
    SESSION_ID="$(python3 - "$MONITOR_FILE" <<'PY'
import sys
from pathlib import Path
try:
    raw = Path(sys.argv[1]).read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError):
    print("")
else:
    candidate = raw.strip()
    if not candidate or any(ch.isspace() for ch in candidate):
        print("")
    else:
        print(candidate)
PY
)"
fi

# Env guard (GAP-3): no dedicated monitor id available -> skip. The route=both
# flip stays safe because Wave A's monitor-absent skip is retryable, so a page is
# never dropped while the monitor is not yet up.
if [ -z "$SESSION_ID" ]; then
    echo "Claude autoping: skipped (no dedicated claude_monitor_session_id available)"
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

WATCH_SCRIPT="$(resolve_session_script claude_autoping_watch.py)"
if [ ! -f "$WATCH_SCRIPT" ]; then
    echo "Claude autoping: missing watcher script at $WATCH_SCRIPT"
    exit 1
fi

SESSION_SLUG="$(printf '%s' "$SESSION_ID" | tr -c 'A-Za-z0-9_.-' '_')"
STATE_PATH="$OBS_DIR/claude_autoping_${SESSION_SLUG}.json"
SUMMARY_PATH="$OBS_DIR/claude_autoping_${SESSION_SLUG}_summary.txt"
LOG_DIR="$OBS_DIR/claude_autoping_dispatch"
RUNNER_LOG="$LOG_DIR/claude_autoping_${SESSION_SLUG}.runner.log"
mkdir -p "$OBS_DIR" "$LOG_DIR"

process_is_recorded_autoping_watcher() {
    local pid="$1"
    python3 - "$pid" "$WATCH_SCRIPT" "$SESSION_ID" <<'PY'
import os
import shlex
import subprocess
import sys
from pathlib import Path

pid_text, watch_script, session_id = sys.argv[1:4]
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
has_session_id = False
for index, token in enumerate(tokens):
    if token == "--session-id" and index + 1 < len(tokens) and tokens[index + 1] == session_id:
        has_session_id = True
        break
if not has_session_id and session_id in tokens:
    has_session_id = True
raise SystemExit(0 if has_watch_script and has_session_id else 1)
PY
}

stop_recorded_autoping_watcher() {
    local pid="$1"
    local reason="$2"
    if process_is_recorded_autoping_watcher "$pid"; then
        echo "Claude autoping: stopping recorded watcher pid=$pid ($reason)"
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
    else
        echo "Claude autoping: recorded pid=$pid is live but not this autoping watcher; preserving process and reseeding"
    fi
}

existing_pid=""
if [ -f "$STATE_PATH" ]; then
    existing_pid="$(python3 - "$STATE_PATH" <<'PY'
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

if [ -n "$existing_pid" ] && ps -p "$existing_pid" > /dev/null 2>&1; then
    if ! process_is_recorded_autoping_watcher "$existing_pid"; then
        echo "Claude autoping: recorded pid=$existing_pid is live but not this autoping watcher; preserving process and reseeding"
    elif [ "$FORCE_RESTART" -ne 1 ]; then
        echo "Claude autoping: active pid=$existing_pid session=$SESSION_ID"
        echo "Autoping state: $STATE_PATH"
        echo "Autoping summary: $SUMMARY_PATH"
        exit 0
    else
        stop_recorded_autoping_watcher "$existing_pid" "force restart"
    fi
fi

# Sweep stale watcher processes for this session that were reparented to init
# (ppid==1) -- e.g. a watcher left behind by a SIGKILL'd / hard-crashed launcher.
# The watcher self-isolates into its own session/process group at startup
# (claude_autoping_watch._isolate_process_group via os.setsid), so group-killing it
# stays scoped to the watcher; the sweep ALSO re-checks group leadership before any
# killpg as defense-in-depth, never signalling an inherited (shared) process group.
cleanup_orphaned_autoping_watchers() {
    python3 - "$SESSION_ID" "$SESSION_SLUG" <<'PY'
import os
import signal
import subprocess
import sys

session_id = sys.argv[1]
session_slug = sys.argv[2]
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
    if "claude_autoping_watch.py" not in command:
        continue
    if session_id not in command and session_slug not in command:
        continue
    try:
        pid = int(pid_text)
        ppid = int(ppid_text)
    except ValueError:
        continue
    if ppid != 1:
        continue
    try:
        # Only group-kill a watcher that is its OWN process-group leader. The watcher
        # self-isolates via os.setsid() at startup (claude_autoping_watch.
        # _isolate_process_group), so an orphaned watcher is normally its own group
        # leader and killpg is scoped to it alone. If it is NOT a leader it shares an
        # inherited group; killpg would signal unrelated processes, so fall back to a
        # single-pid SIGTERM (the watcher reaps its own detached keepalive child on
        # SIGTERM via its signal handler).
        pgid = os.getpgid(pid)
        if pgid == pid:
            os.killpg(pgid, signal.SIGTERM)
            print(f"Claude autoping: cleaned orphaned watcher process group pid={pid}")
        else:
            os.kill(pid, signal.SIGTERM)
            print(f"Claude autoping: cleaned orphaned watcher pid={pid} (single-pid; not group leader)")
    except PermissionError:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Claude autoping: cleaned orphaned watcher pid={pid}")
        except ProcessLookupError:
            continue
    except ProcessLookupError:
        continue
PY
}

cleanup_orphaned_autoping_watchers

# Mirror of the codex launcher's cleanup_orphaned_autoping_execs. The watcher
# reaps its own detached `claude --resume` keepalive on a clean stop (SIGTERM),
# but a SIGKILL'd / hard-crashed watcher cannot, leaving the keepalive child
# orphaned (reparented to init). Sweep those orphans by the unique keepalive
# prompt marker + this session, scoped to ppid==1, and SIGTERM their process
# groups. The marker MUST match the first line of
# claude_autoping_watch._render_prompt.
cleanup_orphaned_autoping_keepalives() {
    python3 - "$SESSION_ID" "$SESSION_SLUG" <<'PY'
import os
import signal
import subprocess
import sys

session_id = sys.argv[1]
session_slug = sys.argv[2]
# Keep in sync with claude_autoping_watch._render_prompt's first line.
KEEPALIVE_MARKER = "WorkingRCX dedicated Claude monitor keepalive tick."
try:
    proc = subprocess.run(
        ["ps", "-ww", "-Ao", "pid=,ppid=,command="],
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
    if KEEPALIVE_MARKER not in command:
        continue
    if session_id not in command and session_slug not in command:
        continue
    if "--resume" not in command:
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
        print(f"Claude autoping: cleaned orphaned keepalive process group pid={pid}")
    except PermissionError:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Claude autoping: cleaned orphaned keepalive pid={pid}")
        except ProcessLookupError:
            continue
    except ProcessLookupError:
        continue
PY
}

cleanup_orphaned_autoping_keepalives

CMD=(python3 "$WATCH_SCRIPT" --repo-root "$REPO" --session-id "$SESSION_ID" --interval "$INTERVAL" --initial-delay "$INITIAL_DELAY" --ping-timeout "$PING_TIMEOUT" --bus-dir "$BUS_DIR")
nohup "${CMD[@]}" >"$RUNNER_LOG" 2>&1 </dev/null &
WATCHER_PID="$!"
echo "Claude autoping: ACTIVE in background pid=$WATCHER_PID for session $SESSION_ID"
echo "Autoping state: $STATE_PATH"
echo "Autoping summary: $SUMMARY_PATH"
echo "Autoping watcher: $WATCH_SCRIPT"
