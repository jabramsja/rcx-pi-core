#!/usr/bin/env bash
# Verify changed-file scope and print a deterministic "verified change files" table.
#
# Usage:
#   tools/checks/verify_changed_files.sh --staged
#   tools/checks/verify_changed_files.sh --range origin/dev...HEAD
#
# Exit codes:
#   0 => all files in scope are valid/tracked paths
#   1 => invalid scope or at least one file failed verification

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

usage() {
    cat <<'USAGE'
Usage:
  tools/checks/verify_changed_files.sh --staged
  tools/checks/verify_changed_files.sh --range <git-range>
USAGE
}

MODE=""
RANGE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --staged)
            MODE="staged"
            shift
            ;;
        --range)
            MODE="range"
            RANGE="${2:-}"
            if [ -z "$RANGE" ]; then
                echo "ERROR: --range requires a value" >&2
                usage
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "ERROR: unknown arg: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "ERROR: must provide --staged or --range" >&2
    usage
    exit 1
fi

if [ "$MODE" = "staged" ]; then
    SCOPE_LABEL="staged"
    DIFF_CMD=(git diff --cached --name-status)
else
    SCOPE_LABEL="$RANGE"
    DIFF_CMD=(git diff --name-status "$RANGE")
fi

DIFF_OUTPUT="$("${DIFF_CMD[@]}")"

if [ -z "$DIFF_OUTPUT" ]; then
    echo "ERROR: no changed files in scope: $SCOPE_LABEL" >&2
    exit 1
fi

echo "Verified Change Files (scope: $SCOPE_LABEL)"
echo "| Status | Path | Exists | Tracked |"
echo "|---|---|---|---|"

FAILED=0

verify_path_row() {
    local status="$1"
    local path="$2"
    local exists="no"
    local tracked="no"

    if [ -e "$path" ]; then
        exists="yes"
    fi

    if git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
        tracked="yes"
    elif git cat-file -e "HEAD:$path" >/dev/null 2>&1; then
        # Handles deleted/renamed-from paths no longer in index.
        tracked="yes"
    fi

    if [[ "$path" == /* ]] || [[ "$path" == *".."* ]]; then
        tracked="invalid-path"
        FAILED=1
    elif [ "$tracked" != "yes" ]; then
        FAILED=1
    fi

    echo "| $status | \`$path\` | $exists | $tracked |"
}

while IFS=$'\t' read -r status path_a path_b; do
    [ -z "${status:-}" ] && continue
    if [[ "$status" =~ ^R[0-9]+$ ]] || [[ "$status" =~ ^C[0-9]+$ ]]; then
        # Rename/copy has source + destination; verify destination path.
        verify_path_row "$status" "$path_b"
    else
        verify_path_row "$status" "$path_a"
    fi
done <<< "$DIFF_OUTPUT"

if [ "$FAILED" -ne 0 ]; then
    echo "ERROR: one or more changed files failed verification" >&2
    exit 1
fi

exit 0
