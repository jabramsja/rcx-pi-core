#!/usr/bin/env bash
# check_stale_next_items.sh — Detect TASKS.md NEXT items referencing merged PRs
# that aren't marked as Landed (struck through).
#
# Usage:
#   bash tools/checks/check_stale_next_items.sh          # Check TASKS.md
#   bash tools/checks/check_stale_next_items.sh --fix     # Show what needs updating
#
# Exit codes:
#   0 -> all NEXT items with merged PRs are properly marked
#   1 -> stale items found (merged PR referenced but not Landed)
#   2 -> usage / gh error

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

TASKS_FILE="TASKS.md"
FIX_MODE=false

if [ "${1:-}" = "--fix" ]; then
    FIX_MODE=true
fi

if [ ! -f "$TASKS_FILE" ]; then
    echo "ERROR: $TASKS_FILE not found" >&2
    exit 2
fi

# Extract NEXT section (between ## NEXT and ## VECTOR)
NEXT_SECTION=$(sed -n '/^## NEXT/,/^## VECTOR/p' "$TASKS_FILE" | sed '$d')

if [ -z "$NEXT_SECTION" ]; then
    echo "WARNING: Could not extract NEXT section from $TASKS_FILE"
    exit 0
fi

# Find all PR references in NEXT section
PR_NUMBERS=$(echo "$NEXT_SECTION" | grep -oE 'PR #[0-9]+' | grep -oE '[0-9]+' | sort -u)

if [ -z "$PR_NUMBERS" ]; then
    echo "OK: No PR references found in NEXT section"
    exit 0
fi

STALE_COUNT=0
CHECKED=0

while IFS= read -r pr_num; do
    [ -z "$pr_num" ] && continue
    CHECKED=$((CHECKED + 1))

    # Check if PR is merged
    PR_STATE=$(gh pr view "$pr_num" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")

    if [ "$PR_STATE" != "MERGED" ]; then
        continue
    fi

    # PR is merged — check if the line referencing it is struck through
    # Look for the PR reference in NEXT section and check if it's in a ~~...~~ line
    LINES_WITH_PR=$(echo "$NEXT_SECTION" | grep -n "PR #${pr_num}" || true)

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        LINE_NUM=$(echo "$line" | cut -d: -f1)
        LINE_TEXT=$(echo "$line" | cut -d: -f2-)

        # Check if line is struck through (~~) or contains "Landed"
        if echo "$LINE_TEXT" | grep -qE '~~|Landed|COMPLETE|CLOSED|Resolved'; then
            continue
        fi

        # Stale item found
        STALE_COUNT=$((STALE_COUNT + 1))
        echo "STALE: PR #${pr_num} is MERGED but NEXT item not marked Landed:"
        echo "  Line: $LINE_TEXT"
        if [ "$FIX_MODE" = true ]; then
            echo "  FIX: Strike through this item and add **Landed** marker"
        fi
        echo ""
    done <<< "$LINES_WITH_PR"

done <<< "$PR_NUMBERS"

echo "Checked $CHECKED PR references in NEXT section"

if [ "$STALE_COUNT" -gt 0 ]; then
    echo ""
    echo "❌ $STALE_COUNT stale NEXT item(s) found — merged PRs not marked Landed"
    echo "   Update TASKS.md to mark these as Landed before pushing."
    exit 1
else
    echo "✅ All NEXT items with merged PRs are properly marked"
    exit 0
fi
