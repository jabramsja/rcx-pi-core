#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ENGINE_RUN_FIXTURE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
GEN="./scripts/orbit_engine_run_to_dot.py"

[[ -f "$ENGINE_RUN_FIXTURE" ]] || { echo "missing engine-run fixture: $ENGINE_RUN_FIXTURE" >&2; exit 1; }
[[ -f "$DOT_FIXTURE" ]] || { echo "missing dot fixture: $DOT_FIXTURE" >&2; exit 1; }
[[ -x "$GEN" ]] || { echo "missing generator (not executable): $GEN" >&2; exit 1; }

TMP="$(mktemp -t rcx_orbit_dot.XXXXXX.dot)"
trap "rm -f "$TMP"" EXIT

echo "== generate dot from engine_run fixture =="
python3 "$GEN" "$ENGINE_RUN_FIXTURE" "$TMP" >/dev/null

echo "== diff against golden dot fixture =="
if diff -u "$DOT_FIXTURE" "$TMP" >/dev/null; then
  echo "OK: orbit DOT matches fixture"
  exit 0
fi

echo "FAIL: orbit DOT drifted from fixture"
diff -u "$DOT_FIXTURE" "$TMP" || true
exit 2
