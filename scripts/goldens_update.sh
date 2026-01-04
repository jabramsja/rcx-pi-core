#!/usr/bin/env bash
set -euo pipefail
echo "== RCX: goldens UPDATE (explicit) =="
RCX_UPDATE_GOLDENS=1 RCX_ACK_GOLDEN_UPDATE=YES \
  python3 -m pytest -q tests/test_semantic_goldens.py
