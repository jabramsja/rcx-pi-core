#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

e() { echo "== $* =="; }

e "1/5 engine_run schema gate"
./scripts/check_engine_run_schema.sh

e "2/5 orbit DOT fixture gate"
./scripts/check_orbit_dot_fixture.sh

e "3/5 orbit SVG semantic gate"
./scripts/check_orbit_svg_fixture.sh

e "4/5 orbit index semantic gate"
./scripts/check_orbit_index_fixture.sh

# Optional: if provenance scripts exist, run them too.
if [ -x ./scripts/check_orbit_provenance.sh ]; then
  e "5/5 orbit provenance gate"
  ./scripts/check_orbit_provenance.sh
else
  e "5/5 done"
fi

echo "OK: all deterministic orbit gates passed"
