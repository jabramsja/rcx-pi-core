#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
SVG_OUT="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"

[[ -f "$DOT_FIXTURE" ]] || { echo "missing dot fixture: $DOT_FIXTURE" >&2; exit 1; }

if ! command -v dot >/dev/null 2>&1; then
  echo "missing graphviz 'dot' binary. Install graphviz and re-run." >&2
  exit 1
fi

dot -Tsvg "$DOT_FIXTURE" > "$SVG_OUT"
echo "OK: wrote $SVG_OUT"
