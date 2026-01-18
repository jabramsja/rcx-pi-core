#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

INDEX_HTML="docs/fixtures/index.html"
SVG_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"
DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
ENGINE_RUN_FIXTURE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"

[[ -f "$INDEX_HTML" ]] || { echo "missing index: $INDEX_HTML" >&2; exit 1; }

python3 - "$INDEX_HTML" "$ENGINE_RUN_FIXTURE" "$DOT_FIXTURE" "$SVG_FIXTURE" <<'PY'
import sys
from pathlib import Path

idx, eng, dot, svg = map(Path, sys.argv[1:5])
txt = idx.read_text(encoding="utf-8", errors="replace")

needles = [
    "RCX Orbit Artifacts (v1)",
    eng.name,
    dot.name,
    svg.name,
    'data="' + svg.name + '"',
    "./scripts/build_orbit_artifacts.sh",
]
missing = [n for n in needles if n not in txt]
if missing:
    print("FAIL: index missing expected anchors:", file=sys.stderr)
    for m in missing:
        print("  -", repr(m), file=sys.stderr)
    sys.exit(2)
print("OK: index contains expected anchors")
PY
