#!/usr/bin/env bash
# RCX JavaScript Contraband Check
# Blocks forbidden patterns that would break L3 parity guarantees
#
# Usage: ./tools/checks/linters/contraband_js.sh [file_or_dir]
#        Default: mu/host/js/ (scans all *.js recursively)
#        Single file: ./tools/checks/linters/contraband_js.sh path/to/file.js
#
# Marker: CONTRABAND_OK on the same line suppresses that match.
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

echo "Scanning $FILE_COUNT JS file(s) under $TARGET for contraband patterns..."

ERRORS=0

check_pattern() {
    local pattern="$1"
    local reason="$2"

    # Batch all files into one grep call (15x fewer subprocesses)
    local all_matches
    all_matches=$(grep -Hn "$pattern" "${JS_FILES[@]}" 2>/dev/null \
        | grep -v ':[0-9]*:\s*//' \
        | grep -v ':[0-9]*:\s*\*' \
        | grep -v '/\*.*\*/' \
        | grep -v 'CONTRABAND_OK' \
        || true)

    if [ -z "$all_matches" ]; then
        return
    fi

    # Group matches by file for per-file reporting
    local prev_file=""
    local file_lines=0
    while IFS= read -r line; do
        local file="${line%%:*}"
        if [ "$file" != "$prev_file" ]; then
            prev_file="$file"
            file_lines=0
            echo "  ✗ CONTRABAND: '$pattern' in $file - $reason"
            ERRORS=$((ERRORS + 1))
        fi
        file_lines=$((file_lines + 1))
        if [ "$file_lines" -le 5 ]; then
            local rest="${line#*:}"
            echo "      $rest"
        fi
    done <<< "$all_matches"
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
check_pattern "webcrypto" "webcrypto API provides getRandomValues (non-determinism)"
check_pattern "getRandomValues" "getRandomValues breaks determinism"
check_pattern "crypto\.subtle" "crypto.subtle API may generate non-deterministic keys"

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
    echo "❌ JS contraband check FAILED: $ERRORS forbidden pattern(s) found in $FILE_COUNT file(s)"
    echo ""
    echo "These patterns break L3 parity guarantees (determinism, purity, isolation)."
    echo "Mark intentional exceptions with // CONTRABAND_OK: <reason> on the same line."
    echo "See mu/docs/core/SelfHosting.v0.md for allowed bootstrap patterns."
    exit 1
fi

echo "✓ No contraband patterns found in $FILE_COUNT file(s)"
echo "OK: JS contraband check passed"
