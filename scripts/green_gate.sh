#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root no matter where this script lives
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="${1:-all}"   # all | python-only | rust-only

echo "== RCX green gate =="
echo "mode: $MODE"
echo

run_python() {
  echo "[PY 1/2] Python syntax check"
  python3 -m py_compile rcx_start.py
  echo
  echo "[PY 2/2] Python test suite"

  python3 -m pytest
echo
echo "[PY] CLI smoke (end-to-end entrypoints)"
python3 scripts/cli_smoke.py

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
