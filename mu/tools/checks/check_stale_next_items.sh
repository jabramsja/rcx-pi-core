#!/usr/bin/env bash
# check_stale_next_items.sh — Detect TASKS.md active items referencing merged
# PRs/branches that aren't marked as Landed (struck through).
#
# Usage:
#   bash tools/checks/check_stale_next_items.sh          # Check TASKS.md
#   bash tools/checks/check_stale_next_items.sh --fix     # Mark stale merged PR refs Landed
#
# Exit codes:
#   0 -> all active items with merged PRs/branches are properly marked
#   1 -> stale items found (merged PR referenced but not Landed)
#   2 -> usage / gh error

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

TASKS_FILE="TASKS.md"
FIX_MODE=false
GH_RETRY_ATTEMPTS="${RCX_GH_RETRY_ATTEMPTS:-3}"
GH_RETRY_SLEEP_SECONDS="${RCX_GH_RETRY_SLEEP_SECONDS:-2}"

if [[ ! "$GH_RETRY_ATTEMPTS" =~ ^[0-9]+$ ]] || [ "$GH_RETRY_ATTEMPTS" -lt 1 ]; then
    echo "ERROR: RCX_GH_RETRY_ATTEMPTS must be a positive integer" >&2
    exit 2
fi
if [[ ! "$GH_RETRY_SLEEP_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "ERROR: RCX_GH_RETRY_SLEEP_SECONDS must be a non-negative integer" >&2
    exit 2
fi

if [ "${1:-}" = "--fix" ]; then
    FIX_MODE=true
fi

if [ ! -f "$TASKS_FILE" ]; then
    echo "ERROR: $TASKS_FILE not found" >&2
    exit 2
fi

# Extract active sections.
ACTIVE_SECTION=$(sed -n '/^## NOW/,/^## VECTOR/p' "$TASKS_FILE" | sed '$d')
NEXT_SECTION=$(sed -n '/^## NEXT/,/^## VECTOR/p' "$TASKS_FILE" | sed '$d')

if [ -z "$NEXT_SECTION" ]; then
    echo "WARNING: Could not extract NEXT section from $TASKS_FILE"
    exit 0
fi
if [ -z "$ACTIVE_SECTION" ]; then
    echo "WARNING: Could not extract NOW/NEXT active sections from $TASKS_FILE"
    exit 0
fi

# Find all PR references in NEXT section
PR_NUMBERS=$(echo "$NEXT_SECTION" | grep -oE 'PR #[0-9]+' | grep -oE '[0-9]+' | sort -u || true)

STALE_COUNT=0
CHECKED=0
STALE_PR_NUMBERS=""
STALE_WAVE_IDS=""
MARKER_RE='~~|Landed|COMPLETE|CLOSED|Resolved|CLEARED|IMPLEMENTED'

run_gh_with_retry() {
    local attempt
    local output=""
    local status=0

    for ((attempt = 1; attempt <= GH_RETRY_ATTEMPTS; attempt++)); do
        if output=$(gh "$@" 2>&1); then
            printf '%s\n' "$output"
            return 0
        else
            status=$?
        fi
        if [ "$attempt" -lt "$GH_RETRY_ATTEMPTS" ]; then
            echo "WARNING: gh $* failed on attempt ${attempt}/${GH_RETRY_ATTEMPTS}: $output" >&2
            sleep "$GH_RETRY_SLEEP_SECONDS"
        fi
    done

    printf '%s\n' "$output"
    return "$status"
}

merged_pr_for_wave_branch() {
    local wave_id="$1"
    local merged_pr
    local branch_filter

    if ! merged_pr=$(run_gh_with_retry pr list --state merged --head "$wave_id" --json number --jq '.[0].number // empty' --limit 1); then
        printf '%s\n' "$merged_pr"
        return 2
    fi
    if [ -n "$merged_pr" ]; then
        printf '%s\n' "$merged_pr"
        return 0
    fi

    # Accept both plain wave branches and contributor-prefixed wave branches.
    branch_filter="map(select(.headRefName == \"${wave_id}\" or (.headRefName | endswith(\"/${wave_id}\")))) | .[0].number // empty"
    if ! merged_pr=$(
        run_gh_with_retry pr list \
            --state merged \
            --search "$wave_id" \
            --json number,headRefName \
            --jq "$branch_filter" \
            --limit 50
    ); then
        printf '%s\n' "$merged_pr"
        return 2
    fi

    if [ -n "$merged_pr" ]; then
        printf '%s\n' "$merged_pr"
        return 0
    fi

    if ! merged_pr=$(
        run_gh_with_retry pr list \
            --state merged \
            --json number,headRefName \
            --jq "$branch_filter" \
            --limit 500
    ); then
        printf '%s\n' "$merged_pr"
        return 2
    fi

    printf '%s\n' "$merged_pr"
}

if [ -n "$PR_NUMBERS" ]; then
    while IFS= read -r pr_num; do
        [ -z "$pr_num" ] && continue
        CHECKED=$((CHECKED + 1))

        # Check if PR is merged
        # Fail closed after bounded retry: if gh fails (auth, network), exit
        # with error rather than silently skipping stale merged PRs.
        if ! PR_STATE=$(run_gh_with_retry pr view "$pr_num" --json state --jq '.state'); then
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
            LINE_TEXT=$(echo "$line" | cut -d: -f2-)

            # Check if line is struck through or contains a completed marker.
            if echo "$LINE_TEXT" | grep -qE "$MARKER_RE"; then
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
fi

# Slashed task labels such as [CI-REPAIR/<wave-id>] are active queue entries
# without PR text. Treat a merged same-name or contributor-prefixed branch as
# stale unless the entry is already closed/struck through.
ACTIVE_TASK_LINES=$(
    echo "$ACTIVE_SECTION" \
        | grep -nE '^- (~~)?\*\*\[[^]]+/[a-z0-9][a-z0-9_-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}\]\*\*' \
        || true
)
while IFS= read -r line; do
    [ -z "$line" ] && continue
    LINE_TEXT=$(echo "$line" | cut -d: -f2-)
    if echo "$LINE_TEXT" | grep -qE "$MARKER_RE"; then
        continue
    fi
    WAVE_ID=$(echo "$LINE_TEXT" | sed -nE 's/^- (~~)?\*\*\[[^]]+\/([^]]+)\]\*\*.*/\2/p')
    [ -z "$WAVE_ID" ] && continue
    CHECKED=$((CHECKED + 1))
    if ! MERGED_PR=$(merged_pr_for_wave_branch "$WAVE_ID"); then
        echo "ERROR: Failed to check merged PR for wave branch ${WAVE_ID}: $MERGED_PR" >&2
        echo "   Ensure gh CLI is authenticated and network is available."
        exit 2
    fi
    if [ -z "$MERGED_PR" ]; then
        continue
    fi
    STALE_COUNT=$((STALE_COUNT + 1))
    STALE_WAVE_IDS="${STALE_WAVE_IDS} ${WAVE_ID}"
    echo "STALE: wave branch ${WAVE_ID} merged as PR #${MERGED_PR} but active item not marked Landed:"
    echo "  Line: $LINE_TEXT"
    if [ "$FIX_MODE" = true ]; then
        echo "  FIX: Add **Landed** marker; non-tracker items may be struck through"
    fi
    echo ""
done <<< "$ACTIVE_TASK_LINES"

echo "Checked $CHECKED PR/branch references in active sections"

if [ "$STALE_COUNT" -gt 0 ]; then
    if [ "$FIX_MODE" = true ]; then
        STALE_PR_NUMBERS="$STALE_PR_NUMBERS" STALE_WAVE_IDS="$STALE_WAVE_IDS" python3 - "$TASKS_FILE" <<'PY'
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
stale_waves = {
    wave
    for wave in os.environ.get("STALE_WAVE_IDS", "").split()
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]+-[0-9]{4}-[0-9]{2}-[0-9]{2}", wave)
}
if not stale_prs and not stale_waves:
    raise SystemExit("ERROR: --fix had no stale PR numbers or wave ids to apply")

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

marker_re = re.compile(r"~~|Landed|COMPLETE|CLOSED|Resolved|CLEARED|IMPLEMENTED")
changed = 0
try:
    now_start = next(i for i, line in enumerate(lines) if line.startswith("## NOW"))
except StopIteration:
    now_start = next_start

for index in range(now_start, next_end):
    line = lines[index]
    line_body = line[:-1] if line.endswith("\n") else line
    newline = "\n" if line.endswith("\n") else ""
    if marker_re.search(line_body):
        continue
    has_stale_pr = any(f"PR #{pr}" in line_body for pr in stale_prs)
    has_stale_wave = any(
        re.search(rf"\*\*\[[^\]]+/{re.escape(wave)}\]\*\*", line_body)
        for wave in stale_waves
    )
    if not has_stale_pr and not has_stale_wave:
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
print(f"FIXED: marked {changed} stale active item(s) as Landed in TASKS.md")
PY
        exec "$0"
    fi

    echo ""
    echo "❌ $STALE_COUNT stale active item(s) found — merged PRs/branches not marked Landed"
    echo "   Update TASKS.md to mark these as Landed before pushing."
    exit 1
else
    echo "✅ All active items with merged PRs/branches are properly marked"
    exit 0
fi
