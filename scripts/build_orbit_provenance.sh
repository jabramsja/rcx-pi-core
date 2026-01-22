#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ENGINE_RUN="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
GENERATOR="scripts/orbit_engine_run_to_dot.py"
OUT="docs/fixtures/orbit_provenance_v1.json"

[[ -f "$ENGINE_RUN" ]] || { echo "missing $ENGINE_RUN" >&2; exit 1; }
[[ -f "$GENERATOR" ]] || { echo "missing $GENERATOR" >&2; exit 1; }

engine_hash="$(sha256sum "$ENGINE_RUN" | awk '{print $1}')"
generator_hash="$(sha256sum "$GENERATOR" | awk '{print $1}')"
git_commit="$(git rev-parse HEAD)"

cat > "$OUT" <<JSON
{
  "schema": "rcx.orbit.provenance.v1",
  "engine_run_sha256": "$engine_hash",
  "generator_sha256": "$generator_hash",
  "git_commit": "$git_commit"
}
JSON

echo "OK: wrote $OUT"
