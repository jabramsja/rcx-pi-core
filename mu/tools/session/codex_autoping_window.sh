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
RENDER_SCRIPT="$(resolve_session_script render_codex_autoping_status.py)"

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
    python3 - "$STATE_PATH" "$RUNNER_LOG" "${WATCHER_PID:-}" "$PING_TIMEOUT" "$INTERVAL" <<'PY'
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
try:
    ping_timeout_s = max(float(sys.argv[4]), 0.0)
except (IndexError, TypeError, ValueError):
    ping_timeout_s = 120.0
try:
    interval_s = max(float(sys.argv[5]), 0.0)
except (IndexError, TypeError, ValueError):
    interval_s = 20.0


class ActiveTargetVerificationError(RuntimeError):
    pass


def log(message):
    with runner_log.open("a", encoding="utf-8") as sink:
        sink.write(f"{message}\n")


def parse_positive_int(value):
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1 else None


def parse_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def cleanup_max_state_age_s():
    return max(60.0, ping_timeout_s + interval_s + 30.0)


def active_pid_from_state():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, json.JSONDecodeError) as exc:
        log(f"[autoping-window] active ping cleanup skipped invalid_state={exc}")
        return {}, None

    pid = parse_positive_int(state.get("active_pid"))
    if pid is None:
        return state, None
    recorded_watcher_pid = parse_positive_int(state.get("watcher_pid")) or 0
    if expected_watcher_pid is not None and recorded_watcher_pid != expected_watcher_pid:
        log(
            "[autoping-window] active ping cleanup skipped "
            f"state_watcher_pid={recorded_watcher_pid} expected_watcher_pid={expected_watcher_pid}"
        )
        return state, None
    if pid == expected_watcher_pid:
        return state, None
    return state, pid


def proc_stat(pid):
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        text = stat_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    close_paren = text.rfind(")")
    if close_paren == -1:
        return None
    fields = text[close_paren + 2:].split()
    if len(fields) < 3:
        return None
    try:
        return {"state": fields[0], "pgrp": int(fields[2])}
    except (TypeError, ValueError):
        return None


def pid_is_zombie(pid):
    stat = proc_stat(pid)
    return bool(stat and stat.get("state") == "Z")


def pid_alive(pid):
    if pid_is_zombie(pid):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return not pid_is_zombie(pid)


def process_group_alive_from_proc(pgid):
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return None
    try:
        entries = list(proc_dir.iterdir())
    except OSError:
        return None
    saw_member = False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        stat = proc_stat(int(entry.name))
        if not stat or stat.get("pgrp") != pgid:
            continue
        saw_member = True
        if stat.get("state") != "Z":
            return True
    return False if saw_member else None


def process_group_alive(pgid):
    proc_alive = process_group_alive_from_proc(pgid)
    if proc_alive is not None:
        return proc_alive
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def active_state_identity_error(state, pid):
    dispatched_pid = parse_positive_int(state.get("last_dispatched_pid"))
    if dispatched_pid != pid:
        return f"last_dispatched_pid_mismatch active_pid={pid} last_dispatched_pid={dispatched_pid}"
    dispatched_at = parse_timestamp(state.get("last_dispatched_at"))
    if dispatched_at is None:
        return "missing_or_invalid_last_dispatched_at"
    updated_at = parse_timestamp(state.get("updated_at"))
    if updated_at is None:
        return "missing_or_invalid_updated_at"
    now = datetime.now(timezone.utc)
    max_age_s = cleanup_max_state_age_s()
    dispatch_age_s = (now - dispatched_at).total_seconds()
    if dispatch_age_s < -10.0:
        return f"last_dispatched_at_from_future age_s={dispatch_age_s:.1f}"
    if dispatch_age_s > max_age_s:
        return f"stale_active_dispatch_age_s={dispatch_age_s:.1f} max_age_s={max_age_s:.1f}"
    age_s = (now - updated_at).total_seconds()
    if age_s < -10.0:
        return f"updated_at_from_future age_s={age_s:.1f}"
    if age_s > max_age_s:
        return f"stale_active_state_age_s={age_s:.1f} max_age_s={max_age_s:.1f}"
    active_log = str(state.get("active_log") or "").strip()
    if not active_log:
        return "missing_active_log"
    active_log_path = Path(active_log)
    if not active_log_path.is_absolute():
        return f"relative_active_log={active_log}"
    try:
        active_log_parent = active_log_path.parent.resolve()
        expected_log_parent = runner_log.parent.resolve()
    except OSError as exc:
        return f"active_log_parent_unresolvable={active_log}: {exc}"
    if active_log_parent != expected_log_parent:
        return f"active_log_outside_autoping_log_dir={active_log}"
    if not active_log_path.exists():
        return f"active_log_missing={active_log}"
    return None


def verified_active_target(state, pid):
    identity_error = active_state_identity_error(state, pid)
    if identity_error:
        raise ActiveTargetVerificationError(identity_error)
    group_alive = process_group_alive(pid)
    process_alive = pid_alive(pid)
    if not group_alive and not process_alive:
        return None
    if process_alive:
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            process_alive = False
        except PermissionError as exc:
            raise PermissionError(f"getpgid pid={pid}: {exc}") from exc
        except OSError as exc:
            raise ActiveTargetVerificationError(f"getpgid_failed pid={pid}: {exc}") from exc
        else:
            if pgid != pid:
                raise ActiveTargetVerificationError(f"active_pid_pgid_mismatch pid={pid} pgid={pgid}")
    group_alive = process_group_alive(pid)
    if not group_alive:
        return None
    return {"pgid": pid, "process_alive": process_alive}


def active_target_alive(state, pid):
    return verified_active_target(state, pid) is not None


def signal_active(state, pid, sig):
    target = verified_active_target(state, pid)
    if target is None:
        return False
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        log(f"[autoping-window] active ping cleanup denied pgid={pid} signal={sig.name}: {exc}")
        raise
    except OSError:
        return False
    return True


def wait_inactive(state, pid, timeout_s):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not active_target_alive(state, pid):
            return True
        time.sleep(0.05)
    return not active_target_alive(state, pid)


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
try:
    if not active_target_alive(state, pid):
        raise SystemExit(0)
except ActiveTargetVerificationError as exc:
    mark_cleanup_degraded(state, pid, f"unsafe_active_ping_cleanup_target: {exc}")
    raise SystemExit(1)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_active_target_check: {exc}")
    raise SystemExit(1)

try:
    sent = signal_active(state, pid, signal.SIGTERM)
except ActiveTargetVerificationError as exc:
    mark_cleanup_degraded(state, pid, f"unsafe_active_ping_cleanup_target: {exc}")
    raise SystemExit(1)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_sigterm: {exc}")
    raise SystemExit(1)

try:
    term_inactive = sent and wait_inactive(state, pid, 2.0)
except ActiveTargetVerificationError as exc:
    mark_cleanup_degraded(state, pid, f"unsafe_active_ping_cleanup_target: {exc}")
    raise SystemExit(1)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_active_target_check: {exc}")
    raise SystemExit(1)

if term_inactive:
    now = datetime.now(timezone.utc).isoformat()
    state.update(
        {
            "updated_at": now,
            "status": "watcher_restarting_active_ping_terminated",
            "active_pid": None,
            "active_mode": None,
            "last_active_cleanup_pid": pid,
            "last_active_cleanup_at": now,
            "last_active_cleanup_error": None,
        }
    )
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    log(f"[autoping-window] terminated stale active ping pid={pid}")
    raise SystemExit(0)

try:
    signal_active(state, pid, signal.SIGKILL)
except ActiveTargetVerificationError as exc:
    mark_cleanup_degraded(state, pid, f"unsafe_active_ping_cleanup_target: {exc}")
    raise SystemExit(1)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_sigkill: {exc}")
    raise SystemExit(1)

try:
    kill_inactive = wait_inactive(state, pid, 1.0)
except ActiveTargetVerificationError as exc:
    mark_cleanup_degraded(state, pid, f"unsafe_active_ping_cleanup_target: {exc}")
    raise SystemExit(1)
except PermissionError as exc:
    mark_cleanup_degraded(state, pid, f"permission_denied_active_target_check: {exc}")
    raise SystemExit(1)

if kill_inactive:
    now = datetime.now(timezone.utc).isoformat()
    state.update(
        {
            "updated_at": now,
            "status": "watcher_restarting_active_ping_killed",
            "active_pid": None,
            "active_mode": None,
            "last_active_cleanup_pid": pid,
            "last_active_cleanup_at": now,
            "last_active_cleanup_error": None,
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
