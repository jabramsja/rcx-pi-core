#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

INPUT="docs/fixtures/orbit_input_v1.json"
SCHEMA="docs/fixtures/orbit_input_schema_v1.json"

[[ -f "$INPUT" ]] || { echo "WARN: missing $INPUT (experimental)"; exit 0; }
[[ -f "$SCHEMA" ]] || { echo "WARN: missing $SCHEMA (experimental)"; exit 0; }

python3 - "$INPUT" "$SCHEMA" <<'PY'
import json, sys
from jsonschema import Draft7Validator

inp, sch = sys.argv[1:3]

try:
    data = json.load(open(inp))
except Exception as e:
    print(f"WARN: orbit_input is not valid JSON (experimental): {e}")
    sys.exit(0)

schema = json.load(open(sch))

errors = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: list(e.path))
if errors:
    print("WARN: orbit_input schema violations (experimental):")
    for e in errors:
        loc = ".".join(str(p) for p in e.path) or "<root>"
        print(f" - {loc}: {e.message}")
    sys.exit(0)

print("OK: orbit_input conforms to schema v1 (experimental)")
PY
