#!/usr/bin/env bash
# Check that STATUS.md matches actual project state
# Run this to catch doc drift

set -e

cd "$(dirname "$0")/.."

echo "=== Checking docs consistency ==="

ERRORS=0

# 1. Check debt count in STATUS.md matches debt_dashboard.sh
echo ""
echo "1. Checking debt count..."

STATUS_DEBT=$(grep -E "^CURRENT:" STATUS.md | grep -oE '[0-9]+' | head -1)
ACTUAL_DEBT=$(./tools/debt_dashboard.sh 2>/dev/null | grep -E "Total Semantic:" | grep -oE '[0-9]+' | head -1)

if [ -z "$STATUS_DEBT" ]; then
    echo "   WARNING: Could not parse debt from STATUS.md"
    ERRORS=$((ERRORS + 1))
elif [ -z "$ACTUAL_DEBT" ]; then
    echo "   WARNING: Could not get actual debt from debt_dashboard.sh"
elif [ "$STATUS_DEBT" != "$ACTUAL_DEBT" ]; then
    echo "   MISMATCH: STATUS.md says $STATUS_DEBT, actual is $ACTUAL_DEBT"
    echo "   → Update STATUS.md debt count"
    ERRORS=$((ERRORS + 1))
else
    echo "   OK: Debt count matches ($STATUS_DEBT)"
fi

# 2. Check STATUS.md was updated recently (within last 7 days)
echo ""
echo "2. Checking STATUS.md freshness..."

STATUS_DATE=$(grep -E "^\\*\\*Last updated:" STATUS.md | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
if [ -n "$STATUS_DATE" ]; then
    STATUS_EPOCH=$(date -j -f "%Y-%m-%d" "$STATUS_DATE" "+%s" 2>/dev/null || date -d "$STATUS_DATE" "+%s" 2>/dev/null)
    NOW_EPOCH=$(date "+%s")
    DAYS_OLD=$(( (NOW_EPOCH - STATUS_EPOCH) / 86400 ))

    if [ "$DAYS_OLD" -gt 7 ]; then
        echo "   WARNING: STATUS.md last updated $DAYS_OLD days ago ($STATUS_DATE)"
        echo "   → Consider reviewing if it's still accurate"
    else
        echo "   OK: STATUS.md updated $DAYS_OLD days ago ($STATUS_DATE)"
    fi
else
    echo "   WARNING: Could not parse last updated date from STATUS.md"
fi

# 3. Check that key files referenced in STATUS.md exist
echo ""
echo "3. Checking referenced files exist..."

MISSING=0
for file in "docs/core/MetaCircularKernel.v0.md" "rcx_pi/selfhost/match_mu.py" "seeds/match.v1.json"; do
    if [ ! -f "$file" ]; then
        echo "   MISSING: $file (referenced in STATUS.md)"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -eq 0 ]; then
    echo "   OK: All referenced files exist"
else
    ERRORS=$((ERRORS + MISSING))
fi

# 4. Check TASKS.md has expected sections
echo ""
echo "4. Checking TASKS.md structure..."

for section in "## North Star" "## Ra" "## NEXT" "## VECTOR"; do
    if ! grep -q "$section" TASKS.md; then
        echo "   MISSING: $section section in TASKS.md"
        ERRORS=$((ERRORS + 1))
    fi
done
echo "   OK: TASKS.md has expected sections"

# Summary
echo ""
echo "=== Summary ==="
if [ "$ERRORS" -eq 0 ]; then
    echo "All checks passed. Docs are consistent."
    exit 0
else
    echo "$ERRORS issue(s) found. Please review and update docs."
    exit 1
fi
