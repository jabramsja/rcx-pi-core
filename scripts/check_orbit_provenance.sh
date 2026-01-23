#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PROV="docs/fixtures/orbit_provenance_v1.json"

[[ -f "$PROV" ]] || { echo "missing provenance fixture: $PROV" >&2; exit 1; }

python3 - <<'PY' "$PROV"
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))

schema = data.get("schema")

# Canonical schema is rcx.orbit.v1 (matches docs/schemas/rcx.orbit.v1.schema.json)
# Accept legacy alias too, if it ever shows up.
if schema not in ("rcx.orbit.v1", "rcx.orbit.provenance.v1"):
    raise SystemExit(f"FAIL: unexpected schema: {schema!r}")

states = data.get("states", [])
prov = data.get("provenance", [])

if not isinstance(states, list) or len(states) < 2:
    raise SystemExit(f"FAIL: expected states>=2, got {len(states) if isinstance(states, list) else type(states)}")

if not isinstance(prov, list) or len(prov) < 1:
    raise SystemExit(f"FAIL: expected provenance>=1, got {len(prov) if isinstance(prov, list) else type(prov)}")

first_keys = sorted(prov[0].keys()) if prov else None
print(f"OK: schema={schema} states={len(states)} provenance={len(prov)} first_keys={first_keys}")
PY

echo "OK: provenance fixture gate passed: $PROV"
