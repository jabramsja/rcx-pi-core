#!/bin/bash
# The "Dumb" Linter - Catches dangerous Python patterns.
# A regex never hallucinates. Run this BEFORE waking up the AI agents.
#
# Philosophy: Block the dangerous stuff, allow the necessary scaffolding.
# Add "# CONTRABAND_OK: reason" to whitelist specific lines.

set -e

RCX_DIR="${1:-./rcx_pi}"
EXIT_CODE=0

echo "Scanning $RCX_DIR for contraband..."
echo ""

# Exclude experimental and CLI directories
EXCLUDE="--exclude-dir=worlds --exclude-dir=prototypes --exclude-dir=core"
# Exclude CLI files (they need dynamic imports for error handling)
EXCLUDE_FILES="--exclude=*_cli.py"

# 1. Ban 'eval(' - NO EXCEPTIONS
EVAL_HITS=$(grep -rn "\beval(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$EVAL_HITS" ]; then
    echo "CRITICAL: Found 'eval()'. Code injection risk:"
    echo "$EVAL_HITS"
    echo ""
    EXIT_CODE=1
fi

# 2. Ban 'exec(' - NO EXCEPTIONS
EXEC_HITS=$(grep -rn "\bexec(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$EXEC_HITS" ]; then
    echo "CRITICAL: Found 'exec()'. Code injection risk:"
    echo "$EXEC_HITS"
    echo ""
    EXIT_CODE=1
fi

# 3. Ban 'globals()' and 'locals()' (Scope Leakage)
GLOBALS_HITS=$(grep -rn "\bglobals(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$GLOBALS_HITS" ]; then
    echo "CRITICAL: Found 'globals()'. Scope leakage:"
    echo "$GLOBALS_HITS"
    echo ""
    EXIT_CODE=1
fi

LOCALS_HITS=$(grep -rn "\blocals(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$LOCALS_HITS" ]; then
    echo "CRITICAL: Found 'locals()'. Scope leakage:"
    echo "$LOCALS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 4. Ban dangerous dunder access (Metaclass Smuggling)
DUNDER_HITS=$(grep -rn "__class__\|__bases__\|__mro__\|__subclasses__" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$DUNDER_HITS" ]; then
    echo "CRITICAL: Found metaclass dunder access:"
    echo "$DUNDER_HITS"
    echo ""
    EXIT_CODE=1
fi

# 5. Ban 'pickle' (Arbitrary Code Execution)
PICKLE_HITS=$(grep -rn "import pickle\|from pickle" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$PICKLE_HITS" ]; then
    echo "CRITICAL: Found 'pickle'. Arbitrary code execution risk:"
    echo "$PICKLE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 6. Ban 'compile(' except re.compile (Code generation)
COMPILE_HITS=$(grep -rn "\bcompile(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "re.compile" | grep -v "CONTRABAND_OK" || true)
if [ -n "$COMPILE_HITS" ]; then
    echo "CRITICAL: Found 'compile()'. Code generation risk:"
    echo "$COMPILE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 7. Ban actual lambda USAGE (not just the word in comments)
# Look for "= lambda" or ": lambda" patterns that indicate actual lambda expressions
LAMBDA_HITS=$(grep -rn "= lambda \|: lambda " "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "key=lambda" | grep -v "CONTRABAND_OK" || true)
if [ -n "$LAMBDA_HITS" ]; then
    echo "CRITICAL: Found lambda expression (not in sort key):"
    echo "$LAMBDA_HITS"
    echo ""
    EXIT_CODE=1
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "No contraband syntax found in core RCX code."
    echo ""
    echo "Excluded from scan:"
    echo "  - worlds/, prototypes/, core/ directories"
    echo "  - *_cli.py files (CLI wrappers)"
    echo ""
    echo "ALLOWED patterns (not contraband):"
    echo "  - lambda in sort keys: .sort(key=lambda ...)"
    echo "  - set() for key comparison or cycle detection"
    echo "  - id() for cycle detection"
    echo "  - Lines marked with # CONTRABAND_OK"
else
    echo "CONTRABAND DETECTED - Fix before running AI agents."
    exit 1
fi
