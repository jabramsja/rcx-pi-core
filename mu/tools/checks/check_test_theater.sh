#!/bin/bash
# RCX Python Test Theater Detection
# Catches vacuous assertions and fake tests
#
# Test theater patterns:
#   - assert True / assert 1 - always passes
#   - self.assertEqual(True, True) - tautology
#   - Empty test bodies (def test_foo(): pass)
#   - Commented-out assertions
#   - TODO/FIXME test placeholders
#   - @pytest.mark.skip without reason
#
# Whitelist with: # THEATER_OK: reason
#
# Philosophy: Tests should verify actual invariants, not just "it didn't crash."

set -e

TESTS_DIR="${1:-./tests}"
EXIT_CODE=0
ERRORS=0

echo "Scanning $TESTS_DIR for test theater..."
echo ""

check_pattern() {
    local pattern="$1"
    local reason="$2"
    local matches

    matches=$(grep -E -rn "$pattern" "$TESTS_DIR" --include="*.py" 2>/dev/null | grep -v "THEATER_OK" || true)

    if [ -n "$matches" ]; then
        echo "  ✗ THEATER: $reason"
        echo "$matches" | head -5 | sed 's/^/      /'
        echo ""
        ERRORS=$((ERRORS + 1))
    fi
}

# =============================================================================
# Vacuous assertions (always true)
# =============================================================================

# AST-based vacuous-assertion scan (replaces six TEXT greps that false-positived
# on vacuous patterns living inside string-literal test FIXTURES; see
# check-test-theater-ast-2026-06-03 / FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03).
# CLI CONTRACT: the linter scans "$TESTS_DIR" DIRECTLY (argv[1] = the dir to walk
# recursively); it must NOT treat argv[1] as a root that re-discovers tests/ +
# mu/tests/ below it (that would scan tests/tests, find nothing, and fail-open).
# set -e SAFE: the guarded `if` (equivalently `... && rc=0 || rc=$?`) stops a
# nonzero linter exit from fail-fasting the script before the branch runs. A bare
# `out=$(...); rc=$?` is FORBIDDEN: under set -e the failing command substitution
# exits the script and rc=$? / the branch never run.
if out=$(python3 "$(dirname "$0")/linters/check_test_theater.py" "$TESTS_DIR" 2>&1); then
    rc=0
else
    rc=$?
fi
if [ "$rc" -eq 0 ]; then
    :                                  # rc==0: scanned clean -> continue
elif [ "$rc" -eq 1 ]; then
    printf '%s\n' "$out"               # rc==1: real vacuous finding(s)
    ERRORS=$((ERRORS + 1))             # accumulate, continue
else
    printf '%s\n' "$out"               # rc>=2: EXECUTION FAILURE
    ERRORS=$((ERRORS + 1))             # FAIL CLOSED -- never treat as clean, continue
fi

# =============================================================================
# Self-comparison (always equal)
# =============================================================================
check_pattern "assert\s+(\w+)\s*==\s*\1\s*$" "assert x == x - self-comparison"

# =============================================================================
# Empty or trivial test bodies
# =============================================================================
# Single-line forms (grep-based)
check_pattern "def test_\w+\s*\([^)]*\)\s*:\s*pass\s*$" "Empty test body (pass)"
check_pattern "def test_\w+\s*\([^)]*\)\s*:\s*\.\.\.\s*$" "Empty test body (...)"

# F-07: Multiline empty test bodies (AST-based — catches standard two-line form)
# THEATER_OK on the def line or immediately preceding line whitelists the test.
_multiline_empty=$(python3 -c "
import ast, sys, os
tests_dir = sys.argv[1]
found = []
for root, dirs, files in os.walk(tests_dir):
    for fname in sorted(files):
        if not fname.endswith('.py'):
            continue
        path = os.path.join(root, fname)
        try:
            source = open(path).read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith('test_'):
                continue
            body = node.body
            # Skip leading docstring if present
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], 'value', None), ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            if len(body) != 1:
                continue
            stmt = body[0]
            is_empty = isinstance(stmt, ast.Pass)
            if not is_empty and isinstance(stmt, ast.Expr):
                val = getattr(stmt, 'value', None)
                if isinstance(val, ast.Constant) and val.value is ...:
                    is_empty = True
            if not is_empty:
                continue
            # Skip single-line forms (already caught by grep patterns above)
            if stmt.lineno == node.lineno:
                continue
            # THEATER_OK on def line or immediately preceding line
            def_idx = node.lineno - 1
            whitelisted = False
            for ci in range(max(0, def_idx - 1), min(len(lines), def_idx + 1)):
                if 'THEATER_OK' in lines[ci]:
                    whitelisted = True
                    break
            if whitelisted:
                continue
            found.append(f'{path}:{node.lineno}')
for f in found:
    print(f)
" "$TESTS_DIR" 2>/dev/null || true)

if [ -n "$_multiline_empty" ]; then
    echo "  ✗ THEATER: Empty test body (multiline def/pass)"
    echo "$_multiline_empty" | head -5 | sed 's/^/      /'
    echo ""
    ERRORS=$((ERRORS + 1))
fi

# =============================================================================
# Skip without reason (hiding broken tests)
# =============================================================================
check_pattern "@pytest\.mark\.skip\s*$" "@pytest.mark.skip without reason"
check_pattern "@pytest\.mark\.skip\s*\(\s*\)" "@pytest.mark.skip() without reason"
check_pattern "@unittest\.skip\s*$" "@unittest.skip without reason"

# =============================================================================
# Commented-out assertions (test theater via comment)
# =============================================================================
check_pattern "^\s*#\s*assert\s" "Commented-out assertion"
check_pattern "^\s*#\s*self\.assert" "Commented-out self.assert"

# =============================================================================
# TODO/FIXME placeholders (incomplete tests)
# =============================================================================
check_pattern "def test_.*#\s*TODO" "TODO in test definition - incomplete"
check_pattern "def test_.*#\s*FIXME" "FIXME in test definition - broken"

# =============================================================================
# Summary
# =============================================================================
if [ $ERRORS -gt 0 ]; then
    echo "------------------------------------------------------------"
    echo "❌ Test theater found: $ERRORS pattern(s)"
    echo ""
    echo "These patterns indicate tests that don't actually test anything."
    echo "Fix: Replace with meaningful assertions that verify actual invariants."
    echo ""
    echo "If truly unavoidable, add: # THEATER_OK: reason"
    EXIT_CODE=1
else
    echo "✅ No test theater found."
fi

echo ""
exit $EXIT_CODE
