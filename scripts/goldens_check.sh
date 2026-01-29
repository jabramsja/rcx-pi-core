#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses
export PYTHONHASHSEED=0

echo "== RCX: goldens check =="
python3 -m pytest -q tests/test_semantic_goldens.py
