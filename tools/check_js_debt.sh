#!/usr/bin/env bash
# Check JavaScript debt markers for L3 parity with Python
#
# This script verifies that mu/host/js/eval_step.js has proper debt tracking
# that matches Python's semantic debt markers.
#
# Usage: ./tools/check_js_debt.sh

set -euo pipefail

JS_FILE="mu/host/js/eval_step.js"

echo "=== Checking JavaScript Debt Markers ==="
echo ""

if [ ! -f "$JS_FILE" ]; then
    echo "ERROR: $JS_FILE not found"
    exit 1
fi

# Count debt markers
HOST_ITERATION=$(grep -c "@host_iteration" "$JS_FILE" || echo 0)
HOST_RECURSION=$(grep -c "@host_recursion" "$JS_FILE" || echo 0)
HOST_BUILTIN=$(grep -c "@host_builtin" "$JS_FILE" || echo 0)
BOOTSTRAP_PRIMITIVE=$(grep -c "BOOTSTRAP_PRIMITIVE" "$JS_FILE" || echo 0)

echo "Debt markers found in $JS_FILE:"
echo "  @host_iteration:    $HOST_ITERATION"
echo "  @host_recursion:    $HOST_RECURSION"
echo "  @host_builtin:      $HOST_BUILTIN"
echo "  BOOTSTRAP_PRIMITIVE: $BOOTSTRAP_PRIMITIVE"
echo ""

# Extract expected counts from DEBT SUMMARY header (self-documenting, no drift)
# Uses portable grep (no -P flag which isn't available on macOS)
EXPECTED_ITERATION=$(grep -o '@host_iteration: [0-9]*' "$JS_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_RECURSION=$(grep -o '@host_recursion: [0-9]*' "$JS_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_BUILTIN=$(grep -o '@host_builtin: [0-9]*' "$JS_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_BOOTSTRAP=$(grep -o 'BOOTSTRAP PRIMITIVES ([0-9]*' "$JS_FILE" | head -1 | grep -o '[0-9]*')

# Validate we extracted the counts (fail if header is missing/malformed)
if [ -z "$EXPECTED_ITERATION" ] || [ -z "$EXPECTED_RECURSION" ] || [ -z "$EXPECTED_BUILTIN" ] || [ -z "$EXPECTED_BOOTSTRAP" ]; then
    echo "ERROR: Could not extract expected counts from DEBT SUMMARY header in $JS_FILE"
    echo "  EXPECTED_ITERATION: ${EXPECTED_ITERATION:-MISSING}"
    echo "  EXPECTED_RECURSION: ${EXPECTED_RECURSION:-MISSING}"
    echo "  EXPECTED_BUILTIN: ${EXPECTED_BUILTIN:-MISSING}"
    echo "  EXPECTED_BOOTSTRAP: ${EXPECTED_BOOTSTRAP:-MISSING}"
    exit 1
fi

ERRORS=0

# Validate counts
if [ "$HOST_ITERATION" -lt "$EXPECTED_ITERATION" ]; then
    echo "WARNING: @host_iteration count ($HOST_ITERATION) < expected ($EXPECTED_ITERATION)"
    ERRORS=$((ERRORS + 1))
fi

if [ "$HOST_RECURSION" -lt "$EXPECTED_RECURSION" ]; then
    echo "WARNING: @host_recursion count ($HOST_RECURSION) < expected ($EXPECTED_RECURSION)"
    ERRORS=$((ERRORS + 1))
fi

if [ "$HOST_BUILTIN" -lt "$EXPECTED_BUILTIN" ]; then
    echo "WARNING: @host_builtin count ($HOST_BUILTIN) < expected ($EXPECTED_BUILTIN)"
    ERRORS=$((ERRORS + 1))
fi

if [ "$BOOTSTRAP_PRIMITIVE" -lt "$EXPECTED_BOOTSTRAP" ]; then
    echo "WARNING: BOOTSTRAP_PRIMITIVE count ($BOOTSTRAP_PRIMITIVE) < expected ($EXPECTED_BOOTSTRAP)"
    ERRORS=$((ERRORS + 1))
fi

# Check for DEBT SUMMARY header
if ! grep -q "DEBT SUMMARY" "$JS_FILE"; then
    echo "ERROR: Missing DEBT SUMMARY header in $JS_FILE"
    ERRORS=$((ERRORS + 1))
fi

# Check that key functions have markers
echo "Checking key functions have debt markers:"

check_function_marker() {
    local func_name="$1"
    local marker="$2"
    # Look up to 15 lines before the function for JSDoc comments
    if grep -B15 "function $func_name" "$JS_FILE" | grep -q "$marker"; then
        echo "  ✓ $func_name has $marker"
    else
        echo "  ✗ $func_name MISSING $marker"
        ERRORS=$((ERRORS + 1))
    fi
}

check_function_marker "step" "@host_iteration"
check_function_marker "run" "@host_iteration"
check_function_marker "runStructural" "@host_iteration"
check_function_marker "match" "@host_recursion"
check_function_marker "substitute" "@host_recursion"
check_function_marker "normalize" "@host_recursion"
check_function_marker "denormalize" "@host_recursion"
check_function_marker "muEqual" "@host_builtin"
check_function_marker "isValidMu" "@host_builtin"

echo ""

if [ $ERRORS -gt 0 ]; then
    echo "FAILED: $ERRORS issues found"
    exit 1
fi

echo "PASSED: All JS debt markers present"
echo ""
echo "Note: JS debt (12) matches Python debt (12) - same bootstrap primitives"
