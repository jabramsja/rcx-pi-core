#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# Resolve repo root no matter where this script lives
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

MODE="${1:-all}"   # all | python-only
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-300}"  # per-test timeout guard (seconds)

# Check if pytest-xdist is available for parallel execution (2-3x speedup)
# Using --dist worksteal for better load balancing (idle workers steal from busy)
PARALLEL_FLAG=""
if python3 -c "import xdist" 2>/dev/null; then
    PARALLEL_FLAG="-n auto --dist worksteal"
    echo "Using parallel execution with worksteal (pytest-xdist detected)"
fi

echo "== RCX green gate =="
echo "mode: $MODE"
echo

run_python() {
  echo "[PY 1/17] Repo clean check"
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Repo not clean"
    git status --porcelain
    exit 1
  fi
  echo "OK: Repo is clean"
  echo

  echo "[PY 2/17] Contraband check (grep-based lint)"
  ./tools/checks/linters/contraband.sh rcx_pi
  echo

  echo "[PY 3/17] Test theater check (assert True)"
  ./tools/checks/check_test_theater.sh tests
  echo

  echo "[PY 4/17] L4 gate theater risk ratchet"
  python3 tools/checks/check_theater_risk_ratchet.py
  echo

  echo "[PY 5/17] Seed-auto execution contract check"
  python3 tools/checks/check_seed_auto_execution_contract.py
  echo

  echo "[PY 6/17] Host-semantics ratchet check"
  python3 tools/checks/check_host_semantics_ratchet.py
  echo

  echo "[PY 6b/17] Bootstrap purity ratchet check"
  python3 tools/checks/check_bootstrap_purity_ratchet.py
  echo

  echo "[PY 6c/17] Boot layer boundary check"
  python3 tools/checks/check_boot_layer_boundaries.py
  echo

  echo "[PY 6d/17] Host-authority inventory ratchet check"
  python3 tools/checks/check_host_authority_inventory_ratchet.py
  echo

  echo "[PY 7/17] AST police (catches what grep misses)"
  python3 tools/checks/linters/ast_police.py
  echo

  echo "[PY 8/17] Anti-cheat scans (test integrity)"
  # No private attr access in tests/ (AST-based; docstring-aware)
  echo "-- no private attr access in tests/ (AST-based)"
  python3 tools/checks/linters/check_private_attr_access.py || exit 1
  echo "OK"

  # No underscored imports from rcx_pi in tests/ (AST-based)
  echo "-- no underscored imports from rcx_pi in tests/ (AST-based)"
  python3 tools/checks/linters/check_underscore_imports.py || exit 1
  echo "OK"

  # No underscore-prefixed keys in JSON
  echo "-- no underscore-prefixed keys in JSON (non-standard Mu)"
  # Note: kernel/match/subst seeds use underscore-prefixed fields for state (_mode, _phase, etc.)
  # Note: mu/closures/ seeds (recurrence, exhaustion) use underscore-prefixed fields for engine state
  # Note: mu/programs/ seeds (rcx_engine) use underscore-prefixed fields for engine state
  # Note: mu/bridge/ seeds (bootstrap_structural) use underscore-prefixed fields for match state
  # Note: mu/utilities/ seeds (terminal_classify) use underscore-prefixed fields for wrapper keys (_tc, _tc_exit)
  # Note: mu/stage0/examples/ Stage0 VM bundles use underscore-prefixed fields for state (_mode, _status, _bindings, etc.)
  # Note: mu/stage0/compiled/ compiled bundles inherit underscore keys from source seeds (mechanically derived)
  # Note: mu/tests/fixtures/ test vectors intentionally use underscore keys for kernel-internal state
  if grep -RInE --include='*.json' '"_[a-zA-Z]+":' mu/ 2>/dev/null | \
      grep -v '"_marker":' | \
      grep -v '"_type":' | \
      grep -v 'kernel.v1.json' | \
      grep -v 'match.v2.json' | \
      grep -v 'subst.v2.json' | \
      grep -v 'recurrence.v1.json' | \
      grep -v 'exhaustion.v1.json' | \
      grep -v 'rcx_engine.v1.json' | \
      grep -v 'enginenews.v1.json' | \
      grep -v 'exhaust.v1.json' | \
      grep -v 'bootstrap_structural.v1.json' | \
      grep -v 'terminal_classify.v1.json' | \
      grep -v 'mu/stage0/examples/' | \
      grep -v 'mu/stage0/compiled/' | \
      grep -v 'mu/tests/fixtures/'; then
    echo "ERROR: Found non-standard underscore keys in JSON"
    exit 1
  fi
  echo "OK"
  echo

  echo "[PY 9/17] Semantic purity audit (host debt, smuggling detection)"
  ./tools/audit_semantic_purity.sh
  echo

  echo "[PY 9b/17] Test speed enforcer (catches misclassified slow tests)"
  bash tools/checks/check_test_speed.sh
  echo

  echo "[PY 9c/17] Simulated production logic check (RT2+RT3)"
  python3 tools/checks/check_simulated_production_logic.py
  echo

  # Nightly (ci_full) runs ALL tests including fuzzers, slow, and JS parity;
  # push/PR excludes fuzzers and slow (JS parity verified via node run in step 11)
  if [ "${HYPOTHESIS_PROFILE:-}" = "ci_full" ]; then
    echo "[PY 10/17] Python test suite — NIGHTLY (includes fuzzers + slow + JS parity)"
    python3 -m pytest $PARALLEL_FLAG --ignore=tests/stress/ --timeout="$PYTEST_TIMEOUT"
  else
    echo "[PY 10/17] Python test suite (excludes stress, slow, fuzzer)"
    # Fuzzer tests run 50+ hypothesis examples each, consuming ~22 min on CI
    # Run fuzzers via: audit_all.sh (local) or nightly CI (ci_full profile)
    # Slow tests (meta-circular, engine pipeline, hemispheres) run in nightly
    # Note: test_js_parity_automated.py is no longer fully ignored — see step 10b
    python3 -m pytest $PARALLEL_FLAG -m "not slow and not fuzzer" \
      --ignore=tests/stress/ \
      --ignore=tests/parity/test_js_parity_automated.py \
      --timeout="$PYTEST_TIMEOUT"
  fi
  echo

  echo "[PY 10b/17] Cross-substrate parity canary (F-01: fast behavioral check)"
  # Single cross-substrate comparison via run_vector JSON API.
  # Full parity suite (150+ tests, ~54s) runs in audit_fast.sh and nightly.
  # This canary catches parity regressions at merge-time in <2s.
  python3 -m pytest tests/parity/test_js_parity_automated.py::test_parity_canary \
    --timeout="$PYTEST_TIMEOUT" -q
  echo

  echo "[PY 10c/17] Cross-substrate parity gate (L3 hard gate, ~7s)"
  # Gate-mapped parity + fast structural parity tests. Catches seed checksum drift,
  # constant divergence, algorithm parity regressions. Excludes slow subprocess-based
  # cross-substrate tests (test_js_parity_automated.py, test_boot1_shadow_parity.py)
  # which run in nightly. Added per founder directive (wave6, 2026-03-12).
  python3 -m pytest $PARALLEL_FLAG -m "not fuzzer and not slow" tests/parity/ \
    --ignore=tests/parity/test_js_parity_automated.py \
    --ignore=tests/parity/test_boot1_shadow_parity.py \
    --timeout="$PYTEST_TIMEOUT" -q
  echo

  echo "[PY 10d/17] L4 gate evidence tests (slow-marked but merge-blocking)"
  # BR-2: 116 L4 gate tests are marked @pytest.mark.slow (they call run_mu,
  # run_engine_pipeline, etc.) but are fast enough for CI (~24s local, ~40s CI).
  # These are the L4 evidence tests that prove gate passage — must run at merge.
  python3 -m pytest $PARALLEL_FLAG -m "slow" tests/l4_gates/ \
    --timeout="$PYTEST_TIMEOUT" -q
  echo

  echo "[PY 11/17] Fixture v2 validation"
  FIXTURE_COUNT=0
  EMPTY_COUNT=0
  for f in $(find tests/fixtures/traces_v2 -name '*.v2.jsonl' -maxdepth 3 2>/dev/null | sort); do
    FIXTURE_COUNT=$((FIXTURE_COUNT + 1))
    n="$(wc -l < "$f" | tr -d ' ')"
    if [ "$n" -eq 0 ]; then
      echo "ERROR: Empty fixture: $f"
      EMPTY_COUNT=$((EMPTY_COUNT + 1))
    fi
  done
  echo "Validated $FIXTURE_COUNT fixtures"
  if [ "$EMPTY_COUNT" -gt 0 ]; then
    echo "ERROR: Found $EMPTY_COUNT empty fixtures"
    exit 1
  fi
  if [ "$FIXTURE_COUNT" -lt 10 ]; then
    echo "ERROR: Expected 10+ fixtures, found $FIXTURE_COUNT"
    exit 1
  fi
  echo "OK"
  echo

  echo "[PY 12/17] CLI smoke (end-to-end entrypoints)"
  python3 scripts/utils/cli_smoke.py
  echo

  echo "[PY 13/17] JavaScript L3 parity (same projections, same semantics)"
  ./tools/checks/check_js_debt.sh
  ./tools/checks/linters/contraband_js.sh
  ./tools/checks/linters/ast_police_js.sh
  ./tools/checks/check_test_theater_js.sh
  ./tools/checks/linters/seed_police.sh
  if node mu/host/js/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS parity tests pass"
  else
    echo "FAIL: JS parity tests failed"
    node mu/host/js/eval_step.js 2>&1 | tail -10
    exit 1
  fi
  echo
}

case "$MODE" in
  all|python-only)
    run_python
    echo "✅ PY GREEN"
    ;;
  *)
    echo "ERROR: unknown mode: $MODE"
    echo "usage: scripts/green_gate.sh [all|python-only]"
    exit 2
    ;;
esac
