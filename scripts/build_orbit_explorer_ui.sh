#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# This is a static file right now, so "build" just verifies it exists.
HTML="docs/fixtures/orbit_explorer_v1.html"
[[ -f "$HTML" ]] || { echo "missing: $HTML" >&2; exit 1; }

# Best-effort sanity: ensure it references rcx.orbit.v1 and a default fixture filename
python3 - <<'PY' "$HTML"
import sys
from pathlib import Path
p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
need = ["rcx.orbit.v1", "orbit_provenance_v1.json", "Orbit Explorer (v1)"]
for n in need:
    if n not in s:
        raise SystemExit(f"FAIL: expected marker missing: {n!r}")
print(f"OK: explorer UI present: {p}")
PY
