#!/bin/bash
# doctor.sh - Verify environment dependencies for RCX development
#
# Usage: ./doctor.sh
#
# Checks: Python 3.10+, Node.js 18+, pytest, hypothesis, git

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== RCX Environment Doctor ===${NC}"
echo ""

ISSUES=0

# Check Python
echo -n "Python 3.10+: "
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
        echo -e "${GREEN}✓ $PY_VERSION${NC}"
    else
        echo -e "${RED}✗ Found $PY_VERSION (need 3.10+)${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "${RED}✗ Not found${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check Node.js
echo -n "Node.js 18+:  "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    if [[ "$NODE_MAJOR" -ge 18 ]]; then
        echo -e "${GREEN}✓ $NODE_VERSION${NC}"
    else
        echo -e "${RED}✗ Found $NODE_VERSION (need 18+)${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "${RED}✗ Not found${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check pytest
echo -n "pytest:       "
if python3 -c "import pytest" 2>/dev/null; then
    PYTEST_VERSION=$(python3 -c "import pytest; print(pytest.__version__)")
    echo -e "${GREEN}✓ $PYTEST_VERSION${NC}"
else
    echo -e "${RED}✗ Not found (pip install pytest)${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check hypothesis
echo -n "hypothesis:   "
if python3 -c "import hypothesis" 2>/dev/null; then
    HYP_VERSION=$(python3 -c "import hypothesis; print(hypothesis.__version__)")
    echo -e "${GREEN}✓ $HYP_VERSION${NC}"
else
    echo -e "${RED}✗ Not found (pip install hypothesis)${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check pytest-xdist (optional but recommended)
echo -n "pytest-xdist: "
if python3 -c "import xdist" 2>/dev/null; then
    XDIST_VERSION=$(python3 -c "import xdist; print(xdist.__version__)")
    echo -e "${GREEN}✓ $XDIST_VERSION${NC}"
else
    echo -e "${YELLOW}○ Not found (optional: pip install pytest-xdist)${NC}"
fi

# Check git
echo -n "git:          "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | sed 's/git version //')
    echo -e "${GREEN}✓ $GIT_VERSION${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Check gh CLI (optional)
echo -n "gh CLI:       "
if command -v gh &> /dev/null; then
    GH_VERSION=$(gh --version | head -1 | sed 's/gh version //' | cut -d' ' -f1)
    echo -e "${GREEN}✓ $GH_VERSION${NC}"
else
    echo -e "${YELLOW}○ Not found (optional: for PR workflows)${NC}"
fi

echo ""

# Summary
if [[ $ISSUES -eq 0 ]]; then
    echo -e "${GREEN}✅ Environment OK${NC}"
    echo ""
    echo "Quick start:"
    echo "  ./dev.sh          # Fast audit + JS parity"
    echo "  ./dev.sh --full   # Full audit with fuzzers"
    exit 0
else
    echo -e "${RED}❌ $ISSUES issue(s) found${NC}"
    echo ""
    echo "Fix the issues above, then run ./doctor.sh again."
    exit 1
fi
