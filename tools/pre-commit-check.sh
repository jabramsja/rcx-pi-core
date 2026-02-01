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
# Note: Kernel/engine seeds use underscore-prefixed fields (_mode, _phase, etc.) by design
#       to distinguish internal state from domain data. See:
#       - MetaCircularKernel.v0.md (kernel.v1.json, match.v2.json, subst.v2.json)
#       - EngineNewsStructural.v0.md (enginenews.v1.json)
KERNEL_SEEDS="kernel.v1.json|match.v2.json|subst.v2.json|enginenews.v1.json"
if [ -n "$STAGED_JSON" ]; then
    echo "-- Checking for non-standard underscore keys in JSON..."
    for f in $STAGED_JSON; do
        if [[ "$f" == prototypes/* ]] || [[ "$f" == seeds/* ]]; then
            # Skip kernel/engine seeds - they legitimately use underscore-prefixed fields
            if echo "$f" | grep -qE "$KERNEL_SEEDS"; then
                continue
            fi
            # Also allow _marker and _type in any seed (security/type features)
            if grep -nE '"_[a-zA-Z]+":' "$f" 2>/dev/null | grep -vE '"_marker":|"_type":'; then
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

# 6b. Run test theater check (assert True)
echo "-- Running test theater check..."
if ! ./tools/check_test_theater.sh tests 2>/dev/null; then
    echo "❌ Test theater check failed (found vacuous assert True)"
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

# 8. Check docs index is up-to-date (if docs changed)
STAGED_DOCS=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^docs/.*\.md$' || true)
if [ -n "$STAGED_DOCS" ]; then
    echo "-- Checking docs index is up-to-date..."
    if ! python3 tools/generate_docs_index.py --check 2>/dev/null; then
        echo "❌ docs/README.md is out of date"
        echo "   Run: python tools/generate_docs_index.py"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 9. Remind about doc updates
if [ -n "$STAGED_PY" ]; then
    for f in $STAGED_PY; do
        if [[ "$f" == rcx_pi/* ]] || [[ "$f" == prototypes/* ]]; then
            echo "📝 Reminder: Update docs/ if implementation differs from spec"
            break
        fi
    done
fi

# 10. Check JS debt parity if JS file changed
STAGED_JS=$(git diff --cached --name-only --diff-filter=ACM | grep -E 'eval_step\.js$' || true)
if [ -n "$STAGED_JS" ]; then
    echo "-- Checking JS debt markers (L3 parity)..."
    if ! ./tools/check_js_debt.sh 2>/dev/null; then
        echo "❌ JS debt check failed"
        ERRORS=$((ERRORS + 1))
    fi

    echo "-- Checking JS contraband (forbidden patterns)..."
    if ! ./tools/contraband_js.sh 2>/dev/null; then
        echo "❌ JS contraband check failed"
        ERRORS=$((ERRORS + 1))
    fi

    echo "-- Checking JS AST police..."
    if ! ./tools/ast_police_js.sh 2>/dev/null; then
        echo "❌ JS AST police check failed"
        ERRORS=$((ERRORS + 1))
    fi

    echo "-- Checking JS test theater..."
    if ! ./tools/check_test_theater_js.sh 2>/dev/null; then
        echo "❌ JS test theater check failed"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 12. Check seed integrity if seed files changed
STAGED_SEEDS=$(git diff --cached --name-only --diff-filter=ACM | grep -E 'seeds/.*\.json$' || true)
if [ -n "$STAGED_SEEDS" ]; then
    echo "-- Checking seed police (structure, theater, host leakage)..."
    if ! ./tools/seed_police.sh 2>/dev/null; then
        echo "❌ Seed police check failed"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 11. Run JS tests if JS file or seeds changed
STAGED_SEEDS=$(git diff --cached --name-only --diff-filter=ACM | grep -E 'seeds/.*\.json$' || true)
if [ -n "$STAGED_JS" ] || [ -n "$STAGED_SEEDS" ]; then
    echo "-- Running JS parity tests..."
    if ! node experiments/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
        echo "❌ JS parity tests failed"
        ERRORS=$((ERRORS + 1))
    else
        echo "   JS tests pass"
    fi
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo "❌ Pre-commit check failed with $ERRORS error(s)"
    echo "Fix the issues above or use 'git commit --no-verify' to bypass"
    exit 1
fi

echo "✅ Pre-commit checks passed"
