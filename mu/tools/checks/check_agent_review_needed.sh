#!/usr/bin/env bash
# Check if agent review is needed for uncommitted core changes
#
# Run at session start to catch files that were edited but not agent-reviewed.
# Returns 0 if no review needed, 1 if review recommended.
#
# Usage: ./tools/check_agent_review_needed.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Check for uncommitted changes to core files
CORE_CHANGES=$(git diff --name-only HEAD 2>/dev/null | grep -E '^(rcx_pi/selfhost/|mu/)' || true)
STAGED_CORE=$(git diff --cached --name-only 2>/dev/null | grep -E '^(rcx_pi/selfhost/|mu/)' || true)

ALL_CORE_CHANGES=$(echo -e "${CORE_CHANGES}\n${STAGED_CORE}" | grep -v '^$' | sort -u || true)

if [ -z "$ALL_CORE_CHANGES" ]; then
    echo "✅ No uncommitted core file changes. Agent review not needed."
    exit 0
fi

# Check agent memory age
MEMORY_FILE=".agent_memory/findings.json"
AGENT_RUN_RECENT=false

if [ -f "$MEMORY_FILE" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        MEMORY_AGE=$(( $(date +%s) - $(stat -f %m "$MEMORY_FILE") ))
    else
        MEMORY_AGE=$(( $(date +%s) - $(stat -c %Y "$MEMORY_FILE") ))
    fi

    # 30 minutes = 1800 seconds
    if [ "$MEMORY_AGE" -lt 1800 ]; then
        AGENT_RUN_RECENT=true
    fi
fi

if [ "$AGENT_RUN_RECENT" = "true" ]; then
    echo "✅ Agent review run recently (<30min). Looks good."
    exit 0
fi

# Review needed
echo ""
echo "⚠️  AGENT REVIEW NEEDED"
echo ""
echo "Uncommitted changes to core files:"
echo "$ALL_CORE_CHANGES" | sed 's/^/  - /'
echo ""
echo "No recent agent review detected."
echo ""
echo "Run before committing:"
echo "  python tools/runners/run_review.py <files> --depth full"
echo ""
exit 1
