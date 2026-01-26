#!/usr/bin/env bash
# Pre-commit quick checks for RCX
#
# STANDARD WORKFLOW (saves API costs):
# 1. Run this script before committing: ./tools/pre-commit-check.sh
# 2. Run agents locally (uses your subscription): python tools/run_verifier.py <files>
# 3. Push - CI runs fast checks (tests, audit) - FREE
# 4. CI agents are manual-trigger only - use GitHub Actions UI when needed
#
# Install as git hook:
#   cp tools/pre-commit-check.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#
# Or run manually: ./tools/pre-commit-check.sh

set -euo pipefail

echo "🔍 Running pre-commit checks..."

# Get staged files
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' || true)
STAGED_JSON=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.json$' || true)

ERRORS=0

# 1. Check for private attr access in tests/prototypes
if [ -n "$STAGED_PY" ]; then
    echo "-- Checking for private attr access..."
    for f in $STAGED_PY; do
        if [[ "$f" == tests/* ]] || [[ "$f" == prototypes/* ]]; then
            if grep -nE '\._[a-zA-Z0-9]+' "$f" 2>/dev/null; then
                echo "❌ Private attr access in $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# 2. Check for underscored imports from rcx_pi
if [ -n "$STAGED_PY" ]; then
    echo "-- Checking for underscored imports..."
    for f in $STAGED_PY; do
        if [[ "$f" == tests/* ]] || [[ "$f" == prototypes/* ]]; then
            if grep -nE 'from rcx_pi\..* import _' "$f" 2>/dev/null; then
                echo "❌ Underscored import from rcx_pi in $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# 3. Check for underscore-prefixed keys in JSON
if [ -n "$STAGED_JSON" ]; then
    echo "-- Checking for non-standard underscore keys in JSON..."
    for f in $STAGED_JSON; do
        if [[ "$f" == prototypes/* ]] || [[ "$f" == seeds/* ]]; then
            if grep -nE '"_[a-zA-Z]+":' "$f" 2>/dev/null; then
                echo "❌ Non-standard underscore key in $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# 4. Quick syntax check for Python files
if [ -n "$STAGED_PY" ]; then
    echo "-- Checking Python syntax..."
    for f in $STAGED_PY; do
        if [ -f "$f" ]; then
            if ! python3 -m py_compile "$f" 2>/dev/null; then
                echo "❌ Syntax error in $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# 5. Check for bare except clauses
if [ -n "$STAGED_PY" ]; then
    echo "-- Checking for bare except clauses..."
    for f in $STAGED_PY; do
        if [[ "$f" == rcx_pi/* ]]; then
            if grep -nE '^\s*except\s*:' "$f" 2>/dev/null; then
                echo "❌ Bare except clause in $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
fi

# 6. Run contraband.sh (fast grep-based linter)
echo "-- Running contraband check..."
if ! ./tools/contraband.sh rcx_pi 2>/dev/null; then
    echo "❌ Contraband check failed"
    ERRORS=$((ERRORS + 1))
fi

# 7. Run ast_police.py (catches what grep misses)
if [ -n "$STAGED_PY" ]; then
    echo "-- Running AST police on staged files..."
    STAGED_RCX_PY=$(echo "$STAGED_PY" | grep '^rcx_pi/' || true)
    if [ -n "$STAGED_RCX_PY" ]; then
        if ! python3 tools/ast_police.py $STAGED_RCX_PY 2>/dev/null; then
            echo "❌ AST police check failed"
            ERRORS=$((ERRORS + 1))
        fi
    fi
fi

# 8. Remind about doc updates
if [ -n "$STAGED_PY" ]; then
    for f in $STAGED_PY; do
        if [[ "$f" == rcx_pi/* ]] || [[ "$f" == prototypes/* ]]; then
            echo "📝 Reminder: Update docs/ if implementation differs from spec"
            break
        fi
    done
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ Pre-commit check failed with $ERRORS error(s)"
    echo "Fix the issues above or use 'git commit --no-verify' to bypass"
    exit 1
fi

echo "✅ Pre-commit checks passed"
