#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# Resolve repo root no matter where this script lives
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="${1:-all}"   # all | python-only | rust-only

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
  echo "[PY 1/11] Repo clean check"
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Repo not clean"
    git status --porcelain
    exit 1
  fi
  echo "OK: Repo is clean"
  echo

  echo "[PY 2/11] Python syntax check"
  python3 -m py_compile rcx_start.py
  echo

  echo "[PY 3/11] Contraband check (grep-based lint)"
  ./tools/contraband.sh rcx_pi
  echo

  echo "[PY 4/11] Test theater check (assert True)"
  ./tools/check_test_theater.sh tests
  echo

  echo "[PY 5/11] AST police (catches what grep misses)"
  python3 tools/ast_police.py
  echo

  echo "[PY 6/11] Anti-cheat scans (test integrity)"
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

  # No underscore-prefixed keys in prototype JSON
  echo "-- no underscore-prefixed keys in prototype JSON (non-standard Mu)"
  # Note: kernel/match/subst seeds use underscore-prefixed fields for state (_mode, _phase, etc.)
  # Note: mu/closures/ seeds (recurrence, exhaustion) use underscore-prefixed fields for engine state
  # Note: mu/programs/ seeds (rcx_engine) use underscore-prefixed fields for engine state
  # Note: mu/bridge/ seeds (bootstrap_structural) use underscore-prefixed fields for match state
  if grep -RInE --include='*.json' '"_[a-zA-Z]+":' prototypes/ mu/ 2>/dev/null | \
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
      grep -v 'bootstrap_structural.v1.json'; then
    echo "ERROR: Found non-standard underscore keys in JSON"
    exit 1
  fi
  echo "OK"
  echo

  echo "[PY 7/11] Semantic purity audit (host debt, smuggling detection)"
  ./tools/audit_semantic_purity.sh
  echo

  echo "[PY 8/11] Python test suite (excludes stress + slow tests)"
  # Stress tests have 60-120s deadlines per example, run separately in audit_all.sh
  # Slow tests (meta-circular recurrence, paxos e2e) run in audit_all.sh / nightly
  # Also exclude test_js_parity_automated.py - JS parity verified via node run in step 11
  python3 -m pytest $PARALLEL_FLAG -m "not slow" --ignore=tests/stress/ --ignore=tests/test_js_parity_automated.py
  echo

  echo "[PY 9/11] Fixture v2 validation"
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

  echo "[PY 10/11] CLI smoke (end-to-end entrypoints)"
  python3 scripts/cli_smoke.py
  echo

  echo "[PY 11/11] JavaScript L3 parity (same projections, same semantics)"
  ./tools/check_js_debt.sh
  ./tools/contraband_js.sh
  ./tools/ast_police_js.sh
  ./tools/check_test_theater_js.sh
  ./tools/seed_police.sh
  if node mu/host/js/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS parity tests pass"
  else
    echo "FAIL: JS parity tests failed"
    node mu/host/js/eval_step.js 2>&1 | tail -10
    exit 1
  fi
  echo
}

run_rust() {
  echo "[RUST 1/2] Rust examples suite (no cargo test)"
  # Prefer repo-root scripts/green_examples.sh if present; fallback to rcx_pi_rust/scripts/green_examples.sh
  if [ -x scripts/green_examples.sh ]; then
    bash scripts/green_examples.sh
  elif [ -x rcx_pi_rust/scripts/green_examples.sh ]; then
    bash rcx_pi_rust/scripts/green_examples.sh
  else
    echo "Not found in provided corpus/output: scripts/green_examples.sh or rcx_pi_rust/scripts/green_examples.sh"
    exit 2
  fi
  echo

  echo "[RUST 2/2] Snapshot integrity (sha256 locked)"

echo
echo "[PY] Ensure pytest for Rust snapshot integrity"
python3 -c "import pytest" >/dev/null 2>&1 || {
  # Make pip available (best-effort), then install pytest into user site so it works even on system python.
  python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
  python3 -m pip install --user -U pip >/dev/null 2>&1 || true
  python3 -m pip install --user -U pytest >/dev/null
}
  python3 -m pytest -q tests/test_snapshot_integrity.py
  echo
}

case "$MODE" in
  all)
    run_python
    run_rust
    echo "✅ ALL GREEN"
    ;;
  python-only)
    run_python
    echo "✅ PY GREEN"
    ;;
  rust-only)
    run_rust
    echo "✅ RUST GREEN"
    ;;
  *)
    echo "ERROR: unknown mode: $MODE"
    echo "usage: scripts/green_gate.sh [all|python-only|rust-only]"
    exit 2
    ;;
esac
