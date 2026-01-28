#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses
export PYTHONHASHSEED=0

echo "== RCX: goldens UPDATE (explicit) =="
RCX_UPDATE_GOLDENS=1 RCX_ACK_GOLDEN_UPDATE=YES \
  python3 -m pytest -q tests/test_semantic_goldens.py
