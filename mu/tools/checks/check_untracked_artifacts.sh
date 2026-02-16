#!/usr/bin/env bash
# check_untracked_artifacts.sh — Detect untracked backup/temp clutter in governed subtrees.
#
# Scans mu/tools/, mu/tests/, mu/scripts/ for untracked files matching
# backup/temp patterns (*.bak*, *.orig, *.rej, *.swp, *.swo, *~).
#
# These files are gitignored (won't be committed) but still clutter the
# working tree and indicate sloppy editing habits.
#
# Exit 0 = clean, Exit 1 = clutter found.
#
# Usage: ./tools/checks/check_untracked_artifacts.sh
#        ./tools/checks/check_untracked_artifacts.sh --quiet  (exit code only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

QUIET=false
if [ "${1:-}" = "--quiet" ]; then
    QUIET=true
fi

# Governed subtrees
SUBTREES=("mu/tools" "mu/tests" "mu/scripts")

# Backup/temp patterns to reject
# Note: find -name patterns, one per entry
PATTERNS=(
    "*.bak"
    "*.bak.*"
    "*.orig"
    "*.rej"
    "*.swp"
    "*.swo"
    "*~"
)

# Build find -name arguments: ( -name "*.bak" -o -name "*.orig" ... )
FIND_ARGS=()
first=true
for p in "${PATTERNS[@]}"; do
    if $first; then
        FIND_ARGS+=("(" "-name" "$p")
        first=false
    else
        FIND_ARGS+=("-o" "-name" "$p")
    fi
done
FIND_ARGS+=(")")

VIOLATIONS=()
for subtree in "${SUBTREES[@]}"; do
    if [ -d "$subtree" ]; then
        while IFS= read -r file; do
            [ -n "$file" ] && VIOLATIONS+=("$file")
        done < <(find "$subtree" "${FIND_ARGS[@]}" -type f 2>/dev/null)
    fi
done

if [ ${#VIOLATIONS[@]} -eq 0 ]; then
    if ! $QUIET; then
        echo "OK: No untracked backup/temp artifacts in governed subtrees"
    fi
    exit 0
else
    if ! $QUIET; then
        echo "WARNING: ${#VIOLATIONS[@]} untracked backup/temp artifact(s) found:"
        echo ""
        for v in "${VIOLATIONS[@]}"; do
            echo "  - $v"
        done
        echo ""
        echo "Remediation: rm these files (they are gitignored, not tracked):"
        echo ""
        echo "  rm ${VIOLATIONS[*]}"
        echo ""
        echo "Or delete all at once:"
        echo "  find mu/tools mu/tests mu/scripts ${FIND_ARGS[*]} -type f -delete"
    fi
    exit 1
fi
