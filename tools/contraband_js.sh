#!/usr/bin/env bash
# RCX JavaScript Contraband Check
# Blocks forbidden patterns that would break L3 parity guarantees
#
# Usage: ./tools/contraband_js.sh [file]
#        Default: mu/host/js/eval_step.js
#
# Forbidden patterns (break determinism or purity):
#   eval(           - Code injection
#   Function(       - Dynamic function creation
#   setTimeout      - Async (breaks determinism)
#   setInterval     - Async (breaks determinism)
#   Math.random     - Non-determinism
#   Date.now        - Non-determinism
#   new Date()      - Non-determinism
#   process.env     - Environment leakage
#   child_process   - Subprocess spawning
#   fs.write        - File mutation (read-only allowed)
#   fs.append       - File mutation
#   fs.unlink       - File mutation
#   fs.rm           - File mutation

set -euo pipefail

JS_FILE="${1:-mu/host/js/eval_step.js}"

if [ ! -f "$JS_FILE" ]; then
    echo "ERROR: $JS_FILE not found"
    exit 1
fi

echo "Checking $JS_FILE for contraband patterns..."

ERRORS=0

# Check for forbidden patterns
# Each pattern has a reason why it's forbidden

check_pattern() {
    local pattern="$1"
    local reason="$2"
    local matches

    # Use grep -n to show line numbers, exclude comments (lines starting with //, *, or whitespace+*)
    matches=$(grep -n "$pattern" "$JS_FILE" 2>/dev/null | grep -v '^\s*//' | grep -v '^\s*\*' | grep -v '/\*.*\*/' || true)

    if [ -n "$matches" ]; then
        echo "  ✗ CONTRABAND: '$pattern' - $reason"
        echo "$matches" | head -5 | sed 's/^/      /'
        ERRORS=$((ERRORS + 1))
    fi
}

# Determinism breakers
check_pattern "eval(" "Code injection breaks purity"
check_pattern "Function(" "Dynamic function creation breaks purity"
check_pattern "setTimeout" "Async breaks determinism"
check_pattern "setInterval" "Async breaks determinism"
check_pattern "Math\.random" "Non-determinism"
check_pattern "Date\.now" "Non-determinism"
check_pattern "new Date(" "Non-determinism"

# Environment leakage
check_pattern "process\.env" "Environment leakage breaks reproducibility"

# Subprocess spawning
check_pattern "child_process" "Subprocess spawning breaks isolation"
check_pattern "exec(" "Subprocess execution breaks isolation"
check_pattern "spawn(" "Subprocess spawning breaks isolation"

# File mutation (fs.readFileSync is allowed - bootstrap needs to load seeds)
check_pattern "fs\.write" "File mutation breaks purity (read-only allowed)"
check_pattern "fs\.append" "File mutation breaks purity"
check_pattern "fs\.unlink" "File mutation breaks purity"
check_pattern "fs\.rm" "File mutation breaks purity"
check_pattern "fs\.mkdir" "File mutation breaks purity"
check_pattern "fs\.rename" "File mutation breaks purity"

# Network (would break determinism)
check_pattern "require.*http" "Network access breaks determinism"
check_pattern "require.*https" "Network access breaks determinism"
check_pattern "fetch(" "Network access breaks determinism"

# VM module (eval equivalent - CRITICAL)
check_pattern "require.*vm" "vm module provides eval capabilities"
check_pattern "vm\.run" "vm.run* provides code execution"

# Crypto randomness (non-determinism)
# Note: crypto.createHash (SHA256) is deterministic and allowed for seed integrity verification
check_pattern "crypto\.random" "crypto.randomBytes breaks determinism"
check_pattern "crypto\.generateKey" "crypto.generateKey breaks determinism"

# WebAssembly (arbitrary code execution - CRITICAL)
check_pattern "WebAssembly" "WebAssembly allows arbitrary compiled code execution"

# Workers and shared memory (concurrency breaks determinism)
check_pattern "new Worker" "Worker threads break determinism"
check_pattern "worker_threads" "Worker threads break determinism"
check_pattern "SharedArrayBuffer" "Shared memory breaks determinism"
check_pattern "Atomics\." "Atomic operations break determinism"

# Promise (async without async/await keywords)
check_pattern "new Promise" "Promise enables async without async keyword"
check_pattern "Promise\." "Promise API enables async execution"

# Allowed patterns (for documentation):
# - fs.readFileSync - Bootstrap must load seeds
# - console.log - Debug output (doesn't affect computation)
# - JSON.parse/stringify - Pure data transformation
# - Object.keys/values/entries - Pure introspection
# - Array methods (map, filter, reduce, etc.) - Pure transformations

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ JS contraband check FAILED: $ERRORS forbidden pattern(s) found"
    echo ""
    echo "These patterns break L3 parity guarantees (determinism, purity, isolation)."
    echo "See docs/core/SelfHosting.v0.md for allowed bootstrap patterns."
    exit 1
fi

echo "✓ No contraband patterns found"
echo "OK: JS contraband check passed"
