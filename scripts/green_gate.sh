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
  echo "[PY 1/8] Python syntax check"
  python3 -m py_compile rcx_start.py
  echo

  echo "[PY 2/8] Contraband check (grep-based lint)"
  ./tools/contraband.sh rcx_pi
  echo

  echo "[PY 3/8] Test theater check (assert True)"
  ./tools/check_test_theater.sh tests
  echo

  echo "[PY 4/8] AST police (catches what grep misses)"
  python3 tools/ast_police.py
  echo

  echo "[PY 5/8] Semantic purity audit (host debt, smuggling detection)"
  ./tools/audit_semantic_purity.sh
  echo

  echo "[PY 6/8] Python test suite"
  python3 -m pytest $PARALLEL_FLAG
  echo

  echo "[PY 7/8] CLI smoke (end-to-end entrypoints)"
  python3 scripts/cli_smoke.py
  echo

  echo "[PY 8/8] JavaScript L3 parity (same projections, same semantics)"
  ./tools/check_js_debt.sh
  ./tools/contraband_js.sh
  ./tools/ast_police_js.sh
  ./tools/check_test_theater_js.sh
  ./tools/seed_police.sh
  if node experiments/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS parity tests pass"
  else
    echo "FAIL: JS parity tests failed"
    node experiments/eval_step.js 2>&1 | tail -10
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
