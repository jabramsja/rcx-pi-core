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
# Canonical bootstrap primitive named set (single source of truth)
JS_PRIMITIVE_SET_FILE="tools/checks/bootstrap_primitive_set.json"

count_marker() {
    local pattern="$1"
    local count
    count=$(grep -rE "$pattern" "$JS_DIR" --include='*.js' 2>/dev/null | wc -l | tr -d '[:space:]')
    echo "${count:-0}"
}

extract_bootstrap_primitive_names() {
    # Extract unique primitive names from BOOTSTRAP_PRIMITIVE: <name> markers.
    # Returns sorted unique set (one name per line).
    grep -roE 'BOOTSTRAP_PRIMITIVE:[[:space:]]*[a-zA-Z_]+' "$JS_DIR" --include='*.js' 2>/dev/null \
        | sed 's/.*BOOTSTRAP_PRIMITIVE:[[:space:]]*//' \
        | sort -u
}

load_expected_primitive_set() {
    local set_file="$1"
    python3 - "$set_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print(f"ERROR: primitive set file not found: {path}", file=sys.stderr)
    sys.exit(2)

try:
    data = json.loads(path.read_text())
except Exception as exc:
    print(f"ERROR: failed to parse primitive set file: {exc}", file=sys.stderr)
    sys.exit(2)

if data.get("schema_version") != 1:
    print(
        f"ERROR: primitive set schema_version must be 1, got {data.get('schema_version')}",
        file=sys.stderr,
    )
    sys.exit(2)

vals = data.get("expected_named_set")
if not isinstance(vals, list) or not vals:
    print("ERROR: expected_named_set must be non-empty list", file=sys.stderr)
    sys.exit(2)
if not all(isinstance(v, str) and v.strip() for v in vals):
    print("ERROR: expected_named_set entries must be non-empty strings", file=sys.stderr)
    sys.exit(2)
if len(vals) != len(set(vals)):
    print("ERROR: expected_named_set contains duplicates", file=sys.stderr)
    sys.exit(2)

print(" ".join(sorted(vals)))
PY
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
if [ ! -f "$JS_PRIMITIVE_SET_FILE" ]; then
    echo "ERROR: $JS_PRIMITIVE_SET_FILE not found (canonical primitive set required)"
    exit 1
fi

# Count debt markers across all JS module files
HOST_ITERATION=$(count_marker "@host_iteration")
HOST_RECURSION=$(count_marker "@host_recursion")
HOST_BUILTIN=$(count_marker "@host_builtin")
BOOTSTRAP_PRIMITIVE_RAW=$(count_marker "BOOTSTRAP_PRIMITIVE")
BOOTSTRAP_PRIMITIVE_NAMES=$(extract_bootstrap_primitive_names)
BOOTSTRAP_PRIMITIVE_COUNT=$(echo "$BOOTSTRAP_PRIMITIVE_NAMES" | grep -c . 2>/dev/null || echo 0)
BOOTSTRAP_PRIMITIVE_SET=$(echo "$BOOTSTRAP_PRIMITIVE_NAMES" | tr '\n' ', ' | sed 's/,$//' | sed 's/,/, /g')
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
echo "  BOOTSTRAP_PRIMITIVE (named set): $BOOTSTRAP_PRIMITIVE_COUNT  ($BOOTSTRAP_PRIMITIVE_SET)"
echo "  BOOTSTRAP_PRIMITIVE (raw tokens): $BOOTSTRAP_PRIMITIVE_RAW  (diagnostic — includes prose mentions)"
echo "  AST_OK_JS:          $AST_OK_TOTAL_JS  (3 is current baseline; infra boundary markers for types.js and pipeline.js)"
echo "  host_runtime_loc_js: $HOST_RUNTIME_LOC_JS"
echo "  host_test_loc_js:    $HOST_TEST_LOC_JS"
echo ""

# Extract expected counts from DEBT SUMMARY header in core/constants.js
# Header uses "iteration debt: N" format (plain text, avoids ratchet scanner inflation)
EXPECTED_ITERATION=$(grep -o 'iteration debt: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f3)
EXPECTED_RECURSION=$(grep -o 'recursion debt: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f3)
EXPECTED_BUILTIN=$(grep -o 'builtin debt: [0-9]*' "$JS_HEADER_FILE" | head -1 | cut -d' ' -f3)
EXPECTED_BOOTSTRAP=$(grep -o 'BOOTSTRAP PRIMITIVES ([0-9]*' "$JS_HEADER_FILE" | head -1 | grep -o '[0-9]*')
EXPECTED_PRIMITIVE_SET=$(load_expected_primitive_set "$JS_PRIMITIVE_SET_FILE")

# Validate we extracted the counts (fail if header is missing/malformed)
if [ -z "$EXPECTED_ITERATION" ] || [ -z "$EXPECTED_RECURSION" ] || [ -z "$EXPECTED_BUILTIN" ] || [ -z "$EXPECTED_BOOTSTRAP" ]; then
    echo "ERROR: Could not extract expected counts from DEBT SUMMARY header in $JS_HEADER_FILE"
    echo "  EXPECTED_ITERATION: ${EXPECTED_ITERATION:-MISSING}"
    echo "  EXPECTED_RECURSION: ${EXPECTED_RECURSION:-MISSING}"
    echo "  EXPECTED_BUILTIN: ${EXPECTED_BUILTIN:-MISSING}"
    echo "  EXPECTED_BOOTSTRAP: ${EXPECTED_BOOTSTRAP:-MISSING}"
    exit 1
fi
if [ -z "$EXPECTED_PRIMITIVE_SET" ]; then
    echo "ERROR: Expected primitive named set resolved empty from $JS_PRIMITIVE_SET_FILE"
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

# Bootstrap primitive gate: pass/fail on exact named set (raw count is diagnostic only)
ACTUAL_PRIMITIVE_SET=$(echo "$BOOTSTRAP_PRIMITIVE_NAMES" | tr '\n' ' ' | sed 's/ $//')
if [ "$ACTUAL_PRIMITIVE_SET" != "$EXPECTED_PRIMITIVE_SET" ]; then
    echo "ERROR: BOOTSTRAP_PRIMITIVE named set mismatch"
    echo "  Expected: {$EXPECTED_PRIMITIVE_SET}"
    echo "  Actual:   {$ACTUAL_PRIMITIVE_SET}"
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
# run/runStructural/runAlgorithmWithBridge/runEnginePipelineRecursive
# reclassified as BOUNDARY (outer loop scaffolding, off kernel path) — P7W5
check_function_marker "run" "BOUNDARY"
check_function_marker "runStructural" "BOUNDARY"
# listToLinked is on kernel path (called by step/stepKernel) — stays @host_iteration
check_function_marker "listToLinked" "@host_iteration"
check_function_marker "runAlgorithmWithBridge" "BOUNDARY"
check_function_marker "runEnginePipelineRecursive" "BOUNDARY"
# collectOntologyEvidence reclassified as boundary (off kernel path) — P7 Wave 3
# runEnginePipeline reclassified as BOUNDARY (off kernel path — orchestrator) — P7W4
# match/substitute reclassified as BOUNDARY (off kernel path since Wave H) — P7W4
check_function_marker "stage0Match" "@host_recursion"
check_function_marker "stage0Substitute" "@host_recursion"
# normalize/denormalize reclassified as BOUNDARY (off kernel path) — P7W4
# muEqual demoted to test-only (P7 Wave 2) — no longer tracked as @host_builtin
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
