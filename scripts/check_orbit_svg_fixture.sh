#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
SVG_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"

[[ -f "$DOT_FIXTURE" ]] || { echo "missing dot fixture: $DOT_FIXTURE" >&2; exit 1; }
[[ -f "$SVG_FIXTURE" ]] || { echo "missing svg fixture: $SVG_FIXTURE" >&2; exit 1; }

TMP_SVG="$(mktemp -t rcx_orbit_svg.XXXXXX.svg)"
trap 'rm -f "$TMP_SVG"' EXIT

echo "== render DOT -> SVG =="
dot -Tsvg "$DOT_FIXTURE" > "$TMP_SVG"

echo "== validate SVG is parseable + contains expected label =="
python3 - "$TMP_SVG" <<'PY'
import sys, xml.etree.ElementTree as ET

path = sys.argv[1]
data = open(path, "rb").read()

# Parse XML
try:
    root = ET.fromstring(data)
except Exception as e:
    print("FAIL: SVG is not valid XML:", e, file=sys.stderr)
    sys.exit(2)

# Basic sanity: root tag ends with 'svg'
tag = root.tag
if not (tag.endswith("svg") or tag.endswith("}svg")):
    print(f"FAIL: root element is not <svg>: {tag!r}", file=sys.stderr)
    sys.exit(2)

# Semantic anchor: the graph label should appear as text somewhere
txt = data.decode("utf-8", errors="replace")
needle = "rcx_core | rcx.engine_run.v1 orbit"
if needle not in txt:
    print("FAIL: expected orbit label text not found in SVG output", file=sys.stderr)
    print(f"missing: {needle!r}", file=sys.stderr)
    sys.exit(2)

print("OK: SVG renders + parses + contains expected label")
PY
