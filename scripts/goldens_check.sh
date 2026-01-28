#!/usr/bin/env bash
set -euo pipefail
echo "== RCX: goldens check =="
PYTHONHASHSEED=0 python3 -m pytest -q tests/test_semantic_goldens.py
