#!/usr/bin/env bash
# check_untracked_artifacts.sh — Detect untracked backup/temp clutter in governed subtrees.
#
# Scans mu/tools/, mu/tests/, mu/scripts/ for untracked files matching
# backup/temp patterns (*.bak*, *.orig, *.rej, *.swp, *.swo, *~).
#
# Supports an allowlist file (.untracked_artifact_allowlist) for rare exceptions.
# Each line in the allowlist is a path relative to repo root (blank lines and
# lines starting with # are ignored).
#
# Exit 0 = clean (or all violations allowlisted), Exit 1 = clutter found.
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
PATTERNS=(
    "*.bak"
    "*.bak.*"
    "*.orig"
    "*.rej"
    "*.swp"
    "*.swo"
    "*~"
)

# Load allowlist (file-based, reviewed exceptions)
ALLOWLIST_FILE="$REPO_ROOT/.untracked_artifact_allowlist"
_is_allowlisted() {
    local file="$1"
    if [ ! -f "$ALLOWLIST_FILE" ]; then
        return 1
    fi
    while IFS= read -r line; do
        # Strip comments and whitespace
        line="${line%%#*}"
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "$line" ] && continue
        if [ "$line" = "$file" ]; then
            return 0
        fi
    done < "$ALLOWLIST_FILE"
    return 1
}

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

RAW_VIOLATIONS=()
for subtree in "${SUBTREES[@]}"; do
    if [ -d "$subtree" ]; then
        while IFS= read -r file; do
            [ -n "$file" ] && RAW_VIOLATIONS+=("$file")
        done < <(find "$subtree" "${FIND_ARGS[@]}" -type f 2>/dev/null)
    fi
done

# Filter out allowlisted files
VIOLATIONS=()
ALLOWLISTED_COUNT=0
if [ ${#RAW_VIOLATIONS[@]} -gt 0 ]; then
    for v in "${RAW_VIOLATIONS[@]}"; do
        if _is_allowlisted "$v"; then
            ALLOWLISTED_COUNT=$((ALLOWLISTED_COUNT + 1))
        else
            VIOLATIONS+=("$v")
        fi
    done
fi

if [ ${#VIOLATIONS[@]} -eq 0 ]; then
    if ! $QUIET; then
        if [ "$ALLOWLISTED_COUNT" -gt 0 ]; then
            echo "OK: $ALLOWLISTED_COUNT artifact(s) allowlisted, 0 violations"
        else
            echo "OK: No untracked backup/temp artifacts in governed subtrees"
        fi
    fi
    exit 0
else
    if ! $QUIET; then
        echo "FAIL: ${#VIOLATIONS[@]} untracked backup/temp artifact(s) found:"
        echo ""
        for v in "${VIOLATIONS[@]}"; do
            echo "  - $v"
        done
        if [ "$ALLOWLISTED_COUNT" -gt 0 ]; then
            echo ""
            echo "  ($ALLOWLISTED_COUNT additional file(s) allowlisted)"
        fi
        echo ""
        echo "Remediation: rm these files (they are gitignored, not tracked):"
        echo ""
        echo "  rm ${VIOLATIONS[*]}"
        echo ""
        echo "Or delete all at once:"
        echo "  find mu/tools mu/tests mu/scripts ${FIND_ARGS[*]} -type f -delete"
        echo ""
        echo "If a file must be kept, add to .untracked_artifact_allowlist with rationale."
    fi
    exit 1
fi
