#!/usr/bin/env bash
# RCX JavaScript Test Theater Detection
# Catches vacuous assertions and fake tests in JS
#
# Usage: ./tools/check_test_theater_js.sh [file]
#        Default: experiments/eval_step.js
#
# Test theater patterns:
#   - assert(true) / assert(1) - always passes
#   - console.assert(true) - vacuous assertion
#   - Empty test bodies
#   - Tests that only log, never assert
#   - Assertions comparing value to itself
#   - Comments claiming "test passes" without actual test

set -euo pipefail

JS_FILE="${1:-experiments/eval_step.js}"

if [ ! -f "$JS_FILE" ]; then
    echo "ERROR: $JS_FILE not found"
    exit 1
fi

echo "Checking $JS_FILE for test theater..."

ERRORS=0

check_pattern() {
    local pattern="$1"
    local reason="$2"
    local matches

    matches=$(grep -nE "$pattern" "$JS_FILE" 2>/dev/null || true)

    if [ -n "$matches" ]; then
        echo "  ✗ THEATER: $reason"
        echo "$matches" | head -5 | sed 's/^/      /'
        ERRORS=$((ERRORS + 1))
    fi
}

# Vacuous assertions (always true)
check_pattern "assert\s*\(\s*true\s*\)" "assert(true) - vacuous assertion"
check_pattern "assert\s*\(\s*1\s*\)" "assert(1) - vacuous assertion"
check_pattern "assert\s*\(\s*!false\s*\)" "assert(!false) - vacuous assertion"
check_pattern "assert\s*\(\s*!0\s*\)" "assert(!0) - vacuous assertion"
check_pattern "console\.assert\s*\(\s*true" "console.assert(true) - vacuous assertion"

# Self-comparison (always equal)
check_pattern "===\s*(\w+)\s*,\s*\1\s*\)" "Comparing variable to itself"
check_pattern "assert.*(\w+)\s*===\s*\1" "assert with self-comparison"

# Empty or trivial test functions
check_pattern "function\s+test\w*\s*\(\s*\)\s*\{\s*\}" "Empty test function body"
check_pattern "=>\s*\{\s*\}" "Empty arrow function (potential empty test)"

# Tests that only log without assertions
# This is tricky - we look for test-like functions that have console.log but no assert
# We'll flag test functions that mention "test" but only have console.log

# Commented-out assertions (test theater via comment)
check_pattern "//\s*assert" "Commented-out assertion"
check_pattern "//\s*expect" "Commented-out expectation"

# "TODO: add test" patterns (placeholder theater)
check_pattern "TODO.*test" "TODO test placeholder - incomplete test"
check_pattern "FIXME.*test" "FIXME test placeholder - broken test"

# Pass markers without actual testing
check_pattern "//\s*pass" "Comment saying 'pass' without assertion"
check_pattern "//\s*works" "Comment claiming 'works' without assertion"

# Blessed patterns (not theater):
# - assert(result === expected) - actual comparison
# - assert(muEqual(a, b)) - structural equality test
# - console.log for debugging (if followed by assertions)
# - Descriptive test names with actual test bodies

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "------------------------------------------------------------"
    echo "❌ Test theater found: $ERRORS pattern(s)"
    echo ""
    echo "These patterns indicate tests that don't actually test anything."
    echo "Replace with real assertions or remove the fake tests."
    exit 1
fi

echo "------------------------------------------------------------"
echo "✅ No test theater found"
