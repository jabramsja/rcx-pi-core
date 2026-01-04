#!/usr/bin/env bash
set -euo pipefail
echo "== RCX: goldens check =="
python3 -m pytest -q tests/test_semantic_goldens.py
