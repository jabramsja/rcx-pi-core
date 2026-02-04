#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# ============================================================================
# FAST AUDIT - For local development iteration (~3 minutes)
# ============================================================================
#
# TESTING TIERS:
#   Tier 1: Fast Audit (this script) - Core tests, ~3 min
#   Tier 2: Full Audit (audit_all.sh) - Core + Fuzzer, ~5-8 min
#   Tier 3: Stress Tests (tests/stress/) - Deep edge cases, ~10+ min
#
# This script runs Tier 1 only:
# - Syntax/structure checks (contraband, AST police)
# - Core algorithm tests (match, subst, step, kernel)
# - Skips fuzzer tests (those run in Tier 2)
# - Skips stress tests (those run in Tier 3)
#
# Use this for rapid iteration. Run audit_all.sh before pushing.
#
# Usage:
#   ./tools/audit_fast.sh
#
# See also:
#   ./tools/audit_all.sh       - Tier 2: Full audit including fuzzer
#   pytest tests/stress/ -v    - Tier 3: Deep edge case stress tests
# ============================================================================

echo "== FAST AUDIT (local iteration) =="
echo ""

# Check if pytest-xdist is available for parallel execution
# Using --dist worksteal for better load balancing (idle workers steal from busy)
PARALLEL_FLAG=""
if python3 -c "import xdist" 2>/dev/null; then
    PARALLEL_FLAG="-n auto --dist worksteal"
    echo "Using parallel execution with worksteal (pytest-xdist detected)"
else
    echo "Note: Install pytest-xdist for faster execution: pip install pytest-xdist"
fi
echo ""

echo "== 1a) Contraband check =="
./tools/contraband.sh rcx_pi

echo "== 1b) Test theater check =="
./tools/check_test_theater.sh tests

echo "== 1c) JS contraband check =="
./tools/contraband_js.sh

echo "== 1d) JS AST police =="
./tools/ast_police_js.sh

echo "== 1e) JS test theater check =="
./tools/check_test_theater_js.sh

echo "== 1f) Seed police =="
./tools/seed_police.sh

echo "== 1g) Anti-cheat scans =="
# No private attr access in tests/ or prototypes/
echo "-- no private attr access in tests/ or prototypes/"
if grep -RInE '\._[a-zA-Z0-9]+' tests/ prototypes/ 2>/dev/null | \
    grep -v 'self\._' | \
    grep -v '_getframe.*CONTRABAND_OK' | \
    grep -v '# ANTICHEAT_OK' | \
    grep -v 'sys\._getframe\|sys\._current_frames' | \
    grep -v 'test_contraband_detection.py.*"""' | \
    grep -v '__pycache__'; then
  echo "ERROR: Found private attr access"
  exit 1
fi
echo "OK"

# No underscored imports from rcx_pi in tests/ or prototypes/
echo "-- no underscored imports from rcx_pi in tests/ or prototypes/"
if grep -RInE 'from rcx_pi\..* import _' tests/ prototypes/ 2>/dev/null | \
    grep -v 'test_type_tag_security.py' | \
    grep -v '# ANTICHEAT_OK' | \
    grep -v '__pycache__'; then
  echo "ERROR: Found underscored import from rcx_pi"
  exit 1
fi
echo "OK"

echo "== 1h) Doc contract verification =="
pytest tests/docs/test_doc_contracts.py -q

echo "== 1i) Doc freshness check (semantic drift) =="
pytest tests/docs/test_doc_freshness.py -q

echo "== 1j) Doc governance check (Three Laws) =="
pytest tests/docs/test_doc_governance.py -q

echo "== 1k) Root files governance check =="
pytest tests/docs/test_root_files.py -q

echo "== 2) AST police (Python) =="
python3 tools/ast_police.py

echo "== 3) Debt dashboard =="
./tools/debt_dashboard.sh | tail -5

echo "== 4) Core structural tests (parallel if available) =="
# Run core algorithm tests - these are the most important for local iteration
# Skip fuzzer tests (those run 500-1000 examples each, slow locally)
# Core tests: match, subst, step, kernel, eval_seed, mu_type
pytest $PARALLEL_FLAG -q \
    tests/structural/ \
    tests/tools/ \
    tests/test_match_parity.py \
    tests/test_match_v2_parity.py \
    tests/test_subst_parity.py \
    tests/test_subst_v2_parity.py \
    tests/test_step_mu_parity.py \
    tests/test_kernel_projections.py \
    tests/test_phase7c_integration.py \
    tests/test_eval_seed_v0.py \
    tests/test_eval_seed_parity.py \
    tests/test_mu_type.py \
    tests/test_seed_integrity.py \
    tests/test_classify_mu.py \
    tests/test_parity_python.py \
    tests/test_structural_trace.py \
    tests/test_kernel_security_fuzzer.py \
    tests/test_normalization_roundtrip.py \
    tests/test_debt_enforcement.py \
    tests/test_eval_seed_adversary.py \
    tests/test_self_hosting_v0.py \
    tests/test_phase8b_grounding_gaps.py \
    tests/test_recurrence_parity.py \
    tests/test_exhaustion_parity.py \
    tests/test_js_parity_automated.py \
    tests/test_bootstrap_structural_bridge.py \
    tests/test_meta_circular_gate6.py \
    tests/test_execution_path_verification.py

echo ""
echo "== 5) JavaScript debt check =="
# Note: JS parity is already tested via test_js_parity_automated.py in pytest above
# The check_js_debt.sh verifies debt markers match Python
./tools/check_js_debt.sh

echo ""
echo "✅ Fast audit pass"
echo ""
echo "Note: This is a quick sanity check. Run ./tools/audit_all.sh before pushing."
