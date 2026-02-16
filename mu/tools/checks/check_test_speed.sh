#!/bin/bash
# RCX Speed Enforcer — Static Analysis for Unmarked Slow Tests
#
# Catches test files that import slow kernel functions but lack @pytest.mark.slow.
# These files leak into the CI green gate and bloat CI time.
#
# Slow function set (each takes >10s per call):
#   run_mu, run_mu_structural, run_algorithm_meta_circular,
#   run_engine_pipeline, run_hemisphere_routing
#
# A file is exempt if it contains ANY of:
#   - pytest.mark.slow (already marked)
#   - pytest.mark.fuzzer (auto-excluded from green gate)
#   - from hypothesis (auto-marked as fuzzer by conftest.py)
#   - # SPEED_OK: reason (explicit whitelist)
#
# Whitelist with: # SPEED_OK: reason
#
# Usage:
#   bash tools/check_test_speed.sh              # scan all tests/
#   bash tools/check_test_speed.sh tests/foo.py # scan specific file(s)

set -e

TESTS_DIR="${1:-./tests}"
EXIT_CODE=0
VIOLATIONS=0

echo "Scanning $TESTS_DIR for unmarked slow test files..."
echo ""

# Two-step detection for slow function imports (handles multiline imports):
# Step 1: File must have an import from the modules that contain slow functions
# Matches both rcx_pi.selfhost.step_mu and legacy rcx_pi.step_mu
SLOW_MODULE_IMPORT='from\s+rcx_pi\.(selfhost\.)?(step_mu|engine)\s+import'
# Step 2: File must mention a slow function name (on import line or in multiline block)
SLOW_FUNC_NAME='\b(run_mu_structural|run_algorithm_meta_circular|run_engine_pipeline|run_hemisphere_routing|run_mu)\b'

# Exempt patterns — any of these means the file is already handled
EXEMPT='pytest\.mark\.slow|pytest\.mark\.fuzzer|from hypothesis|# SPEED_OK'

# Files/dirs to skip
SKIP_PATTERN='tests/stress/|tests/conftest\.py|test_js_parity_automated\.py|tests/fuzz/|fuzzer_config\.py'

check_file() {
    local filepath="$1"

    # Skip non-test files
    case "$filepath" in
        *conftest.py|*fuzzer_config.py) return ;;
    esac

    # Skip stress/fuzz dirs
    if echo "$filepath" | grep -qE "$SKIP_PATTERN" 2>/dev/null; then
        return
    fi

    # Two-step check: file must import from a slow module AND mention a slow function
    # This handles both single-line and multiline imports without false positives
    if ! grep -qE "$SLOW_MODULE_IMPORT" "$filepath" 2>/dev/null; then
        return
    fi
    if ! grep -qE "$SLOW_FUNC_NAME" "$filepath" 2>/dev/null; then
        return
    fi

    # Check if file has an exemption
    if grep -qE "$EXEMPT" "$filepath" 2>/dev/null; then
        return
    fi

    # Extract which slow function(s) are imported
    local funcs
    funcs=$(grep -oE "$SLOW_FUNC_NAME" "$filepath" 2>/dev/null | sort -u | tr '\n' ', ' | sed 's/,$//')

    echo "  ✗ SPEED: $filepath imports $funcs but lacks @pytest.mark.slow"
    VIOLATIONS=$((VIOLATIONS + 1))
}

# If a specific file was passed, check just that file
if [ -f "$TESTS_DIR" ]; then
    check_file "$TESTS_DIR"
else
    # Scan all Python test files recursively
    while IFS= read -r filepath; do
        check_file "$filepath"
    done < <(find "$TESTS_DIR" -name "*.py" -type f 2>/dev/null | sort)
fi

echo ""

if [ $VIOLATIONS -gt 0 ]; then
    echo "------------------------------------------------------------"
    echo "❌ Speed violations found: $VIOLATIONS file(s)"
    echo ""
    echo "These test files call slow kernel functions (>10s) without"
    echo "@pytest.mark.slow, so they leak into the CI green gate."
    echo ""
    echo "Fix: Add to the file after imports:"
    echo "    pytestmark = [pytest.mark.slow]"
    echo ""
    echo "If the import exists but isn't actually called in tests:"
    echo "    # SPEED_OK: imported for type checking only"
    echo ""
    EXIT_CODE=1
else
    echo "✅ No speed violations found."
fi

exit $EXIT_CODE
