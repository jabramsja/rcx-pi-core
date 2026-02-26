#!/usr/bin/env bash
# Check JavaScript debt markers for L3 parity with Python
#
# This script verifies that mu/host/js/ modules have proper debt tracking
# that matches Python's semantic debt markers.
#
# Usage: ./tools/check_js_debt.sh

set -euo pipefail

# Resolve to repo root so relative paths are stable from any cwd.
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

JS_DIR="mu/host/js"
# The DEBT SUMMARY header lives in core/constants.js
JS_HEADER_FILE="$JS_DIR/core/constants.js"

count_marker() {
    local pattern="$1"
    local count
    count=$(grep -rE "$pattern" "$JS_DIR" --include='*.js' 2>/dev/null | wc -l | tr -d '[:space:]')
    echo "${count:-0}"
}

count_loc() {
    local mode="$1"
    local count=0
    local file
    local lines
    if [ "$mode" = "runtime" ]; then
        while IFS= read -r -d '' file; do
            lines=$(wc -l < "$file" | tr -d '[:space:]')
            count=$((count + lines))
        done < <(find "$JS_DIR" -type f -name '*.js' ! -path "$JS_DIR/tests/*" -print0)
    else
        while IFS= read -r -d '' file; do
            lines=$(wc -l < "$file" | tr -d '[:space:]')
            count=$((count + lines))
        done < <(find "$JS_DIR/tests" -type f -name '*.js' -print0 2>/dev/null || true)
    fi
    echo "$count"
}

echo "=== Checking JavaScript Debt Markers ==="
echo ""

if [ ! -d "$JS_DIR" ]; then
    echo "ERROR: $JS_DIR not found"
    exit 1
fi

if [ ! -f "$JS_HEADER_FILE" ]; then
    echo "ERROR: $JS_HEADER_FILE not found (DEBT SUMMARY header expected here)"
    exit 1
fi

# Count debt markers across all JS module files
HOST_ITERATION=$(count_marker "@host_iteration")
HOST_RECURSION=$(count_marker "@host_recursion")
HOST_BUILTIN=$(count_marker "@host_builtin")
BOOTSTRAP_PRIMITIVE=$(count_marker "BOOTSTRAP_PRIMITIVE")
AST_OK_TOTAL_JS=$(count_marker "AST_OK_JS:")
HOST_RUNTIME_LOC_JS=$(count_loc "runtime")
HOST_TEST_LOC_JS=$(count_loc "tests")

if [ "$HOST_RUNTIME_LOC_JS" -eq 0 ]; then
    echo "ERROR: JS runtime LOC resolved to 0 (path/glob failure for $JS_DIR runtime files)"
    exit 1
fi

echo "Debt markers found across $JS_DIR/**/*.js:"
echo "  @host_iteration:    $HOST_ITERATION"
echo "  @host_recursion:    $HOST_RECURSION"
echo "  @host_builtin:      $HOST_BUILTIN"
echo "  BOOTSTRAP_PRIMITIVE: $BOOTSTRAP_PRIMITIVE"
echo "  AST_OK_JS:          $AST_OK_TOTAL_JS  (0 is expected baseline; no AST_OK_JS markers yet)"
echo "  host_runtime_loc_js: $HOST_RUNTIME_LOC_JS"
echo "  host_test_loc_js:    $HOST_TEST_LOC_JS"
echo ""

# Extract expected counts from DEBT SUMMARY header in core/constants.js
EXPECTED_ITERATION=$(grep -o '@host_iteration: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_RECURSION=$(grep -o '@host_recursion: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_BUILTIN=$(grep -o '@host_builtin: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f2)
EXPECTED_BOOTSTRAP=$(grep -o 'BOOTSTRAP PRIMITIVES ([0-9]*' "$JS_HEADER_FILE" | head -1 | grep -o '[0-9]*')

# Validate we extracted the counts (fail if header is missing/malformed)
if [ -z "$EXPECTED_ITERATION" ] || [ -z "$EXPECTED_RECURSION" ] || [ -z "$EXPECTED_BUILTIN" ] || [ -z "$EXPECTED_BOOTSTRAP" ]; then
    echo "ERROR: Could not extract expected counts from DEBT SUMMARY header in $JS_HEADER_FILE"
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
if ! grep -q "DEBT SUMMARY" "$JS_HEADER_FILE"; then
    echo "ERROR: Missing DEBT SUMMARY header in $JS_HEADER_FILE"
    ERRORS=$((ERRORS + 1))
fi

# Check that key functions have debt markers (scan across all modules)
echo "Checking key functions have debt markers:"

check_function_marker() {
    local func_name="$1"
    local marker="$2"
    # Search all JS files for the function with its marker within 15 lines above
    # Use "function name(" to avoid prefix matches (e.g., "run" matching "runStructural")
    if grep -rB15 "function ${func_name}(" "$JS_DIR" --include='*.js' | grep -q "$marker"; then
        echo "  ✓ $func_name has $marker"
    else
        echo "  ✗ $func_name MISSING $marker"
        ERRORS=$((ERRORS + 1))
    fi
}

check_function_marker "step" "@host_iteration"
check_function_marker "run" "@host_iteration"
check_function_marker "runStructural" "@host_iteration"
check_function_marker "runAlgorithmWithBridge" "@host_iteration"
check_function_marker "runEnginePipeline" "@host_iteration"
check_function_marker "runEnginePipelineRecursive" "@host_iteration"
check_function_marker "match" "@host_recursion"
check_function_marker "substitute" "@host_recursion"
check_function_marker "normalize" "@host_recursion"
check_function_marker "denormalize" "@host_recursion"
check_function_marker "muEqual" "@host_builtin"
check_function_marker "muHash" "@host_builtin"
check_function_marker "isValidMu" "@host_builtin"

echo ""

if [ $ERRORS -gt 0 ]; then
    echo "FAILED: $ERRORS issues found"
    exit 1
fi

echo "PASSED: All JS debt markers present"
echo ""
TOTAL=$((HOST_ITERATION + HOST_RECURSION + HOST_BUILTIN))
echo "Note: JS debt ($TOTAL) = $HOST_ITERATION iteration + $HOST_RECURSION recursion + $HOST_BUILTIN builtin"
