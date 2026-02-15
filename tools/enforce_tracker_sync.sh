#!/usr/bin/env bash
# Enforce tracker sync for core structural code changes.
#
# Policy:
# - If files under rcx_pi/selfhost/ or mu/ change, at least one tracker must change:
#   STATUS.md or TASKS.md
#
# Usage:
#   tools/enforce_tracker_sync.sh --staged
#   tools/enforce_tracker_sync.sh --range origin/dev...HEAD
#   tools/enforce_tracker_sync.sh --files rcx_pi/selfhost/step_mu.py STATUS.md
#
# Exit codes:
#   0 -> compliant (or no core changes)
#   1 -> violation
#   2 -> usage / git range error

set -euo pipefail

cd "$(dirname "$0")/.." 2>/dev/null || cd "$(git rev-parse --show-toplevel)"

MODE="staged"
RANGE=""
FILES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --staged)
            MODE="staged"
            shift
            ;;
        --range)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --range requires an argument" >&2
                exit 2
            fi
            MODE="range"
            RANGE="$2"
            shift 2
            ;;
        --files)
            MODE="files"
            shift
            FILES=("$@")
            break
            ;;
        -h|--help)
            sed -n '1,24p' "$0"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

CHANGED_FILES=""
case "$MODE" in
    staged)
        CHANGED_FILES="$(git diff --cached --name-only --diff-filter=ACMR || true)"
        ;;
    range)
        if ! CHANGED_FILES="$(git diff --name-only --diff-filter=ACMR "$RANGE" 2>/dev/null)"; then
            echo "ERROR: Unable to diff range '$RANGE'" >&2
            exit 2
        fi
        ;;
    files)
        if [[ ${#FILES[@]} -eq 0 ]]; then
            CHANGED_FILES=""
        else
            CHANGED_FILES="$(printf '%s\n' "${FILES[@]}")"
        fi
        ;;
esac

CORE_CHANGED="$(echo "$CHANGED_FILES" | grep -E '^(rcx_pi/selfhost/|mu/)' | grep -v '^mu/docs/' || true)"
if [[ -z "$CORE_CHANGED" ]]; then
    echo "Tracker sync OK: no core changes detected."
    exit 0
fi

TRACKER_CHANGED="$(echo "$CHANGED_FILES" | grep -E '^(STATUS\.md|TASKS\.md)$' || true)"
if [[ -n "$TRACKER_CHANGED" ]]; then
    echo "Tracker sync OK: core changes include STATUS.md/TASKS.md update."
    exit 0
fi

echo ""
echo "❌ TRACKER SYNC VIOLATION"
echo "Core structural files changed, but STATUS.md/TASKS.md were not updated."
echo ""
echo "Core files changed:"
echo "$CORE_CHANGED" | sed 's/^/  - /'
echo ""
echo "Required: stage at least one tracker file:"
echo "  - STATUS.md"
echo "  - TASKS.md"
echo ""
echo "If behavior/phase/task state did not change, add a short explicit note in TASKS.md."
echo ""
exit 1

