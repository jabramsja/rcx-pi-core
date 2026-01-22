# EXPERIMENTAL: derived from engine_run; NOT a stable contract yet
# Do not gate in CI until orbit becomes a primary interface

#!/usr/bin/env bash
set -euo pipefail

ENGINE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
OUT="docs/fixtures/orbit_input_v1.json"

[[ -f "$ENGINE" ]] || { echo "missing $ENGINE" >&2; exit 1; }

python3 - "$ENGINE" "$OUT" <<'PY'
import json, sys

engine_path, out_path = sys.argv[1:3]
engine = json.load(open(engine_path))

# Minimal normalization: extract only what orbit needs
orbit_input = {
    "schema_version": "rcx.orbit_input.v1",
    "nodes": engine.get("nodes", []),
    "edges": engine.get("edges", [])
}

json.dump(orbit_input, open(out_path, "w"), indent=2)
print(f"OK: wrote {out_path}")
PY
