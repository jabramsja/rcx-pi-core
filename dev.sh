#!/bin/bash
# dev.sh - Single entrypoint for fast development iteration
#
# Usage: ./dev.sh [--full]
#
# Default: Fast audit + JS parity (quick feedback loop)
# --full:  Full audit including fuzzers (before push)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== RCX Dev Check ===${NC}"
echo ""

# Check if --full flag is passed
if [[ "$1" == "--full" ]]; then
    echo -e "${YELLOW}Running FULL audit (includes fuzzers)...${NC}"
    echo ""
    ./tools/audit_all.sh
else
    echo -e "${YELLOW}Running FAST audit...${NC}"
    echo ""
    ./tools/audit_fast.sh
fi

# Check exit status
if [[ $? -eq 0 ]]; then
    echo ""
    echo -e "${GREEN}✅ Dev check passed${NC}"
    echo ""
    echo "Next steps:"
    echo "  ./dev.sh --full   # Run full audit before push"
    echo "  git status        # Check changes"
else
    echo ""
    echo -e "${RED}❌ Dev check failed${NC}"
    exit 1
fi
