#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
SVG_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"

[[ -f "$DOT_FIXTURE" ]] || { echo "missing dot fixture: $DOT_FIXTURE" >&2; exit 1; }
[[ -f "$SVG_FIXTURE" ]] || { echo "missing svg fixture: $SVG_FIXTURE" >&2; exit 1; }

TMP_SVG="$(mktemp -t rcx_orbit_svg.XXXXXX.svg)"
NORM_A="$(mktemp -t rcx_orbit_svg_normA.XXXXXX.svg)"
NORM_B="$(mktemp -t rcx_orbit_svg_normB.XXXXXX.svg)"
trap "rm -f \"$TMP_SVG\" \"$NORM_A\" \"$NORM_B\"" EXIT

dot -Tsvg "$DOT_FIXTURE" > "$TMP_SVG"

# Normalize: remove XML/Graphviz comments (Graphviz often embeds version info) + trim trailing whitespace.
norm() {
  python3 - "$1" "$2" <<'PY'
import re, sys
inp, outp = sys.argv[1], sys.argv[2]
txt = open(inp, "r", encoding="utf-8", errors="replace").read().splitlines()
clean = []
for line in txt:
    if re.search(r"<!--.*-->", line):
        continue
    clean.append(line.rstrip())
while clean and clean[0] == "":
    clean.pop(0)
while clean and clean[-1] == "":
    clean.pop()
open(outp, "w", encoding="utf-8").write("\n".join(clean) + "\n")
PY
}

norm "$SVG_FIXTURE" "$NORM_A"
norm "$TMP_SVG"    "$NORM_B"

if diff -u "$NORM_A" "$NORM_B" >/dev/null; then
  echo "OK: orbit SVG matches fixture (normalized)"
  exit 0
fi

echo "FAIL: orbit SVG drifted from fixture (normalized diff below)"
diff -u "$NORM_A" "$NORM_B" || true
exit 2
