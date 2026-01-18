#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
SVG_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"

[[ -f "$DOT_FIXTURE" ]] || { echo "missing dot fixture: $DOT_FIXTURE" >&2; exit 1; }
[[ -f "$SVG_FIXTURE" ]] || { echo "missing svg fixture: $SVG_FIXTURE" >&2; exit 1; }

TMP="$(mktemp -t rcx_orbit_svg.XXXXXX.svg)"
trap 'rm -f "$TMP"' EXIT

dot -Tsvg "$DOT_FIXTURE" > "$TMP"

if diff -u "$SVG_FIXTURE" "$TMP" >/dev/null; then
  echo "OK: orbit SVG matches fixture"
  exit 0
fi

echo "FAIL: orbit SVG drifted from fixture"
diff -u "$SVG_FIXTURE" "$TMP" || true
exit 2
