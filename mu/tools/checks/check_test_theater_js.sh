#!/usr/bin/env bash
# RCX JavaScript Test Theater Detection
# Catches vacuous assertions and fake tests in JS
#
# Usage: ./tools/checks/check_test_theater_js.sh [file_or_dir]
#        Default: mu/host/js/ (scans all *.js recursively)
#        Single file: ./tools/checks/check_test_theater_js.sh path/to/file.js
#
# Marker: THEATER_OK on the same line suppresses that match.
#
# Test theater patterns:
#   - assert(true) / assert(1) - always passes
#   - console.assert(true) - vacuous assertion
#   - Empty test bodies
#   - Tests that only log, never assert
#   - Assertions comparing value to itself
#   - Comments claiming "test passes" without actual test

set -euo pipefail

TARGET="${1:-mu/host/js/}"
JS_FILES=()

if [ -d "$TARGET" ]; then
    while IFS= read -r f; do
        JS_FILES+=("$f")
    done < <(find "$TARGET" -name '*.js' -not -path '*/node_modules/*' | sort)
elif [ -f "$TARGET" ]; then
    JS_FILES=("$TARGET")
else
    echo "ERROR: $TARGET not found (not a file or directory)"
    exit 1
fi

FILE_COUNT=${#JS_FILES[@]}
if [ "$FILE_COUNT" -eq 0 ]; then
    echo "ERROR: No .js files found in $TARGET"
    exit 1
fi

echo "Checking $FILE_COUNT JS file(s) under $TARGET for test theater..."

ERRORS=0

# check_pattern: detect theater in executable code (filters out comment lines)
check_pattern() {
    local pattern="$1"
    local reason="$2"

    local all_matches
    all_matches=$(grep -HnE "$pattern" "${JS_FILES[@]}" 2>/dev/null \
        | grep -v ':[0-9]*:\s*//' \
        | grep -v ':[0-9]*:\s*\*' \
        | grep -v ':[0-9]*:\s*/\*' \
        | grep -v 'THEATER_OK' \
        || true)

    if [ -z "$all_matches" ]; then
        return
    fi

    local prev_file=""
    local file_lines=0
    while IFS= read -r line; do
        local file="${line%%:*}"
        if [ "$file" != "$prev_file" ]; then
            prev_file="$file"
            file_lines=0
            echo "  ✗ THEATER in $file: $reason"
            ERRORS=$((ERRORS + 1))
        fi
        file_lines=$((file_lines + 1))
        if [ "$file_lines" -le 5 ]; then
            local rest="${line#*:}"
            echo "      $rest"
        fi
    done <<< "$all_matches"
}

# check_comment_pattern: detect theater that IS in comments (no comment filter)
check_comment_pattern() {
    local pattern="$1"
    local reason="$2"

    local all_matches
    all_matches=$(grep -HnE "$pattern" "${JS_FILES[@]}" 2>/dev/null \
        | grep -v 'THEATER_OK' \
        || true)

    if [ -z "$all_matches" ]; then
        return
    fi

    local prev_file=""
    local file_lines=0
    while IFS= read -r line; do
        local file="${line%%:*}"
        if [ "$file" != "$prev_file" ]; then
            prev_file="$file"
            file_lines=0
            echo "  ✗ THEATER in $file: $reason"
            ERRORS=$((ERRORS + 1))
        fi
        file_lines=$((file_lines + 1))
        if [ "$file_lines" -le 5 ]; then
            local rest="${line#*:}"
            echo "      $rest"
        fi
    done <<< "$all_matches"
}

# Vacuous assertions (always true) — in executable code
check_pattern "assert\s*\(\s*true\s*\)" "assert(true) - vacuous assertion"
check_pattern "assert\s*\(\s*1\s*\)" "assert(1) - vacuous assertion"
check_pattern "assert\s*\(\s*!false\s*\)" "assert(!false) - vacuous assertion"
check_pattern "assert\s*\(\s*!0\s*\)" "assert(!0) - vacuous assertion"
check_pattern "console\.assert\s*\(\s*true" "console.assert(true) - vacuous assertion"

# Self-comparison (always equal) — in executable code
check_pattern "===\s*(\w+)\s*,\s*\1\s*\)" "Comparing variable to itself"
check_pattern "assert.*(\w+)\s*===\s*\1" "assert with self-comparison"

# Empty or trivial test functions — in executable code
check_pattern "function\s+test\w*\s*\(\s*\)\s*\{\s*\}" "Empty test function body"
check_pattern "=>\s*\{\s*\}" "Empty arrow function (potential empty test)"

# Commented-out assertions — theater IS the comment, so no comment filter
check_comment_pattern "//\s*assert" "Commented-out assertion"
check_comment_pattern "//\s*expect" "Commented-out expectation"

# "TODO: add test" patterns — theater IS the comment
check_comment_pattern "TODO.*test" "TODO test placeholder - incomplete test"
check_comment_pattern "FIXME.*test" "FIXME test placeholder - broken test"

# Pass markers without actual testing — theater IS the comment
check_comment_pattern "//\s*pass" "Comment saying 'pass' without assertion"
check_comment_pattern "//\s*works" "Comment claiming 'works' without assertion"

# Blessed patterns (not theater):
# - assert(result === expected) - actual comparison
# - assert(muEqual(a, b)) - structural equality test
# - console.log for debugging (if followed by assertions)
# - Descriptive test names with actual test bodies

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "------------------------------------------------------------"
    echo "❌ Test theater found: $ERRORS pattern(s) in $FILE_COUNT file(s)"
    echo ""
    echo "These patterns indicate tests that don't actually test anything."
    echo "Replace with real assertions or remove the fake tests."
    echo "Mark intentional exceptions with // THEATER_OK: <reason> on the same line."
    exit 1
fi

echo "------------------------------------------------------------"
echo "✅ No test theater found in $FILE_COUNT file(s)"
