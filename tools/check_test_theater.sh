#!/bin/bash
# Check for "assert True" theater in tests - vacuous assertions that verify nothing.
#
# This catches patterns like:
#   assert True      # Theater - verifies nothing
#
# This allows:
#   assert True == 1 # Legitimate - tests Python type coercion
#   # THEATER_OK: reason   # Whitelisted
#
# Philosophy: Tests should verify actual invariants, not just "it didn't crash."

set -e

TESTS_DIR="${1:-./tests}"
EXIT_CODE=0

echo "Scanning $TESTS_DIR for test theater..."
echo ""

# Find "assert True" that is:
# - Not followed by "==" (which tests type coercion)
# - Not whitelisted with THEATER_OK
# Pattern: "assert True" followed by optional comment or end of line
# Note: -E for extended regex (needed for \s and |)
THEATER_HITS=$(grep -E -rn "assert True\s*$|assert True\s*#" "$TESTS_DIR" --include="*.py" 2>/dev/null | grep -v "THEATER_OK" | grep -v "assert True ==" || true)

if [ -n "$THEATER_HITS" ]; then
    echo "TEST THEATER DETECTED: Found vacuous 'assert True':"
    echo ""
    echo "$THEATER_HITS"
    echo ""
    echo "Fix: Replace with meaningful assertions that verify actual invariants."
    echo "Example: assert result is not None or isinstance(result, (int, str, dict, list))"
    echo ""
    echo "If truly unavoidable, add: # THEATER_OK: reason"
    EXIT_CODE=1
else
    echo "No test theater found."
fi

echo ""
exit $EXIT_CODE
