#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

sanitize_local_git_env() {
    local git_local_env
    git_local_env="$(git rev-parse --local-env-vars 2>/dev/null || true)"
    if [ -n "$git_local_env" ]; then
        # shellcheck disable=SC2086
        unset $git_local_env
    fi
}

sanitize_local_git_env

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# Use fast Hypothesis profile for local iteration (50 examples vs 500 default)
# CI sets its own profile via environment variable
export HYPOTHESIS_PROFILE="${HYPOTHESIS_PROFILE:-ci_fast}"

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
# - Skips most fuzzer tests (except kernel_security_fuzzer - critical for security)
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

# Check if git hooks are installed
if [ ! -L ".git/hooks/pre-commit" ]; then
    echo "⚠️  Warning: pre-commit hook not installed"
    echo "   Run: ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit"
    echo ""
fi
if [ ! -L ".git/hooks/pre-push" ]; then
    echo "⚠️  Warning: pre-push hook not installed"
    echo "   Run: ln -sf ../../tools/pre-push-fast .git/hooks/pre-push"
    echo ""
fi

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

echo "== 0) Agent review check =="
if ./tools/checks/check_agent_review_needed.sh; then
    echo ""
else
    echo "(This is a reminder - continuing with audit)"
    echo ""
fi

echo "== 0b) Untracked artifact check (BLOCKING) =="
./tools/checks/check_untracked_artifacts.sh

echo "== 1a) Contraband check =="
./tools/checks/linters/contraband.sh rcx_pi

echo "== 1b) Test theater check =="
./tools/checks/check_test_theater.sh tests

echo "== 1b2) L4 gate theater risk ratchet =="
python3 tools/checks/check_theater_risk_ratchet.py

echo "== 1b3) Simulated production logic check =="
python3 tools/checks/check_simulated_production_logic.py

echo "== 1c) JS contraband check =="
./tools/checks/linters/contraband_js.sh

echo "== 1d) JS AST police =="
./tools/checks/linters/ast_police_js.sh

echo "== 1e) JS test theater check =="
./tools/checks/check_test_theater_js.sh

echo "== 1f) Seed police =="
./tools/checks/linters/seed_police.sh

echo "== 1g) Anti-cheat scans =="
# No private attr access in tests/ (AST-based; docstring-aware)
echo "-- no private attr access in tests/ (AST-based)"
python3 tools/checks/linters/check_private_attr_access.py || exit 1
echo "OK"

# No underscored imports from rcx_pi in tests/ (AST-based)
echo "-- no underscored imports from rcx_pi in tests/ (AST-based)"
python3 tools/checks/linters/check_underscore_imports.py || exit 1
echo "OK"

echo "== 1h) Doc contract verification =="
pytest tests/docs/test_doc_contracts.py -q

echo "== 1i) Doc freshness check (semantic drift) =="
pytest tests/docs/test_doc_freshness.py -q

echo "== 1j) Doc governance check (Three Laws) =="
pytest tests/docs/test_doc_governance.py -q

echo "== 1k) Root files governance check =="
pytest tests/docs/test_root_files.py -q

echo "== 1l) Roadmap governance check =="
pytest tests/docs/test_roadmap_governance.py -q

echo "== 1n) Seed-auto execution contract check =="
python3 tools/checks/check_seed_auto_execution_contract.py

echo "== 1o) Host-semantics ratchet check =="
python3 tools/checks/check_host_semantics_ratchet.py

echo "== 1o2) Host-authority inventory ratchet check =="
python3 tools/checks/check_host_authority_inventory_ratchet.py

echo "== 1p) Bootstrap purity ratchet check =="
python3 tools/checks/check_bootstrap_purity_ratchet.py

echo "== 1q) Boot layer boundary check =="
python3 tools/checks/check_boot_layer_boundaries.py

_l4_has_runtime_files() {
    grep -Eq \
        '^(mu/host/|mu/substrate/|mu/closures/|mu/bridge/|mu/programs/|rcx_pi/selfhost/|mu/tools/compilers/)'
}

_l4_branch_wave_id() {
    local branch="$1"
    local suffix=""
    if [[ "$branch" == codex/* ]]; then
        suffix="${branch#codex/}"
    elif [[ "$branch" == jabramsja/* ]]; then
        suffix="${branch#jabramsja/}"
    fi
    if [[ "$suffix" =~ ^(.+)-restart(-.+)?$ ]]; then
        suffix="${BASH_REMATCH[1]}"
    fi
    if [ -n "$suffix" ] && grep -qE "Tracker sync note \([^,]+, ${suffix}\):" TASKS.md 2>/dev/null; then
        printf '%s' "$suffix"
    fi
}

echo "== 1m) L4 execution contract check =="
# Derive wave-id from branch name when TASKS.md is in the scope being checked.
# Supports codex/* and jabramsja/* branch naming conventions.
# Follow-up CI/tooling commits that don't change TASKS.md skip wave-class enforcement.
L4_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git diff --cached --name-only | grep -q .; then
    STAGED_FILES="$(git diff --cached --name-only)"
    # Shared exact-match derivation prevents restart branches from forcing a
    # bogus wave id into the L4 checker when TASKS.md carries the canonical
    # tracked wave instead.
    # shellcheck source=/dev/null
    source tools/checks/derive_wave_id.sh "$L4_BRANCH" --staged
    L4_CLASS_FLAG=()
    # Staged tooling/control-plane follow-up commits on a structural branch
    # must be judged as L4_ENABLER diffs even when TASKS.md-derived wave id
    # binding points at the branch-wide structural tracker note.
    if ! printf '%s\n' "$STAGED_FILES" | _l4_has_runtime_files; then
        if [ -z "$WAVE_ID_FLAG" ]; then
            STAGED_WAVE_ID="$(_l4_branch_wave_id "$L4_BRANCH")"
            if [ -n "$STAGED_WAVE_ID" ]; then
                WAVE_ID_FLAG="--wave-id=$STAGED_WAVE_ID"
            fi
        fi
        L4_CLASS_FLAG=(--wave-class L4_ENABLER)
    fi
    python3 tools/checks/enforce_l4_execution_contract.py --staged $WAVE_ID_FLAG "${L4_CLASS_FLAG[@]}"
else
    # No staged files — use committed range.
    # L4 contract must evaluate the FULL wave diff from dev, not per-push
    # incremental (@{upstream}...HEAD).  Incremental ranges miss runtime
    # files committed in earlier pushes, causing indicator delta mismatches
    # with CI (which always uses origin/dev...HEAD).  Matches pre-push-fast.
    L4_RANGE=""
    if git show-ref --verify --quiet refs/remotes/origin/dev; then
        L4_RANGE="origin/dev...HEAD"
    elif git rev-parse --verify --quiet "@{upstream}" >/dev/null 2>&1; then
        L4_RANGE="@{upstream}...HEAD"
    fi
    if [ -n "$L4_RANGE" ]; then
        L4_RANGE_FILES="$(git diff --name-only "$L4_RANGE" 2>/dev/null || true)"
        if [ -n "$L4_RANGE_FILES" ]; then
            echo "No staged files — using committed range $L4_RANGE"
            # shellcheck source=/dev/null
            source tools/checks/derive_wave_id.sh "$L4_BRANCH" --range "$L4_RANGE"
            python3 tools/checks/enforce_l4_execution_contract.py --range "$L4_RANGE" $WAVE_ID_FLAG
        else
            echo "No staged files, no committed changes in $L4_RANGE — skipping L4 check"
        fi
    else
        # No upstream — check dirty tracked files only (NO untracked)
        L4_DIRTY_FILES="$(git diff --name-only | sort -u)"
        if [ -n "$L4_DIRTY_FILES" ]; then
            echo "No staged files, no upstream — checking dirty tracked files only"
            # shellcheck source=/dev/null
            source tools/checks/derive_wave_id.sh "$L4_BRANCH" --files "$L4_DIRTY_FILES"
            # shellcheck disable=SC2086
            python3 tools/checks/enforce_l4_execution_contract.py --files $L4_DIRTY_FILES $WAVE_ID_FLAG
        else
            echo "No staged or dirty tracked files — skipping L4 check"
        fi
    fi
fi

echo "== 2a) Structural lint (projection validity) =="
python3 tools/docs/structural_lint.py mu/

echo "== 2b) AST police (Python) =="
python3 tools/checks/linters/ast_police.py

echo "== 3) Debt dashboard =="
./tools/debt_dashboard.sh | tail -5

echo "== 4) Core structural tests (parallel if available) =="
# Run core algorithm tests - these are the most important for local iteration
# Skip fuzzer tests (those run 500-1000 examples each, slow locally)
# Core tests: match, subst, step, kernel, eval_seed, mu_type
pytest $PARALLEL_FLAG -q -m "not slow and not fuzzer" \
    tests/structural/ \
    tests/tools/ \
    tests/l4_gates/ \
    tests/parity/test_match_parity.py \
    tests/parity/test_match_v2_parity.py \
    tests/parity/test_subst_parity.py \
    tests/parity/test_subst_v2_parity.py \
    tests/parity/test_step_mu_parity.py \
    tests/engine/test_kernel_projections.py \
    tests/integration/test_phase7c_integration.py \
    tests/engine/test_eval_seed_v0.py \
    tests/parity/test_eval_seed_parity.py \
    tests/engine/test_mu_type.py \
    tests/engine/test_seed_integrity.py \
    tests/engine/test_classify_mu.py \
    tests/parity/test_parity_python.py \
    tests/engine/test_structural_trace.py \
    tests/fuzz/test_kernel_security_fuzzer.py \
    tests/engine/test_normalization_roundtrip.py \
    tests/tools/test_debt_enforcement.py \
    tests/parity/test_eval_seed_adversary.py \
    tests/integration/test_self_hosting_v0.py \
    tests/engine/test_phase8b_grounding_gaps.py \
    tests/parity/test_recurrence_parity.py \
    tests/parity/test_exhaustion_parity.py \
    tests/structural/test_bootstrap_structural_bridge.py \
    tests/integration/test_meta_circular_gate6.py \
    tests/structural/test_execution_path_verification.py \
    tests/parity/test_js_parity_automated.py

echo ""
echo "== 5) JavaScript L3 parity check =="
./tools/checks/check_js_debt.sh
if node mu/host/js/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS tests pass"
else
    echo "FAIL: JS tests failed"
    node mu/host/js/eval_step.js 2>&1 | tail -10
    exit 1
fi

# === Condensed Summary ===
CURRENT_PHASE=$(grep -E '^PHASE:' STATUS.md 2>/dev/null | sed 's/PHASE: *//' || echo "?")
DEBT_CURRENT=$(grep -E '^CURRENT:' STATUS.md 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "?")
DEBT_THRESHOLD=$(grep -E '^THRESHOLD:' STATUS.md 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "?")

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ FAST AUDIT PASS"
echo "   Phase: $CURRENT_PHASE | Debt: $DEBT_CURRENT/$DEBT_THRESHOLD | Core tests: PASS"
echo "   Run ./tools/audit_all.sh for full validation before PR"
echo "════════════════════════════════════════════════════════════"
