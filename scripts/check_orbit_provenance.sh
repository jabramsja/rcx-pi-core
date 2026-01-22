#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ENGINE_RUN="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
GENERATOR="scripts/orbit_engine_run_to_dot.py"
PROV="docs/fixtures/orbit_provenance_v1.json"

[[ -f "$ENGINE_RUN" ]] || { echo "FAIL: missing $ENGINE_RUN" >&2; exit 1; }
[[ -f "$GENERATOR" ]] || { echo "FAIL: missing $GENERATOR" >&2; exit 1; }
[[ -f "$PROV" ]] || { echo "FAIL: missing $PROV" >&2; exit 1; }

python3 - "$ENGINE_RUN" "$GENERATOR" "$PROV" <<'PY'
import json, sys, hashlib, pathlib

eng, gen, prov = map(pathlib.Path, sys.argv[1:4])

def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

data = json.loads(prov.read_text())

errors = []
if data.get("schema") != "rcx.orbit.provenance.v1":
    errors.append("schema tag mismatch")

if data.get("engine_run_sha256") != sha(eng):
    errors.append("engine_run hash mismatch")

if data.get("generator_sha256") != sha(gen):
    errors.append("generator hash mismatch")

if errors:
    print("FAIL: orbit provenance mismatch:", file=sys.stderr)
    for e in errors:
        print(" -", e, file=sys.stderr)
    sys.exit(2)

print("OK: orbit provenance matches inputs")
PY
