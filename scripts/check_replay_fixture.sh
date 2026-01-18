#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

SNAPSHOT_FIXTURE="docs/fixtures/snapshot_rcx_core_v1.json"
ENGINE_RUN_FIXTURE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"

if [[ ! -f "$SNAPSHOT_FIXTURE" ]]; then
  echo "missing snapshot fixture: $SNAPSHOT_FIXTURE" >&2
  exit 1
fi

if [[ ! -f "$ENGINE_RUN_FIXTURE" ]]; then
  echo "missing engine-run fixture: $ENGINE_RUN_FIXTURE" >&2
  exit 1
fi

TMP="$(mktemp -t rcx_engine_run_from_snapshot.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT

echo "== build examples =="
( cd rcx_pi_rust && cargo build --examples >/dev/null )

echo "== replay snapshot -> engine_run json =="
( cd rcx_pi_rust && cargo run --quiet --example replay_snapshot_cli -- "../$SNAPSHOT_FIXTURE" rcx_core > "$TMP" )

if command -v jq >/dev/null 2>&1; then
  jq . "$TMP" >/dev/null
fi

echo "== diff against golden fixture =="
if command -v diff >/dev/null 2>&1; then
  if diff -u "$ENGINE_RUN_FIXTURE" "$TMP" >/dev/null; then
    echo "OK: replay output matches fixture"
    exit 0
  else
    echo "FAIL: replay output drifted from fixture"
    diff -u "$ENGINE_RUN_FIXTURE" "$TMP" || true
    exit 2
  fi
else
  # ultra-portable fallback
  python3 - <<PY2
import pathlib, sys
a = pathlib.Path("$ENGINE_RUN_FIXTURE").read_text(encoding="utf-8")
b = pathlib.Path("$TMP").read_text(encoding="utf-8")
if a == b:
    print("OK: replay output matches fixture")
    sys.exit(0)
print("FAIL: replay output drifted from fixture")
sys.exit(2)
PY2
fi
