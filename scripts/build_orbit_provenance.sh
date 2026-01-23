#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT="docs/fixtures/orbit_provenance_v1.json"
TMP="$(mktemp)"
cleanup(){ rm -f "$TMP"; }
trap cleanup EXIT

mkdir -p docs/fixtures

# Canonical generator: use existing example that already supports:
#   cargo run --example orbit_json_cli -- pingpong ping 12
#
# IMPORTANT: run from rcx_pi_rust/ because Cargo.toml lives there.
GEN=( bash -lc 'cd rcx_pi_rust && cargo run --quiet --example orbit_json_cli -- pingpong ping 12' )
"${GEN[@]}" > "$TMP"

python3 - <<'PY' "$TMP" "$OUT"
import json, sys
from pathlib import Path

tmp = Path(sys.argv[1])
out = Path(sys.argv[2])

d = json.loads(tmp.read_text(encoding="utf-8"))

schema = d.get("schema")
states = d.get("states", [])
prov = d.get("provenance", None)

if schema != "rcx.orbit.v1":
    raise SystemExit(f"FAIL: expected schema rcx.orbit.v1, got {schema!r}")

if not isinstance(states, list) or len(states) < 2:
    raise SystemExit(f"FAIL: expected states>=2, got {len(states) if isinstance(states, list) else type(states)}")

# We are explicitly building the provenance fixture, so enforce non-empty provenance.
if not isinstance(prov, list):
    raise SystemExit(f"FAIL: expected provenance list, got {type(prov).__name__}")
if len(prov) < 1:
    raise SystemExit("FAIL: provenance is empty (expected >=1 entries for pingpong)")

out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"OK: wrote {out} (states={len(states)} provenance={len(prov)})")
print("first provenance keys:", sorted(prov[0].keys()))
PY
