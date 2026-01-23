#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT="docs/fixtures/orbit_provenance_v1.json"
TMP="$(mktemp)"
cleanup(){ rm -f "$TMP"; }
trap cleanup EXIT

mkdir -p docs/fixtures

# Run from crate dir so relative mu_programs/ paths resolve in CI too.
( cd rcx_pi_rust && cargo run --quiet --example orbit_json_cli -- pingpong ping 12 ) > "$TMP"

# Validate shape (do not reformat)
python3 - <<'PY' "$TMP"
import json, sys
from pathlib import Path

tmp = Path(sys.argv[1])
d = json.loads(tmp.read_text(encoding="utf-8"))

schema = d.get("schema")
states = d.get("states", [])
prov = d.get("provenance", None)

if schema not in ("rcx.orbit.v1", "rcx.orbit.provenance.v1"):
    raise SystemExit(f"FAIL: unexpected schema: {schema!r}")

if not isinstance(states, list) or len(states) < 2:
    raise SystemExit(f"FAIL: expected states>=2, got {len(states) if isinstance(states, list) else type(states)}")

if not isinstance(prov, list) or len(prov) < 1:
    raise SystemExit(f"FAIL: expected provenance>=1, got {len(prov) if isinstance(prov, list) else type(prov)}")

print(f"OK: schema={schema} states={len(states)} provenance={len(prov)}")
PY

# Write exact bytes
cp "$TMP" "$OUT"
echo "OK: wrote $OUT"
