#!/usr/bin/env bash
# check_stale_next_items.sh — Detect TASKS.md NEXT items referencing merged PRs
# that aren't marked as Landed (struck through).
#
# Usage:
#   bash tools/checks/check_stale_next_items.sh          # Check TASKS.md
#   bash tools/checks/check_stale_next_items.sh --fix     # Mark stale merged PR refs Landed
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
PR_NUMBERS=$(echo "$NEXT_SECTION" | grep -oE 'PR #[0-9]+' | grep -oE '[0-9]+' | sort -u || true)

if [ -z "$PR_NUMBERS" ]; then
    echo "OK: No PR references found in NEXT section"
    exit 0
fi

STALE_COUNT=0
CHECKED=0
STALE_PR_NUMBERS=""

while IFS= read -r pr_num; do
    [ -z "$pr_num" ] && continue
    CHECKED=$((CHECKED + 1))

    # Check if PR is merged
    # Fail closed: if gh fails (auth, network), exit with error rather than silently skipping
    if ! PR_STATE=$(gh pr view "$pr_num" --json state --jq '.state' 2>&1); then
        echo "ERROR: Failed to check PR #${pr_num} state: $PR_STATE" >&2
        echo "   Ensure gh CLI is authenticated and network is available."
        exit 2
    fi

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
        STALE_PR_NUMBERS="${STALE_PR_NUMBERS} ${pr_num}"
        echo "STALE: PR #${pr_num} is MERGED but NEXT item not marked Landed:"
        echo "  Line: $LINE_TEXT"
        if [ "$FIX_MODE" = true ]; then
            echo "  FIX: Add **Landed** marker; non-tracker items may be struck through"
        fi
        echo ""
    done <<< "$LINES_WITH_PR"

done <<< "$PR_NUMBERS"

echo "Checked $CHECKED PR references in NEXT section"

if [ "$STALE_COUNT" -gt 0 ]; then
    if [ "$FIX_MODE" = true ]; then
        STALE_PR_NUMBERS="$STALE_PR_NUMBERS" python3 - "$TASKS_FILE" <<'PY'
import os
import re
import sys
from pathlib import Path

tasks_path = Path(sys.argv[1])
stale_prs = {
    pr
    for pr in os.environ.get("STALE_PR_NUMBERS", "").split()
    if pr.isdigit()
}
if not stale_prs:
    raise SystemExit("ERROR: --fix had no stale PR numbers to apply")

lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
try:
    next_start = next(i for i, line in enumerate(lines) if line.startswith("## NEXT"))
except StopIteration:
    raise SystemExit("ERROR: Could not find ## NEXT in TASKS.md")

try:
    next_end = next(
        i for i in range(next_start + 1, len(lines))
        if lines[i].startswith("## VECTOR")
    )
except StopIteration:
    next_end = len(lines)

marker_re = re.compile(r"~~|Landed|COMPLETE|CLOSED|Resolved")
changed = 0
for index in range(next_start, next_end):
    line = lines[index]
    line_body = line[:-1] if line.endswith("\n") else line
    newline = "\n" if line.endswith("\n") else ""
    if marker_re.search(line_body):
        continue
    if not any(f"PR #{pr}" in line_body for pr in stale_prs):
        continue

    indent_len = len(line_body) - len(line_body.lstrip())
    indent = line_body[:indent_len]
    content = line_body[indent_len:]
    if content.startswith("- Tracker sync note"):
        lines[index] = f"{indent}{content} **Landed**{newline}"
    elif content.startswith("- "):
        lines[index] = f"{indent}- ~~{content[2:]}~~ **Landed**{newline}"
    else:
        lines[index] = f"{indent}~~{content}~~ **Landed**{newline}"
    changed += 1

if changed == 0:
    raise SystemExit("ERROR: --fix found stale PRs but made no TASKS.md changes")

tasks_path.write_text("".join(lines), encoding="utf-8")
print(f"FIXED: marked {changed} stale NEXT item(s) as Landed in TASKS.md")
PY
        exec "$0"
    fi

    echo ""
    echo "❌ $STALE_COUNT stale NEXT item(s) found — merged PRs not marked Landed"
    echo "   Update TASKS.md to mark these as Landed before pushing."
    exit 1
else
    echo "✅ All NEXT items with merged PRs are properly marked"
    exit 0
fi
