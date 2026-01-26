#!/usr/bin/env bash
# Run agents locally via Claude Code (uses Max subscription)
#
# This script reminds you to run agents in Claude Code before pushing.
# The actual agents run inside your Claude Code session using your subscription.
#
# Usage:
#   ./tools/run_agents_local.sh [files...]
#
# Example:
#   ./tools/run_agents_local.sh rcx_pi/deep_eval.py
#   ./tools/run_agents_local.sh  # prompts for files

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           RCX Local Agent Runner (Subscription)              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get files to check
if [ $# -gt 0 ]; then
    FILES="$*"
else
    echo "No files specified. Getting recently modified files..."
    FILES=$(git diff --name-only HEAD~1 | grep -E '\.(py|json)$' | tr '\n' ' ' || true)
    if [ -z "$FILES" ]; then
        FILES=$(find rcx_pi -name "*.py" | head -5 | tr '\n' ' ')
    fi
fi

echo -e "${YELLOW}Files to review:${NC}"
for f in $FILES; do
    echo "  - $f"
done
echo ""

echo -e "${GREEN}To run agents, copy/paste these commands into Claude Code:${NC}"
echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""
echo "  Run verifier on $FILES"
echo ""
echo "  Run adversary on $FILES"
echo ""
echo "  Run expert on $FILES"
echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""
echo -e "${YELLOW}Or simply ask:${NC}"
echo ""
echo "  \"Run verifier, adversary, and expert agents on the changed files\""
echo ""
echo -e "${BLUE}This uses your Max subscription - no API charges.${NC}"
echo ""

# Check if Claude Code is available
if command -v claude &> /dev/null; then
    echo -e "${GREEN}Claude Code detected. You can also run:${NC}"
    echo "  claude \"Run verifier on $FILES\""
    echo ""
fi

echo "After agents pass, you can safely push."
