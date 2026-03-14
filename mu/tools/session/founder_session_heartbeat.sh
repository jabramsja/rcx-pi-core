#!/usr/bin/env bash
set -uo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/founder_session_heartbeat.sh <mode> [--interval SEC] [--count N] [--run-guard] [--bell]

Modes:
  redteam
  parity
  docs
  closeout

Notes:
  - Prints a concise founder-protocol reminder on a recurring interval.
  - Run this in a second terminal during a long session.
  - --run-guard executes ./tools/session/founder_session_guard.sh <mode> once before the loop.
  - --count limits the number of reminders; omit it for an infinite loop.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -eq 0 ]; then
    usage
    exit 0
fi

MODE="$1"
shift
INTERVAL=300
COUNT=0
RUN_GUARD=0
BELL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --interval)
            INTERVAL="${2:-}"
            shift
            ;;
        --count)
            COUNT="${2:-}"
            shift
            ;;
        --run-guard)
            RUN_GUARD=1
            ;;
        --bell)
            BELL=1
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

case "$MODE" in
    redteam|parity|docs|closeout)
        ;;
    *)
        echo "ERROR: unknown mode '$MODE'" >&2
        usage >&2
        exit 2
        ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: must run inside the WorkingRCX git repo" >&2
    exit 2
}
cd "$REPO_ROOT"

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -le 0 ]; then
    echo "ERROR: --interval must be a positive integer (seconds)" >&2
    exit 2
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --count must be a non-negative integer" >&2
    exit 2
fi

if [ "$RUN_GUARD" -eq 1 ]; then
    ./tools/session/founder_session_guard.sh "$MODE"
    echo ""
fi

print_mode_notes() {
    case "$MODE" in
        redteam)
            echo "Re-anchor on code truth over docs."
            echo "Keep findings split into DEFECT / POLICY_BOUND / DOC_ACCURACY."
            echo "Distinguish full L4 completion from active bounded reduction work."
            ;;
        parity)
            echo "Re-check Python/JS allowlists, fallbacks, and live path threading."
            echo "Ratchet totals alone do not prove parity."
            ;;
        docs)
            echo "Re-check STATUS/TASKS against live runtime flags and active doctrine docs."
            echo "Treat GROUNDING_TESTS: none on live current-state docs as a drift smell."
            ;;
        closeout)
            echo "Preserve direct-vs-inferred evidence in final closeout."
            echo "Use reports/deferred/blocking and reports/deferred/non_blocking."
            ;;
    esac
}

ITERATION=0
while :; do
    ITERATION=$((ITERATION + 1))
    NOW="$(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "[founder-heartbeat][$NOW] mode=$MODE beat=$ITERATION"
    echo "Re-read AGENTS.md and FOUNDER_SESSION_BOOTSTRAP.md if scope drifted."
    echo "Guard command: ./tools/session/founder_session_guard.sh $MODE --run"
    print_mode_notes
    if [ "$BELL" -eq 1 ]; then
        printf '\a'
    fi
    echo ""

    if [ "$COUNT" -gt 0 ] && [ "$ITERATION" -ge "$COUNT" ]; then
        break
    fi

    sleep "$INTERVAL"
done
