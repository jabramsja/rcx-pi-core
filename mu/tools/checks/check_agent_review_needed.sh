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
CORE_CHANGES=$(git diff --name-only HEAD 2>/dev/null | grep -E '^(rcx_pi/selfhost/|mu/host/python/rcx_pi/selfhost/|mu/)' || true)
STAGED_CORE=$(git diff --cached --name-only 2>/dev/null | grep -E '^(rcx_pi/selfhost/|mu/host/python/rcx_pi/selfhost/|mu/)' || true)

ALL_CORE_CHANGES=$(echo -e "${CORE_CHANGES}\n${STAGED_CORE}" | grep -v '^$' | sort -u || true)

if [ -z "$ALL_CORE_CHANGES" ]; then
    echo "✅ No uncommitted core file changes. Agent review not needed."
    exit 0
fi

# Check for recent agent output (same paths as bridge hook for consistency)
# 1. SDK review ledger (.agent_memory/findings.json) - must be non-empty
# 2. Bridge bus artifacts (.agent_bus/raw/*.txt - non-empty only)
# 3. SDK run_review.py reports (reports/*review*.md - non-empty only)

# Check .agent_memory/findings.json (must be non-empty)
RECENT_MEMORY=0
if [ -f ".agent_memory/findings.json" ] && [ -s ".agent_memory/findings.json" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        MEMORY_AGE=$(( $(date +%s) - $(stat -f %m ".agent_memory/findings.json") ))
    else
        MEMORY_AGE=$(( $(date +%s) - $(stat -c %Y ".agent_memory/findings.json") ))
    fi
    # 2 hours = 7200 seconds
    if [ "$MEMORY_AGE" -lt 7200 ]; then
        RECENT_MEMORY=1
    fi
fi

# Check .agent_bus/raw/*.txt (non-empty files only)
RECENT_BUS=$( (find .agent_bus/raw/ -name "*.txt" -size +0 -mmin -120 2>/dev/null || true) | wc -l | tr -d ' ')

# Check reports/*review*.md (non-empty files only)
RECENT_REPORTS=$( (find reports/ -maxdepth 1 -name "*review*.md" -size +0 -mmin -120 2>/dev/null || true) | wc -l | tr -d ' ')

if [ "$RECENT_MEMORY" -gt 0 ] || [ "$RECENT_BUS" -gt 0 ] || [ "$RECENT_REPORTS" -gt 0 ]; then
    echo "✅ Agent review run recently (<2h). Looks good."
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
echo "  python tools/runners/run_review.py <files> --depth full --output reports/agent_review.md"
echo ""
exit 1
