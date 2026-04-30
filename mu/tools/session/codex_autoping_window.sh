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
touch "$RUNNER_LOG" "$SUMMARY_PATH"

python3 "$WATCH_SCRIPT" \
    --repo-root "$REPO" \
    --thread-id "$THREAD_ID" \
    --interval "$INTERVAL" \
    --initial-delay "$INITIAL_DELAY" \
    --ping-timeout "$PING_TIMEOUT" \
    --bus-dir "$BUS_DIR" \
    --tmux-session "$TMUX_SESSION" \
    --tmux-pane "$TMUX_PANE" \
    >"$RUNNER_LOG" 2>&1 &
WATCHER_PID="$!"

cleanup() {
    kill "$WATCHER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

printf 'Watching %s\n' "$RUNNER_LOG"
printf 'State: %s\n' "$STATE_PATH"
printf 'Summary: %s\n\n' "$SUMMARY_PATH"
printf '[autoping-launch] watcher_pid=%s\n' "$WATCHER_PID"

while true; do
    printf '\033[H\033[2J'
    python3 "$RENDER_SCRIPT" --thread-id "$THREAD_ID"
    sleep 2
done
