#!/usr/bin/env bash
# RCX JavaScript AST Police
# Catches patterns that grep-based contraband check misses
#
# Usage: ./tools/ast_police_js.sh [file]
#        Default: substrates/js/eval_step.js
#
# This catches sneaky patterns like:
#   - Indirect eval: window['eval'], globalThis.eval, (0,eval)
#   - Dynamic property access hiding forbidden calls
#   - String concatenation to bypass grep: 'ev'+'al'
#   - Obfuscated function construction
#   - with() statements (scope manipulation)
#   - debugger statements (non-deterministic)
#   - arguments.callee (deprecated, non-strict)

set -euo pipefail

JS_FILE="${1:-substrates/js/eval_step.js}"

if [ ! -f "$JS_FILE" ]; then
    echo "ERROR: $JS_FILE not found"
    exit 1
fi

echo "AST Police inspecting $JS_FILE..."
echo "   Catching: indirect eval, dynamic access, obfuscation, scope manipulation"
echo ""

ERRORS=0

check_pattern() {
    local pattern="$1"
    local reason="$2"
    local matches

    # Exclude comments (lines starting with //, *, or containing /* */)
    matches=$(grep -nE "$pattern" "$JS_FILE" 2>/dev/null | grep -v '^\s*//' | grep -v '^\s*\*' | grep -v '^\s*/\*' || true)

    if [ -n "$matches" ]; then
        echo "  ✗ AST VIOLATION: $reason"
        echo "$matches" | head -5 | sed 's/^/      /'
        ERRORS=$((ERRORS + 1))
    fi
}

# Indirect eval patterns (bypass direct 'eval(' check)
check_pattern "window\[.*eval" "Indirect eval via window bracket access"
check_pattern "globalThis\[.*eval" "Indirect eval via globalThis bracket access"
check_pattern "global\[.*eval" "Indirect eval via global bracket access"
check_pattern "\(0,\s*eval\)" "Indirect eval via comma operator"
check_pattern "this\[.*eval" "Indirect eval via this bracket access"

# Dynamic property access that could hide forbidden calls
check_pattern "\[['\"]ev['\"].*\+.*['\"]al['\"]" "String concatenation to hide eval"
check_pattern "\[['\"]set['\"].*\+.*['\"]Timeout['\"]" "String concatenation to hide setTimeout"
check_pattern "\[['\"]set['\"].*\+.*['\"]Interval['\"]" "String concatenation to hide setInterval"

# Function constructor variants
check_pattern "new\s+Function\s*\(" "Function constructor (explicit)"
check_pattern "Function\.prototype\.constructor" "Function constructor via prototype"
check_pattern "\.constructor\s*\(" "Constructor access (potential Function bypass)"

# Scope manipulation
check_pattern "\bwith\s*\(" "with() statement - scope manipulation breaks determinism"
check_pattern "\bdebugger\b" "debugger statement - non-deterministic execution"

# Non-strict mode patterns
check_pattern "arguments\.callee" "arguments.callee - deprecated, non-strict"
check_pattern "arguments\.caller" "arguments.caller - deprecated, non-strict"

# Prototype pollution (could inject behavior)
check_pattern "__proto__" "__proto__ access - prototype pollution risk"
check_pattern "Object\.setPrototypeOf" "setPrototypeOf - prototype manipulation"

# Reflection that could bypass checks
check_pattern "Reflect\.construct" "Reflect.construct - could bypass Function check"
check_pattern "Reflect\.apply" "Reflect.apply - could bypass call checks"
check_pattern "Reflect\.get" "Reflect.get - could access eval/Function indirectly"

# Import/require that could bypass module checks
check_pattern "import\s*\(" "Dynamic import - could load arbitrary modules"
check_pattern "require\s*\(\s*[^'\"]" "Dynamic require - variable module loading"

# Generators and async (break determinism)
check_pattern "\basync\s+function" "async function - breaks determinism"
check_pattern "\bawait\s+" "await - async operation"
check_pattern "function\s*\*" "Generator function - stateful iteration"
check_pattern "\byield\b" "yield - generator state"

# Proxy (could intercept and modify behavior)
check_pattern "new\s+Proxy" "Proxy - behavior interception breaks purity"

# WeakMap/WeakSet (non-deterministic GC behavior)
check_pattern "new\s+WeakMap" "WeakMap - GC-dependent behavior"
check_pattern "new\s+WeakSet" "WeakSet - GC-dependent behavior"

# Symbol (hidden properties, non-deterministic iteration)
# Exception: const SENTINEL = Symbol('name') is allowed for sentinel values
# Block: Symbol as object key, Symbol.for (global registry), Symbol.iterator, etc.
check_pattern "Symbol\.for" "Symbol.for - global symbol registry"
check_pattern "Symbol\.iterator" "Symbol.iterator - custom iteration"
check_pattern "Symbol\.toStringTag" "Symbol.toStringTag - type spoofing"
check_pattern "\[Symbol\." "Symbol as object key - hidden properties"
# Note: const FOO = Symbol('FOO') is allowed for sentinel values (like Python's object())

# Blessed patterns (allowed, documented here for clarity):
# - const, let, var - variable declarations
# - function name() {} - named functions
# - arrow functions () => {} - lexical this
# - JSON.parse/stringify - pure data transformation
# - Object.keys/values/entries - pure introspection
# - Array methods (map, filter, reduce) - pure transformations
# - console.log - debug output (doesn't affect computation)
# - fs.readFileSync - bootstrap must load seeds (read-only)
# - require('fs'), require('path') - core modules for bootstrap

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "------------------------------------------------------------"
    echo "❌ AST Police found $ERRORS violation(s)"
    echo ""
    echo "These patterns can bypass grep-based contraband checks."
    echo "Fix the violations or mark with // AST_OK_JS: <reason>"
    exit 1
fi

echo "------------------------------------------------------------"
echo "✅ AST Police: No violations found"
