#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FAST AUDIT - For local development iteration (~2 minutes)
# ============================================================================
#
# This is the quick sanity check for local development. It runs:
# - Syntax/structure checks (contraband, AST police)
# - Core algorithm tests (match, subst, step, kernel)
# - Skips fuzzer tests (those run in CI via audit_all.sh)
#
# Use this for rapid iteration. Run audit_all.sh before pushing.
#
# Usage:
#   ./tools/audit_fast.sh
#
# See also:
#   ./tools/audit_all.sh  - Full audit including fuzzer (CI standard)
# ============================================================================

# macOS bash session-save quirks
export HISTTIMEFORMAT="${HISTTIMEFORMAT:-}"
export size="${size:-}"

echo "== FAST AUDIT (local iteration) =="
echo ""

# Check if pytest-xdist is available for parallel execution
PARALLEL_FLAG=""
if python3 -c "import xdist" 2>/dev/null; then
    PARALLEL_FLAG="-n auto"
    echo "Using parallel execution (pytest-xdist detected)"
else
    echo "Note: Install pytest-xdist for faster execution: pip install pytest-xdist"
fi
echo ""

echo "== 1) Contraband check =="
./tools/contraband.sh rcx_pi

echo "== 2) AST police =="
python3 tools/ast_police.py

echo "== 3) Debt dashboard =="
./tools/debt_dashboard.sh | tail -5

echo "== 4) Core structural tests (parallel if available) =="
# Run core algorithm tests - these are the most important for local iteration
# Skip fuzzer tests (those run 500-1000 examples each, slow locally)
# Core tests: match, subst, step, kernel, eval_seed, mu_type
PYTHONHASHSEED=0 pytest $PARALLEL_FLAG -q \
    tests/structural/ \
    tests/test_match_parity.py \
    tests/test_match_v2_parity.py \
    tests/test_subst_parity.py \
    tests/test_subst_v2_parity.py \
    tests/test_step_mu_parity.py \
    tests/test_kernel_v0.py \
    tests/test_kernel_projections.py \
    tests/test_phase7c_integration.py \
    tests/test_eval_seed_v0.py \
    tests/test_eval_seed_parity.py \
    tests/test_mu_type.py \
    tests/test_seed_integrity.py \
    tests/test_classify_mu.py

echo ""
echo "✅ Fast audit pass"
echo ""
echo "Note: This is a quick sanity check. Run ./tools/audit_all.sh before pushing."
