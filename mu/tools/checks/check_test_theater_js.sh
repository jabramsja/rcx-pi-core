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

# _strip_block_comments: remove /* ... */ content from a JS file.
# Preserves line count, line comments (//), string literals, and regex literals.
# Tracks ", ', ` for strings and /.../ for regex (with [..] char-class and
# \-escape handling) so that "/*" or /[/*]/ are not misinterpreted as
# block-comment starts.
# Known limitation: template-literal ${} nesting with backticks or comment
# tokens may confuse the parser.  Acceptable for linting scope.
_strip_block_comments() {
    awk '
    BEGIN {
        in_bc = 0; in_str = 0; str_delim = ""
        SQ = sprintf("%c", 39)
    }
    # Determine if / at the current position starts a regex literal.
    # Scans backwards through s for the last non-whitespace token:
    #   operator/paren -> regex context  (includes ) for control-flow)
    #   JS keyword     -> regex context
    #   identifier/]   -> division context
    #   empty/SOL      -> regex context
    # Note: ) is regex-context because if/while/for close-parens precede
    # regex literals.  This is safe: /* detection runs before is_regex_ctx
    # so foo()/* still enters block-comment mode.  The only effect is that
    # foo()/expr may briefly enter regex scan, but content is preserved.
    function is_regex_ctx(s,    i, ch, w) {
        w = ""
        for (i = length(s); i > 0; i--) {
            ch = substr(s, i, 1)
            if (ch == " " || ch == "\t") { if (w != "") break; continue }
            if (w == "" && index("=([{,;!&|^~+-*%<>?:)", ch) > 0) return 1
            if (ch ~ /[a-zA-Z_$0-9]/) { w = ch w }
            else { if (w != "") break; return 0 }
        }
        if (w == "return" || w == "typeof" || w == "instanceof" || \
            w == "throw" || w == "case" || w == "void" || \
            w == "delete" || w == "new" || w == "in" || \
            w == "yield" || w == "await" || w == "else" || w == "do") return 1
        if (w == "") return 1
        return 0
    }
    {
        line = $0; out = ""
        while (length(line) > 0) {
            if (in_bc) {
                idx = index(line, "*/")
                if (idx > 0) { in_bc = 0; line = substr(line, idx + 2) }
                else         { line = "" }
            } else if (in_str) {
                esc = index(line, "\\")
                cp  = index(line, str_delim)
                if (cp == 0) {
                    out = out line; line = ""
                } else if (esc > 0 && esc < cp) {
                    out = out substr(line, 1, esc + 1)
                    line = substr(line, esc + 2)
                } else {
                    out = out substr(line, 1, cp)
                    line = substr(line, cp + 1)
                    in_str = 0
                }
            } else {
                # Find earliest significant token: /, ", SQ, `
                idx_sl = index(line, "/")
                idx_dq = index(line, "\"")
                idx_sq = index(line, SQ)
                idx_bt = index(line, "`")

                mp = 0; mt = ""
                if (idx_sl > 0 && (mp == 0 || idx_sl < mp)) { mp = idx_sl; mt = "sl" }
                if (idx_dq > 0 && (mp == 0 || idx_dq < mp)) { mp = idx_dq; mt = "dq" }
                if (idx_sq > 0 && (mp == 0 || idx_sq < mp)) { mp = idx_sq; mt = "sq" }
                if (idx_bt > 0 && (mp == 0 || idx_bt < mp)) { mp = idx_bt; mt = "bt" }

                if (mt == "") {
                    out = out line; line = ""
                } else if (mt == "sl") {
                    nxt = substr(line, mp + 1, 1)
                    if (nxt == "/") {
                        # Line comment //: keep rest of line as-is
                        out = out line; line = ""
                    } else if (nxt == "*") {
                        # /* is always a block comment (* cannot start regex body)
                        out = out substr(line, 1, mp - 1)
                        line = substr(line, mp + 2)
                        in_bc = 1
                    } else if (is_regex_ctx(out substr(line, 1, mp - 1))) {
                        # Regex literal: emit opening / then scan body
                        out = out substr(line, 1, mp)
                        line = substr(line, mp + 1)
                        in_rc = 0
                        while (length(line) > 0) {
                            c1 = substr(line, 1, 1)
                            if (c1 == "\\" && length(line) >= 2) {
                                out = out substr(line, 1, 2)
                                line = substr(line, 3)
                            } else if (in_rc) {
                                if (c1 == "]") in_rc = 0
                                out = out c1; line = substr(line, 2)
                            } else if (c1 == "[") {
                                in_rc = 1
                                out = out c1; line = substr(line, 2)
                            } else if (c1 == "/") {
                                out = out c1; line = substr(line, 2)
                                # Consume regex flags
                                while (length(line) > 0 && \
                                       index("dgimsuyv", substr(line, 1, 1)) > 0) {
                                    out = out substr(line, 1, 1)
                                    line = substr(line, 2)
                                }
                                break
                            } else {
                                out = out c1; line = substr(line, 2)
                            }
                        }
                    } else {
                        # Division operator: emit /
                        out = out substr(line, 1, mp)
                        line = substr(line, mp + 1)
                    }
                } else if (mt == "dq") {
                    out = out substr(line, 1, mp)
                    line = substr(line, mp + 1)
                    in_str = 1; str_delim = "\""
                } else if (mt == "sq") {
                    out = out substr(line, 1, mp)
                    line = substr(line, mp + 1)
                    in_str = 1; str_delim = SQ
                } else if (mt == "bt") {
                    out = out substr(line, 1, mp)
                    line = substr(line, mp + 1)
                    in_str = 1; str_delim = "`"
                }
            }
        }
        print out
    }
    ' "$1"
}

# Pre-strip block comments for accurate code-only pattern detection.
# check_pattern greps these stripped copies to avoid false positives
# on theater tokens inside /* ... */ comments.
STRIPPED_DIR=$(mktemp -d)
trap 'rm -rf "$STRIPPED_DIR"' EXIT

STRIPPED_FILES=()
for f in "${JS_FILES[@]}"; do
    mkdir -p "$STRIPPED_DIR/$(dirname "$f")"
    _strip_block_comments "$f" > "$STRIPPED_DIR/$f"
    STRIPPED_FILES+=("$STRIPPED_DIR/$f")
done

# check_pattern: detect theater in executable code.
# Greps block-comment-stripped copies to eliminate /* ... */ false positives.
# Line-comment lines (// ...) are still filtered via grep -v.
# THEATER_OK suppression checks the ORIGINAL source line (not stripped),
# so markers inside block comments (e.g. /* THEATER_OK */) still suppress.
check_pattern() {
    local pattern="$1"
    local reason="$2"

    local all_matches
    all_matches=$(grep -HnE "$pattern" "${STRIPPED_FILES[@]}" 2>/dev/null \
        | sed "s|^${STRIPPED_DIR}/||" \
        | grep -v ':[0-9]*:\s*//' \
        || true)

    if [ -z "$all_matches" ]; then
        return
    fi

    local prev_file=""
    local file_lines=0
    while IFS= read -r line; do
        local file="${line%%:*}"
        local rest="${line#*:}"
        local lineno="${rest%%:*}"

        # Check THEATER_OK against the ORIGINAL source line (not stripped).
        # This preserves suppression for markers inside block comments.
        local original_line
        original_line=$(sed -n "${lineno}p" "$file" 2>/dev/null || true)
        if echo "$original_line" | grep -q 'THEATER_OK'; then
            continue
        fi

        if [ "$file" != "$prev_file" ]; then
            prev_file="$file"
            file_lines=0
            echo "  ✗ THEATER in $file: $reason"
            ERRORS=$((ERRORS + 1))
        fi
        file_lines=$((file_lines + 1))
        if [ "$file_lines" -le 5 ]; then
            echo "      $rest"
        fi
    done <<< "$all_matches"
}

# check_comment_pattern: detect theater that IS in comments (no comment filter).
# Searches ORIGINAL files (not stripped) since we are looking FOR comment patterns.
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
