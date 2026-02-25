#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# Resolve repo root no matter where this script lives
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

MODE="${1:-all}"   # all | python-only

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
  echo "[PY 1/10] Repo clean check"
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Repo not clean"
    git status --porcelain
    exit 1
  fi
  echo "OK: Repo is clean"
  echo

  echo "[PY 2/10] Contraband check (grep-based lint)"
  ./tools/checks/linters/contraband.sh rcx_pi
  echo

  echo "[PY 3/10] Test theater check (assert True)"
  ./tools/checks/check_test_theater.sh tests
  echo

  echo "[PY 4/10] AST police (catches what grep misses)"
  python3 tools/checks/linters/ast_police.py
  echo

  echo "[PY 5/10] Anti-cheat scans (test integrity)"
  # No private attr access in tests/
  echo "-- no private attr access in tests/"
  if grep -RInE '\._[a-zA-Z0-9]+' tests/ 2>/dev/null | \
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
      grep -v 'mu/tests/fixtures/'; then
    echo "ERROR: Found non-standard underscore keys in JSON"
    exit 1
  fi
  echo "OK"
  echo

  echo "[PY 6/10] Semantic purity audit (host debt, smuggling detection)"
  ./tools/audit_semantic_purity.sh
  echo

  # Nightly (ci_full) runs ALL tests including fuzzers, slow, and JS parity;
  # push/PR excludes fuzzers and slow (JS parity verified via node run in step 11)
  if [ "${HYPOTHESIS_PROFILE:-}" = "ci_full" ]; then
    echo "[PY 7/10] Python test suite — NIGHTLY (includes fuzzers + slow + JS parity)"
    python3 -m pytest $PARALLEL_FLAG --ignore=tests/stress/ --timeout=300
  else
    echo "[PY 7/10] Python test suite (excludes stress, slow, fuzzer, and JS parity tests)"
    # Fuzzer tests run 50+ hypothesis examples each, consuming ~22 min on CI
    # Run fuzzers via: audit_all.sh (local) or nightly CI (ci_full profile)
    # Slow tests (meta-circular, engine pipeline, hemispheres) run in nightly
    # JS parity tests spawn node subprocesses — nightly only; fast path has step 11
    python3 -m pytest $PARALLEL_FLAG -m "not slow and not fuzzer" --ignore=tests/stress/ --ignore=tests/parity/test_js_parity_automated.py
  fi
  echo

  echo "[PY 8/10] Fixture v2 validation"
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

  echo "[PY 9/10] CLI smoke (end-to-end entrypoints)"
  python3 scripts/utils/cli_smoke.py
  echo

  echo "[PY 10/10] JavaScript L3 parity (same projections, same semantics)"
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
