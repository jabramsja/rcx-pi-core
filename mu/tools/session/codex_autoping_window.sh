#!/usr/bin/env bash
set -euo pipefail

REPO=""
THREAD_ID=""
INTERVAL="20"
INITIAL_DELAY="30"
PING_TIMEOUT="120"
BUS_DIR="${RCX_AGENT_BUS_DIR:-.agent_bus}"
TMUX_SESSION="rcx-pipeline"
TMUX_PANE=""

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/codex_autoping_window.sh --repo <path> --thread-id <id> [--interval N] [--initial-delay N] [--ping-timeout N] [--bus-dir DIR] [--tmux-session NAME] [--tmux-pane TARGET]
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

[ -n "$REPO" ] || { echo "ERROR: --repo is required" >&2; exit 2; }
[ -n "$THREAD_ID" ] || { echo "ERROR: --thread-id is required" >&2; exit 2; }
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

THREAD_SLUG="$(printf '%s' "$THREAD_ID" | tr -c 'A-Za-z0-9_.-' '_')"
STATE_DIR="${RCX_CODEX_HOME:-$HOME/.codex}/state"
LOG_DIR="${RCX_CODEX_HOME:-$HOME/.codex}/log/autoping"
STATE_PATH="$STATE_DIR/rcx_autoping_${THREAD_SLUG}.json"
SUMMARY_PATH="$STATE_DIR/rcx_autoping_${THREAD_SLUG}_summary.txt"
RUNNER_LOG="$LOG_DIR/rcx_autoping_${THREAD_SLUG}.runner.log"
WATCH_SCRIPT="$REPO/tools/session/codex_autoping_watch.py"
RENDER_SCRIPT="$REPO/tools/session/render_codex_autoping_status.py"

mkdir -p "$STATE_DIR" "$LOG_DIR"
touch "$SUMMARY_PATH"
: >"$RUNNER_LOG"

WATCHER_PID=""

start_watcher() {
    printf '[autoping-window] starting watcher\n' >>"$RUNNER_LOG"
    python3 "$WATCH_SCRIPT" \
        --repo-root "$REPO" \
        --thread-id "$THREAD_ID" \
        --interval "$INTERVAL" \
        --initial-delay "$INITIAL_DELAY" \
        --ping-timeout "$PING_TIMEOUT" \
        --bus-dir "$BUS_DIR" \
        --tmux-session "$TMUX_SESSION" \
        --tmux-pane "$TMUX_PANE" \
        >>"$RUNNER_LOG" 2>&1 &
    WATCHER_PID="$!"
    printf '[autoping-window] watcher_pid=%s\n' "$WATCHER_PID" >>"$RUNNER_LOG"
}

watcher_is_running() {
    [ -n "${WATCHER_PID:-}" ] && kill -0 "$WATCHER_PID" >/dev/null 2>&1
}

cleanup_active_ping_from_state() {
    python3 - "$STATE_PATH" "$RUNNER_LOG" "${WATCHER_PID:-}" <<'PY'
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
runner_log = Path(sys.argv[2])
expected_watcher_pid = None
if len(sys.argv) > 3 and sys.argv[3]:
    try:
        expected_watcher_pid = int(sys.argv[3])
    except ValueError:
        expected_watcher_pid = None


def log(message):
    with runner_log.open("a", encoding="utf-8") as sink:
        sink.write(f"{message}\n")


def active_pid_from_state():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, json.JSONDecodeError) as exc:
        log(f"[autoping-window] active ping cleanup skipped invalid_state={exc}")
        return {}, None

    try:
        pid = int(state.get("active_pid") or 0)
    except (TypeError, ValueError):
        return state, None
    try:
        recorded_watcher_pid = int(state.get("watcher_pid") or 0)
    except (TypeError, ValueError):
        recorded_watcher_pid = 0
    if expected_watcher_pid is not None and recorded_watcher_pid != expected_watcher_pid:
        log(
            "[autoping-window] active ping cleanup skipped "
            f"state_watcher_pid={recorded_watcher_pid} expected_watcher_pid={expected_watcher_pid}"
        )
        return state, None
    if pid <= 1 or pid == expected_watcher_pid:
        return state, None
    return state, pid


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def active_target_alive(pid):
    return pid_alive(pid) or process_group_alive(pid)


def signal_active(pid, sig):
    sent = False
    try:
        os.killpg(pid, sig)
        sent = True
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        log(f"[autoping-window] active ping cleanup denied pgid={pid} signal={sig.name}: {exc}")
        raise
    except OSError:
        pass

    if pid_alive(pid):
        try:
            os.kill(pid, sig)
            sent = True
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            log(f"[autoping-window] active ping cleanup denied pid={pid} signal={sig.name}: {exc}")
            raise
    return sent


def wait_inactive(pid, timeout_s):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not active_target_alive(pid):
            return True
        time.sleep(0.05)
    return not active_target_alive(pid)


def mark_cleanup_degraded(state, pid, reason):
    now = datetime.now(timezone.utc).isoformat()
    state.update(
        {
            "updated_at": now,
            "status": "watcher_restart_degraded_active_ping_cleanup_failed",
            "active_pid": pid,
            "last_active_cleanup_pid": pid,
            "last_active_cleanup_at": now,
            "last_active_cleanup_error": reason,
        }
    )
    try:
        state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        log(f"[autoping-window] failed to persist degraded cleanup state pid={pid}: {exc}")


state, pid = active_pid_from_state()
if pid is None:
    raise SystemExit(0)
if not active_target_alive(pid):
    raise SystemExit(0)

try:
    sent = signal_active(pid, signal.SIGTERM)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_sigterm: {exc}")
    raise SystemExit(1)

if sent and wait_inactive(pid, 2.0):
    state.update(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "watcher_restarting_active_ping_terminated",
            "active_pid": None,
            "active_mode": None,
            "last_active_cleanup_pid": pid,
            "last_active_cleanup_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    log(f"[autoping-window] terminated stale active ping pid={pid}")
    raise SystemExit(0)

try:
    signal_active(pid, signal.SIGKILL)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_sigkill: {exc}")
    raise SystemExit(1)

if wait_inactive(pid, 1.0):
    state.update(
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "watcher_restarting_active_ping_killed",
            "active_pid": None,
            "active_mode": None,
            "last_active_cleanup_pid": pid,
            "last_active_cleanup_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    log(f"[autoping-window] killed stale active ping pid={pid}")
    raise SystemExit(0)

mark_cleanup_degraded(state, pid, "stale active ping still alive after SIGTERM/SIGKILL")
log(f"[autoping-window] stale active ping still alive pid={pid}; restarting watcher degraded")
raise SystemExit(1)
PY
}

ensure_watcher() {
    if watcher_is_running; then
        return 0
    fi
    if [ -n "${WATCHER_PID:-}" ]; then
        wait "$WATCHER_PID" >/dev/null 2>&1 || true
        printf '[autoping-window] watcher exited pid=%s; restarting\n' "$WATCHER_PID" >>"$RUNNER_LOG"
    fi
    if ! cleanup_active_ping_from_state; then
        printf '[autoping-window] active ping cleanup failed; restarting watcher degraded\n' >>"$RUNNER_LOG"
    fi
    start_watcher
    printf '[autoping-restart] watcher_pid=%s\n' "$WATCHER_PID"
}

start_watcher

cleanup() {
    if watcher_is_running; then
        kill "$WATCHER_PID" >/dev/null 2>&1 || true
    fi
    if [ -n "${WATCHER_PID:-}" ]; then
        wait "$WATCHER_PID" >/dev/null 2>&1 || true
    fi
    cleanup_active_ping_from_state || true
}
handle_signal() {
    trap - EXIT
    cleanup
    exit 0
}
trap cleanup EXIT
trap handle_signal INT TERM

printf 'Watching %s\n' "$RUNNER_LOG"
printf 'State: %s\n' "$STATE_PATH"
printf 'Summary: %s\n\n' "$SUMMARY_PATH"
printf '[autoping-launch] watcher_pid=%s\n' "$WATCHER_PID"

while true; do
    ensure_watcher
    printf '\033[H\033[2J'
    python3 "$RENDER_SCRIPT" --thread-id "$THREAD_ID"
    sleep 2
done
