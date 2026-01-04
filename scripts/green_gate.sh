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
}

run_rust() {
  echo "[RUST 1/1] Rust examples suite (no cargo test)"
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
