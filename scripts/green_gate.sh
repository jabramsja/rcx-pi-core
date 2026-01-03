#!/usr/bin/env bash
set -euo pipefail

# Run from repo root (where rcx_start.py lives)
cd "$(dirname "$0")"

echo "== RCX green gate =="

echo "[1/3] Python syntax check"
python3 -m py_compile rcx_start.py

echo "[2/3] Python test suite"
python3 -m pytest

echo "[3/3] Rust examples suite (no cargo test)"
bash rcx_pi_rust/scripts/green_examples.sh

echo "✅ ALL GREEN"