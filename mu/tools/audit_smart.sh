#!/usr/bin/env bash
# Smart test runner - only runs tests affected by your changes
# Uses pytest-testmon to track dependencies
#
# First run: builds dependency database (~same as full run)
# Subsequent runs: only runs affected tests (often 80%+ faster)
#
# Usage:
#   ./tools/audit_smart.sh           # Run affected tests
#   ./tools/audit_smart.sh --full    # Force full run, rebuild db
#   ./tools/audit_smart.sh --clean   # Clear testmon database

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if testmon is installed
if ! python3 -c "import pytest_testmon" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-testmon...${NC}"
    pip install pytest-testmon
fi

case "${1:-}" in
    --full)
        echo -e "${YELLOW}Full run: rebuilding testmon database...${NC}"
        rm -f .testmondata
        PYTHONHASHSEED=0 pytest --testmon -q
        ;;
    --clean)
        echo -e "${YELLOW}Cleaning testmon database...${NC}"
        rm -f .testmondata
        echo -e "${GREEN}Done. Next run will be a full run.${NC}"
        ;;
    *)
        if [ ! -f .testmondata ]; then
            echo -e "${YELLOW}First run: building dependency database...${NC}"
            echo -e "${YELLOW}This will take as long as a full run. Subsequent runs will be faster.${NC}"
        else
            echo -e "${GREEN}Smart run: only testing affected code...${NC}"
        fi

        PYTHONHASHSEED=0 pytest --testmon -q

        if [ -f .testmondata ]; then
            echo ""
            echo -e "${GREEN}Testmon database updated. Future runs will be faster.${NC}"
        fi
        ;;
esac
