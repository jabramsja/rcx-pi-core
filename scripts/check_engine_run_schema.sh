#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ENGINE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
SCHEMA="docs/fixtures/engine_run_schema_v1.json"

[[ -f "$ENGINE" ]] || { echo "FAIL: missing $ENGINE" >&2; exit 1; }
[[ -f "$SCHEMA" ]] || { echo "FAIL: missing $SCHEMA" >&2; exit 1; }

python3 - "$ENGINE" "$SCHEMA" <<'PY'
import json, sys
from jsonschema import Draft7Validator

engine_path, schema_path = sys.argv[1:3]

try:
    engine = json.load(open(engine_path))
except Exception as e:
    print("FAIL: engine_run is not valid JSON:", e, file=sys.stderr)
    sys.exit(2)

if not isinstance(engine, dict):
    print("FAIL: engine_run must be a JSON object at top-level", file=sys.stderr)
    sys.exit(2)

schema = json.load(open(schema_path))

# Soft version check:
sv = engine.get("schema_version")
schema_field = engine.get("schema")

# Accept either schema_version (preferred) or schema (legacy/current fixture field).
effective = sv if sv is not None else schema_field

if effective is None:
    print("WARN: engine_run has no schema_version/schema (allowed for raw v1 artifacts)")
elif effective != "rcx.engine_run.v1":
    label = "schema_version" if sv is not None else "schema"
    print(f"FAIL: unsupported {label}: {effective!r}", file=sys.stderr)
    sys.exit(2)

validator = Draft7Validator(schema)
errors = sorted(validator.iter_errors(engine), key=lambda e: list(e.path))

if errors:
    print("FAIL: engine_run schema violations:", file=sys.stderr)
    for e in errors:
        loc = ".".join(str(p) for p in e.path) or "<root>"
        print(f" - {loc}: {e.message}", file=sys.stderr)
    sys.exit(2)

print("OK: engine_run accepted as raw v1 artifact")
PY
