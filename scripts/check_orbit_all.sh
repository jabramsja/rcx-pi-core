#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

e() { echo "== $* =="; }

e "1/6 replay fixture gate"
./scripts/check_replay_fixture.sh

e "2/6 orbit DOT fixture gate"
./scripts/check_orbit_dot_fixture.sh

e "3/6 orbit SVG semantic gate"
./scripts/check_orbit_svg_fixture.sh

e "4/6 orbit index semantic gate"
./scripts/check_orbit_index_fixture.sh

e "5/6 orbit provenance gate"
./scripts/check_orbit_provenance.sh

e "6/6 done"
echo "OK: all deterministic orbit gates passed"
