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

# assert True (not followed by ==, which tests coercion)
check_pattern "assert True\s*$|assert True\s*#" "assert True - vacuous assertion"

# assert 1 / assert "string" / assert [] is falsy but assert [1] is truthy
check_pattern "^\s*assert 1\s*$|^\s*assert 1\s*#" "assert 1 - vacuous assertion"

# assertTrue(True) / assertEqual(True, True)
check_pattern "assertTrue\s*\(\s*True\s*\)" "assertTrue(True) - tautology"
check_pattern "assertEqual\s*\(\s*True\s*,\s*True\s*\)" "assertEqual(True, True) - tautology"
check_pattern "assertEqual\s*\(\s*1\s*,\s*1\s*\)" "assertEqual(1, 1) - tautology"
check_pattern "assertEqual\s*\(\s*0\s*,\s*0\s*\)" "assertEqual(0, 0) - tautology"

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
